"""
LangGraph-based agent orchestrator.
Each agent is a real ReAct agent with tool use, chain-of-thought, and streaming steps.
"""
import asyncio
import json
import os
import re
import time
from typing import Callable, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from tools import BASE_TOOL_MAP, make_send_message_tool

# ─── Tool → workspace location map ──────────────────────────────────────────
_SEARCH_TOOLS = {"web_search", "read_url", "search", "tavily", "tavilysearchresults",
                 "browse", "fetch", "duckduckgo", "bing", "google"}
_CODE_TOOLS   = {"readfiletool", "writefiletool", "listdirectorytool",
                 "read_file", "write_file", "list_directory",
                 "exec", "execute", "python", "terminal", "bash", "shell"}


def _tool_location(tool_name: str) -> Optional[str]:
    tl = tool_name.lower()
    if any(kw in tl for kw in ("search", "web", "url", "fetch", "browse", "tavily", "read_url")):
        return "table1"
    if any(kw in tl for kw in ("file", "code", "exec", "python", "terminal", "bash", "shell", "script")):
        return "pc1"
    return None


def infer_location(task: str) -> Optional[str]:
    tl = task.lower()
    for kw, loc in (
        ("research", "table1"), ("search", "table1"), ("find", "table1"),
        ("analyze",  "table1"), ("analyse", "table1"), ("look up", "table1"),
        ("investigate", "table1"), ("explore", "table1"),
        ("write",    "table2"), ("writing", "table2"), ("document", "table2"),
        ("draft",    "table2"), ("report",  "table2"), ("summarize", "table2"),
        ("summarise","table2"), ("create",  "table2"), ("compose",   "table2"),
        ("code",     "pc1"),    ("program", "pc1"),    ("debug",     "pc1"),
        ("develop",  "pc1"),    ("fix",     "pc1"),    ("implement", "pc1"),
        ("script",   "pc1"),    ("build",   "pc1"),    ("test",      "pc1"),
    ):
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
    move_to_location: Optional[Callable] = None,
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
                                # Move to the workspace location matching the tool
                                if move_to_location:
                                    loc = _tool_location(tc["name"])
                                    if loc:
                                        await move_to_location(loc)
                                await broadcast({
                                    "type":     "task_tool",
                                    "agent_id": aid,
                                    "tool":     tc["name"],
                                    "input":    tc["args"],
                                    "ts":       time.time(),
                                })
                        elif content:
                            # Final answer — agent writes response → Table 2
                            if move_to_location:
                                await move_to_location("table2")
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
def _make_move_to_location(aid: str, env_objects_snapshot: dict,
                            move_agent: Callable, env_agents: dict) -> Callable:
    """Return a closure that moves the given agent to a named workspace object."""
    last: Dict[str, str] = {}   # tracks last location to avoid redundant moves

    async def move_to_location(loc_id: str) -> None:
        if last.get("loc") == loc_id:
            return                       # already there / already heading there
        last["loc"] = loc_id
        if loc_id not in env_objects_snapshot:
            return
        obj    = env_objects_snapshot[loc_id]
        cx     = obj["x"] + obj["w"] / 2
        cy     = obj["y"] + obj["h"] / 2
        # slight upward offset so agent stands in front of the object
        await move_agent(aid, cx, cy - 45, loc_id)
        # update agent state immediately so canvas shows movement
        agent = env_agents.get(aid)
        if agent:
            agent.state = "moving"

    return move_to_location


