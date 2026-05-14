"""Per-agent AI chat — supports Claude and OpenAI."""
import os
import time
from typing import Any, Dict, List

import httpx


async def chat(
    agent: dict,
    message: str,
    history: List[Dict[str, str]],
    scene_context: str = "",
) -> Dict[str, Any]:
    cfg      = agent.get("ai_config", {})
    provider = cfg.get("provider", "claude")
    model    = cfg.get("model",    "claude-haiku-4-5-20251001")
    temp     = float(cfg.get("temperature", 0.7))
    sys_p    = cfg.get("system_prompt", "").strip()

    if not sys_p:
        sys_p = (
            f"You are {agent['name']}, an AI agent in a 2-D simulation.\n"
            f"Position: ({agent['x']:.0f}, {agent['y']:.0f})  State: {agent['state']}.\n"
            "Be helpful and concise."
        )

    if scene_context:
        sys_p += f"\n\n{scene_context}"

    active_mcps = [m for m in agent.get("mcp_servers", []) if m.get("active", True)]
    if active_mcps:
        lines = [f"- {m['name']}: {m.get('description', '')}" for m in active_mcps]
        sys_p += "\n\nAvailable tools/services:\n" + "\n".join(lines)

    msgs = [{"role": m["role"], "content": m["content"]} for m in history]
    msgs.append({"role": "user", "content": message})

    key_c = cfg.get("api_key_claude", "") or os.environ.get("ANTHROPIC_API_KEY", "")
    key_o = cfg.get("api_key_openai", "") or os.environ.get("OPENAI_API_KEY", "")

    if provider == "claude":
        if not key_c:
            return {"ok": False, "error": "ANTHROPIC_API_KEY not set for this agent"}
        return await _claude(key_c, model, sys_p, msgs, temp)
    else:
        if not key_o:
            return {"ok": False, "error": "OPENAI_API_KEY not set for this agent"}
        return await _openai(key_o, model, sys_p, msgs, temp)


async def _claude(key: str, model: str, system: str,
                  messages: list, temperature: float) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":           key,
                    "anthropic-version":   "2023-06-01",
                    "content-type":        "application/json",
                },
                json={
                    "model":       model,
                    "max_tokens":  1024,
                    "temperature": temperature,
                    "system":      system,
                    "messages":    messages,
                },
            )
        data = r.json()
        if r.status_code != 200:
            return {"ok": False, "error": data.get("error", {}).get("message", str(data))}
        return {"ok": True, "response": data["content"][0]["text"],
                "model": model, "provider": "claude"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def _openai(key: str, model: str, system: str,
                  messages: list, temperature: float) -> Dict[str, Any]:
    try:
        all_msgs = [{"role": "system", "content": system}] + messages
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model":       model,
                    "messages":    all_msgs,
                    "max_tokens":  1024,
                    "temperature": temperature,
                },
            )
        data = r.json()
        if r.status_code != 200:
            return {"ok": False, "error": data.get("error", {}).get("message", str(data))}
        return {"ok": True, "response": data["choices"][0]["message"]["content"],
                "model": model, "provider": "openai"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
