"""
LangGraph-based agent orchestrator.
Each agent is a real ReAct agent with tool use, chain-of-thought, and streaming steps.
"""
import os
import time
from typing import Callable, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from tools import BASE_TOOL_MAP, make_send_message_tool

# ─── Task → location keyword map ────────────────────────────────────────────
TASK_LOCATION: Dict[str, str] = {
    "research":    "table1", "search":    "table1", "find":      "table1",
    "analyze":     "table1", "analyse":   "table1", "look up":   "table1",
    "investigate": "table1", "explore":   "table1",
    "write":       "table2", "writing":   "table2", "document":  "table2",
    "draft":       "table2", "report":    "table2", "summarize": "table2",
    "summarise":   "table2", "create":    "table2", "compose":   "table2",
    "code":        "pc1",    "program":   "pc1",    "debug":     "pc1",
    "develop":     "pc1",    "fix":       "pc1",    "implement": "pc1",
    "script":      "pc1",    "build":     "pc1",    "test":      "pc1",
}


def infer_location(task: str) -> Optional[str]:
    tl = task.lower()
    for kw, loc in TASK_LOCATION.items():
        if kw in tl:
            return loc
    return None


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _build_llm(provider: str, model: str, temperature: float,
               key_claude: str, key_openai: str):
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(api_key=key_openai, model=model, temperature=temperature)
    else:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(api_key=key_claude, model_name=model, temperature=temperature)


def _build_tools(enabled: list, mcp_active: list, inter_agent_messages: dict) -> list:
    tools = []
    for tid in enabled:
        if tid == "send_message_to_agent":
            tools.append(make_send_message_tool(inter_agent_messages))
        elif tid in BASE_TOOL_MAP:
            tools.append(BASE_TOOL_MAP[tid])

    # Map active MCP presets → real LangChain tools where possible
    for mcp in mcp_active:
        mid = mcp.get("id", "")
        if mid == "tavily":
            try:
                from langchain_community.tools.tavily_search import TavilySearchResults
                key = os.getenv("TAVILY_API_KEY", "")
                if key:
                    tools.append(TavilySearchResults(max_results=5, tavily_api_key=key))
            except ImportError:
                pass
        elif mid == "gmail":
            # Gmail requires real OAuth — described in system prompt, not as a tool
            pass
        elif mid == "filesystem":
            try:
                from langchain_community.tools.file_management import (
                    ReadFileTool, WriteFileTool, ListDirectoryTool,
                )
                tools.extend([ReadFileTool(), WriteFileTool(), ListDirectoryTool()])
            except ImportError:
                pass

    return tools


def _ai_msg_text(msg: AIMessage) -> str:
    """Extract plain text from an AIMessage (handles both string and list content)."""
    if isinstance(msg.content, str):
        return msg.content
    if isinstance(msg.content, list):
        parts = []
        for block in msg.content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _build_system(agent_dict: dict, prior_context: str, mcp_active: list) -> str:
    cfg = agent_dict.get("ai_config", {})

    mcp_lines = ""
    for s in mcp_active:
        mcp_lines += f"\n  • {s['name']}: {s.get('description', '')}"

    base = cfg.get("system_prompt") or (
        f"You are {agent_dict['name']}, an autonomous AI agent in a collaborative workspace.\n"
        "Think step-by-step. Use your tools to gather real information before answering.\n"
        "Do not guess or make up facts — always search first.\n"
        "Give a clear, structured final response."
    )

    if mcp_lines:
        base += f"\n\nConfigured integrations (use your tools to interact with them):{mcp_lines}"

    if prior_context:
        base += f"\n\n--- Context from collaborating agents ---\n{prior_context}"

    return base