async def run_task(
    agent_ids: List[str],
    task: str,
    env_agents: dict,
    env_objects_snapshot: dict,
    broadcast: Callable,
    move_agent: Callable,
) -> None:
    inter_agent_messages: Dict[str, List[str]] = {}

    # Save home positions before any movement
    home = {aid: (env_agents[aid].x, env_agents[aid].y)
            for aid in agent_ids if aid in env_agents}

    await broadcast({"type": "task_start", "agents": agent_ids,
                     "task": task, "ts": time.time()})

    # Sequential pipeline: each agent gets prior context, returns home when done
    prior_context = ""
    for aid in agent_ids:
        agent = env_agents.get(aid)
        if not agent:
            continue

        agent_dict = agent.to_dict()
        agent_dict["ai_config"]["api_key_claude"] = agent.ai_config.get("api_key_claude", "")
        agent_dict["ai_config"]["api_key_openai"] = agent.ai_config.get("api_key_openai", "")
        agent_dict["mcp_servers"] = agent.mcp_servers

        move_to_loc = _make_move_to_location(aid, env_objects_snapshot, move_agent, env_agents)
        await broadcast({"type": "task_agent_start", "agent_id": aid, "ts": time.time()})

        result = await run_agent_task(
            agent_dict, task, prior_context, broadcast, inter_agent_messages,
            move_to_location=move_to_loc,
        )

        # Agent finished — reset state and walk home immediately
        agent.state = "idle"
        agent.target_x = None
        agent.target_y = None
        agent.interaction_target = None
        if aid in home:
            await move_agent(aid, home[aid][0], home[aid][1], None)

        # Pass result as context to the next agent
        if result:
            prior_context += f"\n\n[{agent_dict['name']} completed]:\n{result}"

    await broadcast({"type": "task_done", "ts": time.time()})


