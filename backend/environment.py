import time
from typing import Any, Dict, List, Optional

from agents import Agent
from config import (
    AGENT_COLORS, DEFAULT_AGENTS, DEFAULT_OBJECTS,
    SCENE_HEIGHT, SCENE_WIDTH,
)


class SceneObject:
    def __init__(self, obj_id: str, obj_type: str, x: float, y: float,
                 w: float, h: float, label: str = "",
                 task: str = "", task_desc: str = ""):
        self.id        = obj_id
        self.type      = obj_type
        self.x         = x
        self.y         = y
        self.w         = w
        self.h         = h
        self.label     = label or obj_id
        self.task      = task
        self.task_desc = task_desc
        self.agents_here: List[str] = []

    def approach_point(self, margin: float = 40.0):
        return self.x + self.w / 2, self.y - margin

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":          self.id,
            "type":        self.type,
            "x":           self.x,
            "y":           self.y,
            "w":           self.w,
            "h":           self.h,
            "label":       self.label,
            "task":        self.task,
            "task_desc":   self.task_desc,
            "agents_here": self.agents_here,
        }


class Environment:
    def __init__(self):
        self.width    = SCENE_WIDTH
        self.height   = SCENE_HEIGHT
        self.agents:  Dict[str, Agent]      = {}
        self.objects: Dict[str, SceneObject] = {}
        self.cmd_log: List[Dict[str, Any]]  = []
        self._color_idx  = 0
        self._last_tick  = time.time()
        self._reset_defaults()

    # ------------------------------------------------------------------
    def _reset_defaults(self):
        for d in DEFAULT_AGENTS:
            a = self._add_agent_raw(d["id"], d["name"], d["x"], d["y"], d["color"])
            if d.get("system_prompt"):
                a.ai_config["system_prompt"] = d["system_prompt"]
        for d in DEFAULT_OBJECTS:
            self._add_object_raw(
                d["id"], d["type"], d["x"], d["y"], d["w"], d["h"],
                d.get("label", ""), d.get("task", ""), d.get("task_desc", ""),
            )

    def _next_color(self) -> str:
        c = AGENT_COLORS[self._color_idx % len(AGENT_COLORS)]
        self._color_idx += 1
        return c

    def _add_agent_raw(self, aid, name, x, y, color) -> Agent:
        a = Agent(aid, name, x, y, color)
        self.agents[aid] = a
        return a

    def _add_object_raw(self, oid, otype, x, y, w, h, label,
                         task="", task_desc="") -> SceneObject:
        o = SceneObject(oid, otype, x, y, w, h, label, task, task_desc)
        self.objects[oid] = o
        return o

    # ------------------------------------------------------------------
    def add_agent(self, aid: str, name: str, x: float, y: float,
                  color: Optional[str] = None) -> Agent:
        return self._add_agent_raw(aid, name, x, y, color or self._next_color())

    def remove_agent(self, aid: str) -> bool:
        if aid in self.agents:
            del self.agents[aid]
            for obj in self.objects.values():
                obj.agents_here = [a for a in obj.agents_here if a != aid]
            return True
        return False

    def add_object(self, oid: str, otype: str, x: float, y: float,
                   w: float = 80, h: float = 60, label: str = "",
                   task: str = "", task_desc: str = "") -> SceneObject:
        return self._add_object_raw(oid, otype, x, y, w, h, label, task, task_desc)

    def remove_object(self, oid: str) -> bool:
        if oid in self.objects:
            del self.objects[oid]
            return True
        return False

    def reset(self):
        self.agents.clear()
        self.objects.clear()
        self.cmd_log.clear()
        self._color_idx = 0
        self._last_tick = time.time()
        self._reset_defaults()

    # ------------------------------------------------------------------
    def tick(self) -> None:
        now = time.time()
        dt  = min(now - self._last_tick, 0.1)
        self._last_tick = now
        for agent in self.agents.values():
            arrived = agent.update(dt)
            if arrived and agent.interaction_target:
                oid = agent.interaction_target
                if oid in self.objects and agent.id not in self.objects[oid].agents_here:
                    self.objects[oid].agents_here.append(agent.id)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "width":   self.width,
            "height":  self.height,
            "agents":  [a.to_dict() for a in self.agents.values()],
            "objects": [o.to_dict() for o in self.objects.values()],
            "cmd_log": self.cmd_log[-60:],
        }

    def log_cmd(self, command: str, result: str, success: bool):
        self.cmd_log.append({"ts": round(time.time(), 3), "cmd": command,
                              "result": result, "ok": success})
        if len(self.cmd_log) > 200:
            self.cmd_log = self.cmd_log[-200:]