# ─── Single-agent task runner ────────────────────────────────────────────────
async def run_agent_task(
    agent_dict: dict,
    task: str,
    prior_context: str,
    broadcast: Callable,
    inter_agent_messages: Dict[str, List[str]],
) -> str:
    from langgraph.prebuilt import create_react_agent
    from langchain_core.runnables import RunnableConfig

    aid         = agent_dict["id"]
    cfg         = agent_dict.get("ai_config", {})
    provider    = cfg.get("provider", "claude")
    model       = cfg.get("model", "claude-haiku-4-5-20251001")
    temperature = float(cfg.get("temperature", 0.7))

    key_claude = cfg.get("api_key_claude", "") or os.getenv("ANTHROPIC_API_KEY", "")
    key_openai = cfg.get("api_key_openai", "") or os.getenv("OPENAI_API_KEY", "")

    if provider == "openai" and not key_openai:
        msg = f"No OpenAI API key for {agent_dict['name']}. Add it in the AI tab."
        await broadcast({"type": "task_msg", "agent_id": aid,
                         "role": "error", "content": msg, "ts": time.time()})
        return msg
    if provider != "openai" and not key_claude:
        msg = f"No Anthropic API key for {agent_dict['name']}. Add it in the AI tab."
        await broadcast({"type": "task_msg", "agent_id": aid,
                         "role": "error", "content": msg, "ts": time.time()})
        return msg

    try:
        llm = _build_llm(provider, model, temperature, key_claude, key_openai)
    except Exception as e:
        err = f"LLM init error: {e}"
        await broadcast({"type": "task_msg", "agent_id": aid,
                         "role": "error", "content": err, "ts": time.time()})
        return err

    enabled    = cfg.get("enabled_tools", ["web_search", "read_url", "send_message_to_agent"])
    mcp_active = [s for s in agent_dict.get("mcp_servers", []) if s.get("active")]
    tools      = _build_tools(enabled, mcp_active, inter_agent_messages)
    system     = _build_system(agent_dict, prior_context, mcp_active)

    # Build LangGraph ReAct agent (LangGraph 1.x uses `prompt` param)
    agent = create_react_agent(llm, tools, prompt=system)

    # Inject messages from other agents
    received  = inter_agent_messages.pop(aid, [])
    full_task = task
    if received:
        full_task += "\n\n[Messages from collaborating agents]:\n" + "\n".join(received)

    messages   = [HumanMessage(content=full_task)]
    final_text = ""
    config     = RunnableConfig(recursion_limit=30)

    try:
        async for chunk in agent.astream(
            {"messages": messages},
            config=config,
            stream_mode="updates",
        ):
            for node_name, node_output in chunk.items():
                for msg in node_output.get("messages", []):

                    if isinstance(msg, AIMessage):
                        content = _ai_msg_text(msg)

                        if msg.tool_calls:
                            # Agent is reasoning + about to call tools
                            if content:
                                await broadcast({
                                    "type":     "task_thought",
                                    "agent_id": aid,
                                    "content":  content,
                                    "ts":       time.time(),
                                })
                            for tc in msg.tool_calls:
                                await broadcast({
                                    "type":     "task_tool",
                                    "agent_id": aid,
                                    "tool":     tc["name"],
                                    "input":    tc["args"],
                                    "ts":       time.time(),
                                })
                        elif content:
                            # Final answer — no more tool calls
                            final_text = content
                            await broadcast({
                                "type":     "task_msg",
                                "agent_id": aid,
                                "role":     "assistant",
                                "content":  content,
                                "ts":       time.time(),
                            })

                    elif isinstance(msg, ToolMessage):
                        obs = msg.content if isinstance(msg.content, str) else str(msg.content)
                        await broadcast({
                            "type":     "task_observation",
                            "agent_id": aid,
                            "tool":     getattr(msg, "name", ""),
                            "content":  obs[:600],
                            "ts":       time.time(),
                        })

    except Exception as e:
        err = f"Agent error: {e}"
        await broadcast({"type": "task_msg", "agent_id": aid,
                         "role": "error", "content": err, "ts": time.time()})
        return err

    return final_text


# ─── Multi-agent task runner ─────────────────────────────────────────────────
async def run_task(
    agent_ids: List[str],
    task: str,
    env_agents: dict,
    env_objects_snapshot: dict,
    broadcast: Callable,
    move_agent: Callable,
) -> None:
    inter_agent_messages: Dict[str, List[str]] = {}

    # Move agents toward the relevant workspace object
    location_id = infer_location(task)
    if location_id and location_id in env_objects_snapshot:
        obj = env_objects_snapshot[location_id]
        cx  = obj["x"] + obj["w"] / 2
        cy  = obj["y"] + obj["h"] / 2
        n   = len(agent_ids)
        for i, aid in enumerate(agent_ids):
            offset = (i - (n - 1) / 2) * 35
            await move_agent(aid, cx + offset, cy - 40)

    await broadcast({"type": "task_start", "agents": agent_ids,
                     "task": task, "ts": time.time()})

    prior_context = ""
    for aid in agent_ids:
        agent = env_agents.get(aid)
        if not agent:
            continue

        agent_dict = agent.to_dict()
        # Re-inject private API keys (stripped by to_dict for security)
        agent_dict["ai_config"]["api_key_claude"] = agent.ai_config.get("api_key_claude", "")
        agent_dict["ai_config"]["api_key_openai"] = agent.ai_config.get("api_key_openai", "")
        agent_dict["mcp_servers"] = agent.mcp_servers

        await broadcast({"type": "task_agent_start", "agent_id": aid, "ts": time.time()})

        result = await run_agent_task(
            agent_dict, task, prior_context, broadcast, inter_agent_messages
        )

        if result and len(agent_ids) > 1:
            prior_context += f"\n\n[{agent_dict['name']} said]:\n{result}"

    await broadcast({"type": "task_done", "ts": time.time()})