# ─── Auto-planning orchestrator ───────────────────────────────────────────────
async def auto_plan_task(
    task: str,
    env_agents: dict,
    env_objects_snapshot: dict,
    broadcast: Callable,
    move_agent: Callable,
) -> None:
    """Use LLM to decide which agents should handle the task and how."""

    # Find the first available API key
    planner_provider   = "claude"
    planner_model      = "claude-haiku-4-5-20251001"
    planner_key_claude = ""
    planner_key_openai = ""

    for agent in env_agents.values():
        k = agent.ai_config.get("api_key_claude", "") or os.getenv("ANTHROPIC_API_KEY", "")
        if k:
            planner_key_claude = k
            planner_model = agent.ai_config.get("model", "claude-haiku-4-5-20251001")
            break
    if not planner_key_claude:
        for agent in env_agents.values():
            k = agent.ai_config.get("api_key_openai", "") or os.getenv("OPENAI_API_KEY", "")
            if k:
                planner_key_openai = k
                planner_provider = "openai"
                planner_model = "gpt-4o-mini"
                break

    if not planner_key_claude and not planner_key_openai:
        await broadcast({"type": "task_msg", "agent_id": None, "role": "error",
                         "content": "No API keys configured. Add a key in an agent's AI tab.",
                         "ts": time.time()})
        return

    # Build agent capability profiles
    profiles = []
    for aid, agent in env_agents.items():
        cfg     = agent.ai_config
        mcps    = [s["name"] for s in agent.mcp_servers if s.get("active")]
        tools   = cfg.get("enabled_tools", [])
        sp      = (cfg.get("system_prompt") or "").strip()[:200]
        has_key = bool(
            cfg.get("api_key_claude") or os.getenv("ANTHROPIC_API_KEY", "")
            or cfg.get("api_key_openai") or os.getenv("OPENAI_API_KEY", "")
        )
        if not has_key:
            continue  # skip agents with no API key — they can't work
        parts = [f"id={aid}", f"name={agent.name}"]
        if sp:
            parts.append(f"specialty=\"{sp}\"")
        if mcps:
            parts.append(f"integrations={mcps}")
        if tools:
            parts.append(f"tools={tools}")
        profiles.append("- " + ", ".join(parts))

    if not profiles:
        await broadcast({"type": "task_msg", "agent_id": None, "role": "error",
                         "content": "No AI-enabled agents found. Add an API key in an agent's AI tab.",
                         "ts": time.time()})
        return

    plan_prompt = (
        f"Task: {task}\n\n"
        f"Available agents:\n" + "\n".join(profiles) + "\n\n"
        "Your job: decide which agents are actually needed for this task "
        "and assign each a specific subtask.\n\n"
        "Rules:\n"
        "- Include an agent ONLY if the task genuinely benefits from their specialty or integrations.\n"
        "- If the task can be done by one agent, return one element.\n"
        "- Do NOT include agents whose specialty is irrelevant to the task.\n"
        "- Agents run sequentially — order matters. Put research/search agents first, "
        "writing agents second, coding agents last.\n"
        "- Each subtask must be a concrete instruction for that specific agent.\n\n"
        "Respond ONLY with a JSON array, no markdown, no explanation:\n"
        '[{"agent_id":"...","subtask":"..."}]'
    )

    await broadcast({"type": "task_plan", "content": "Planning task distribution…",
                     "ts": time.time()})

    plan: List[dict] = []
    try:
        llm    = _build_llm(planner_provider, planner_model, 0.3,
                            planner_key_claude, planner_key_openai)
        result = await llm.ainvoke([HumanMessage(content=plan_prompt)])
        text   = _ai_msg_text(result)
        match  = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            raise ValueError("No JSON array in planner response")
        plan = json.loads(match.group())
    except Exception as e:
        await broadcast({"type": "task_msg", "agent_id": None, "role": "error",
                         "content": f"Auto-plan failed ({e}). Running all AI-enabled agents.",
                         "ts": time.time()})
        capable = [
            aid for aid, a in env_agents.items()
            if a.ai_config.get("api_key_claude") or os.getenv("ANTHROPIC_API_KEY", "")
            or a.ai_config.get("api_key_openai") or os.getenv("OPENAI_API_KEY", "")
        ]
        if not capable:
            return
        await run_task(capable, task, env_agents, env_objects_snapshot, broadcast, move_agent)
        return

    if not plan:
        await broadcast({"type": "task_msg", "agent_id": None, "role": "error",
                         "content": "Planner returned an empty plan.", "ts": time.time()})
        return

    # Show the plan — list which agents were selected and why
    total    = len(env_agents)
    selected = len(plan)
    skipped  = [aid for aid in env_agents if aid not in {p["agent_id"] for p in plan}]
    lines    = [f"{p['agent_id']} ({env_agents[p['agent_id']].name if p['agent_id'] in env_agents else '?'}): {p['subtask'][:80]}"
                for p in plan]
    skip_note = f"  (skipped: {', '.join(skipped)})" if skipped else ""
    summary = f"{selected}/{total} agents selected{skip_note}\n" + "\n".join(lines)
    await broadcast({"type": "task_plan", "content": summary, "ts": time.time()})

    planned_ids = [p["agent_id"] for p in plan]
    home = {aid: (env_agents[aid].x, env_agents[aid].y)
            for aid in planned_ids if aid in env_agents}

    await broadcast({"type": "task_start",
                     "agents": planned_ids,
                     "task": task, "ts": time.time()})

    inter_agent_messages: Dict[str, List[str]] = {}

    # Sequential pipeline: each agent works, then returns home and passes context to next
    prior_context = ""
    for assignment in plan:
        aid     = assignment.get("agent_id", "")
        subtask = assignment.get("subtask", task)
        agent   = env_agents.get(aid)
        if not agent:
            continue

        agent_dict = agent.to_dict()
        agent_dict["ai_config"]["api_key_claude"] = agent.ai_config.get("api_key_claude", "")
        agent_dict["ai_config"]["api_key_openai"] = agent.ai_config.get("api_key_openai", "")
        agent_dict["mcp_servers"] = agent.mcp_servers

        move_to_loc = _make_move_to_location(aid, env_objects_snapshot, move_agent, env_agents)
        await broadcast({"type": "task_agent_start", "agent_id": aid, "ts": time.time()})

        result = await run_agent_task(
            agent_dict, subtask, prior_context, broadcast, inter_agent_messages,
            move_to_location=move_to_loc,
        )

        # Agent finished — reset state and walk home immediately
        agent.state = "idle"
        agent.target_x = None
        agent.target_y = None
        agent.interaction_target = None
        if aid in home:
            await move_agent(aid, home[aid][0], home[aid][1], None)

        # Pass result as context to the next agent
        if result:
            prior_context += f"\n\n[{agent.name} completed]:\n{result}"

    await broadcast({"type": "task_done", "ts": time.time()})
