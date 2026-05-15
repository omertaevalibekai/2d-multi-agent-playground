import math
import time
from typing import Any, Dict, List, Optional

from config import AGENT_SPEED, ARRIVE_THRESHOLD


class Agent:
    def __init__(self, agent_id: str, name: str, x: float, y: float, color: str = "#6366f1"):
        self.id    = agent_id
        self.name  = name
        self.x     = x
        self.y     = y
        self.color = color
        self.speed = float(AGENT_SPEED)

        self.target_x: Optional[float] = None
        self.target_y: Optional[float] = None
        self.state = "idle"
        self.interaction_target: Optional[str] = None

        self.current_activity: str = ""

        self.history: List[Dict[str, Any]] = []
        self.chat_history: List[Dict[str, str]] = []   # {role, content}
        self.created_at = time.time()

        # AI configuration
        self.ai_config: Dict[str, Any] = {
            "provider":       "claude",
            "model":          "claude-haiku-4-5-20251001",
            "system_prompt":  "",
            "temperature":    0.7,
            "api_key_claude": "",
            "api_key_openai": "",
            "enabled_tools":  ["web_search", "read_url", "send_message_to_agent"],
        }

        # MCP servers: [{id, name, url, description, active}]
        self.mcp_servers: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    def move_to(self, x: float, y: float) -> None:
        self.target_x = float(x)
        self.target_y = float(y)
        self.state    = "moving"
        self.interaction_target = None
        self._log("move", f"-> ({x:.0f}, {y:.0f})")

    def stop(self) -> None:
        self.target_x = None
        self.target_y = None
        self.state    = "idle"
        self._log("stop", "stopped")

    def interact(self, obj_id: str, near_x: float, near_y: float) -> None:
        self.interaction_target = obj_id
        self.move_to(near_x, near_y)
        self.state = "moving"
        self._log("interact", f"-> {obj_id}")

    # ------------------------------------------------------------------
    def update(self, dt: float) -> bool:
        if self.state != "moving" or self.target_x is None:
            return False
        dx   = self.target_x - self.x
        dy   = self.target_y - self.y
        dist = math.hypot(dx, dy)
        if dist <= ARRIVE_THRESHOLD:
            self.x, self.y = self.target_x, self.target_y
            self.target_x  = self.target_y = None
            self.state     = "interacting" if self.interaction_target else "idle"
            return True
        step = min(self.speed * dt, dist)
        self.x += dx / dist * step
        self.y += dy / dist * step
        return False

    # ------------------------------------------------------------------
    def _log(self, action: str, detail: str) -> None:
        self.history.append({"ts": round(time.time(), 3), "action": action, "detail": detail})
        if len(self.history) > 50:
            self.history = self.history[-50:]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":                   self.id,
            "name":                 self.name,
            "x":                    round(self.x, 2),
            "y":                    round(self.y, 2),
            "target_x":             self.target_x,
            "target_y":             self.target_y,
            "color":                self.color,
            "speed":                self.speed,
            "state":                self.state,
            "interaction_target":   self.interaction_target,
            "current_activity":     self.current_activity,
            "history":              self.history[-10:],
            "ai_config":            {
                k: v for k, v in self.ai_config.items()
                if k not in ("api_key_claude", "api_key_openai")   # never expose keys
            },
            "ai_config_has_key_claude": bool(self.ai_config.get("api_key_claude")),
            "ai_config_has_key_openai": bool(self.ai_config.get("api_key_openai")),
            "mcp_servers":          self.mcp_servers,
            "chat_history":         self.chat_history[-30:],
        }
