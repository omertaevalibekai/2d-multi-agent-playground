"""
Optional AI integration — converts natural-language input into simulator commands.
Enabled when ANTHROPIC_API_KEY or OPENAI_API_KEY is set in the environment.
"""
import os
from typing import Optional

import httpx


class AIIntegration:
    def __init__(self):
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.openai_key    = os.environ.get("OPENAI_API_KEY", "")
        self.enabled       = bool(self.anthropic_key or self.openai_key)

    # ------------------------------------------------------------------
    async def interpret(self, user_input: str, scene: dict) -> Optional[str]:
        """Return one or more simulator command lines, or None on failure."""
        if not self.enabled:
            return None

        agents  = [f"{a['id']}({a['name']}) @({a['x']:.0f},{a['y']:.0f})"
                   for a in scene.get("agents", [])]
        objects = [f"{o['id']}({o['type']}) @({o['x']:.0f},{o['y']:.0f})"
                   for o in scene.get("objects", [])]

        system = (
            "You are a command translator for a 2-D agent simulator. "
            "Convert natural-language instructions into one or more simulator commands, "
            "one per line, with NO extra explanation.\n\n"
            "Available commands:\n"
            "  <agent_id> move <x> <y>\n"
            "  <agent_id> stop\n"
            "  <agent_id> interact <object_id>\n"
            "  <agent_id> speed <value>\n"
            "  all move <x> <y>\n"
            "  all stop\n"
            "  status\n"
            "  reset\n\n"
            f"Scene ({scene.get('width',800)}x{scene.get('height',600)}):\n"
            f"  Agents:  {', '.join(agents)}\n"
            f"  Objects: {', '.join(objects)}"
        )

        prompt = user_input.strip()
        if self.anthropic_key:
            return await self._claude(system, prompt)
        return await self._openai(system, prompt)

    # ------------------------------------------------------------------
    async def _claude(self, system: str, prompt: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 200,
                        "system": system,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                return r.json()["content"][0]["text"].strip()
        except Exception as exc:
            print(f"[AI] Claude error: {exc}")
            return None

    async def _openai(self, system: str, prompt: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.openai_key}"},
                    json={
                        "model": "gpt-4o-mini",
                        "max_tokens": 200,
                        "messages": [
                            {"role": "system",  "content": system},
                            {"role": "user",    "content": prompt},
                        ],
                    },
                )
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            print(f"[AI] OpenAI error: {exc}")
            return None
