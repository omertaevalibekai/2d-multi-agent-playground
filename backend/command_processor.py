"""
Command grammar
---------------
<agent_id>  <verb>  [args...]
all         <verb>  [args...]
<standalone_verb>   [args...]

Verbs: move interact stop speed color rename delete
Standalone: status history reset help create place remove
"""
import time
from typing import Any, Dict, List

from environment import Environment


class CommandResult:
    def __init__(self, ok: bool, msg: str):
        self.ok = ok
        self.msg = msg

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "message": self.msg}


class CommandProcessor:
    STANDALONE = {"status", "history", "reset", "help", "create", "place", "remove"}

    def __init__(self, env: Environment):
        self.env = env

    # ------------------------------------------------------------------ public
    def run(self, raw: str) -> CommandResult:
        raw = raw.strip()
        if not raw:
            return CommandResult(False, "Empty command")

        parts = raw.split()
        verb_or_target = parts[0].lower()
        rest = parts[1:]

        if verb_or_target in self.STANDALONE:
            result = self._dispatch_standalone(verb_or_target, rest)
        elif verb_or_target == "all":
            result = self._dispatch_all(rest)
        elif verb_or_target in self.env.agents:
            result = self._dispatch_agent(verb_or_target, rest)
        else:
            result = CommandResult(False,
                f"Unknown target '{verb_or_target}'. Type help for usage.")

        self.env.log_cmd(raw, result.msg, result.ok)
        return result

    # ------------------------------------------------------------------ standalone
    def _dispatch_standalone(self, verb: str, args: List[str]) -> CommandResult:
        handlers = {
            "status":  self._cmd_status,
            "history": self._cmd_history,
            "reset":   self._cmd_reset,
            "help":    self._cmd_help,
            "create":  self._cmd_create,
            "place":   self._cmd_place,
            "remove":  self._cmd_remove,
        }
        return handlers[verb](args)

    def _dispatch_all(self, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(False, "all requires a verb (e.g. all move 400 300)")
        verb = args[0].lower()
        vargs = args[1:]
        results = []
        ok = True
        for aid in list(self.env.agents.keys()):
            r = self._dispatch_agent(aid, [verb] + vargs)
            results.append(r.msg)
            if not r.ok:
                ok = False
        return CommandResult(ok, " | ".join(results) if results else "No agents")

    def _dispatch_agent(self, aid: str, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(False, f"No verb for {aid}")
        verb = args[0].lower()
        vargs = args[1:]
        verbs = {
            "move":     self._av_move,
            "stop":     self._av_stop,
            "interact": self._av_interact,
            "speed":    self._av_speed,
            "color":    self._av_color,
            "rename":   self._av_rename,
            "delete":   self._av_delete,
        }
        if verb not in verbs:
            return CommandResult(False, f"Unknown verb '{verb}'. Type help.")
        return verbs[verb](aid, vargs)

    # ------------------------------------------------------------------ agent verbs
    def _av_move(self, aid: str, args: List[str]) -> CommandResult:
        if len(args) < 2:
            return CommandResult(False, f"Usage: {aid} move <x> <y>")
        try:
            x = max(0.0, min(float(args[0]), self.env.width))
            y = max(0.0, min(float(args[1]), self.env.height))
        except ValueError:
            return CommandResult(False, "Coordinates must be numbers")
        self.env.agents[aid].move_to(x, y)
        return CommandResult(True, f"{self.env.agents[aid].name} → ({x:.0f}, {y:.0f})")

    def _av_stop(self, aid: str, args: List[str]) -> CommandResult:
        self.env.agents[aid].stop()
        return CommandResult(True, f"{self.env.agents[aid].name} stopped")

    def _av_interact(self, aid: str, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(False, f"Usage: {aid} interact <object_id>")
        oid = args[0]
        if oid not in self.env.objects:
            return CommandResult(False, f"Object '{oid}' not found")
        obj = self.env.objects[oid]
        ax, ay = obj.approach_point()
        ax = max(0.0, min(ax, self.env.width))
        ay = max(0.0, min(ay, self.env.height))
        self.env.agents[aid].interact(oid, ax, ay)
        return CommandResult(True, f"{self.env.agents[aid].name} → {obj.label}")

    def _av_speed(self, aid: str, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(False, f"Usage: {aid} speed <value>")
        try:
            s = float(args[0])
            self.env.agents[aid].speed = max(10.0, min(s, 600.0))
            return CommandResult(True, f"{self.env.agents[aid].name} speed={s:.0f}")
        except ValueError:
            return CommandResult(False, "Speed must be a number")

    def _av_color(self, aid: str, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(False, f"Usage: {aid} color <#hex>")
        c = args[0] if args[0].startswith("#") else "#" + args[0]
        self.env.agents[aid].color = c
        return CommandResult(True, f"{self.env.agents[aid].name} color={c}")

    def _av_rename(self, aid: str, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(False, f"Usage: {aid} rename <new_name>")
        new = " ".join(args)
        old = self.env.agents[aid].name
        self.env.agents[aid].name = new
        return CommandResult(True, f"{old} → {new}")

    def _av_delete(self, aid: str, args: List[str]) -> CommandResult:
        name = self.env.agents[aid].name
        self.env.remove_agent(aid)
        return CommandResult(True, f"Deleted {name}")

    # ------------------------------------------------------------------ standalone handlers
    def _cmd_status(self, args: List[str]) -> CommandResult:
        if not self.env.agents:
            return CommandResult(True, "No agents in scene")
        lines = []
        for a in self.env.agents.values():
            tgt = f" → ({a.target_x:.0f},{a.target_y:.0f})" if a.target_x is not None else ""
            lines.append(f"[{a.id}] {a.name}  ({a.x:.0f},{a.y:.0f})  {a.state}{tgt}")
        return CommandResult(True, "\n".join(lines))

    def _cmd_history(self, args: List[str]) -> CommandResult:
        if not self.env.cmd_log:
            return CommandResult(True, "No history")
        n = int(args[0]) if args and args[0].isdigit() else 20
        lines = []
        for e in self.env.cmd_log[-n:]:
            t = time.strftime("%H:%M:%S", time.localtime(e["ts"]))
            mark = "✓" if e["ok"] else "✗"
            lines.append(f"[{t}] {mark} {e['cmd']}")
        return CommandResult(True, "\n".join(lines))

    def _cmd_reset(self, args: List[str]) -> CommandResult:
        self.env.reset()
        return CommandResult(True, "Scene reset to defaults")

    def _cmd_create(self, args: List[str]) -> CommandResult:
        # create agent <id> <name> <x> <y>
        if len(args) < 5 or args[0] != "agent":
            return CommandResult(False, "Usage: create agent <id> <name> <x> <y>")
        aid, name = args[1], args[2]
        if aid in self.env.agents:
            return CommandResult(False, f"Agent '{aid}' already exists")
        try:
            x, y = float(args[3]), float(args[4])
        except ValueError:
            return CommandResult(False, "Coordinates must be numbers")
        self.env.add_agent(aid, name, x, y)
        return CommandResult(True, f"Created {name} ({aid}) at ({x:.0f},{y:.0f})")

    def _cmd_place(self, args: List[str]) -> CommandResult:
        # place <type> <id> <x> <y> [w] [h]
        if len(args) < 4:
            return CommandResult(False, "Usage: place <type> <id> <x> <y> [width] [height]")
        otype, oid = args[0], args[1]
        try:
            x, y = float(args[2]), float(args[3])
            w = float(args[4]) if len(args) > 4 else 80.0
            h = float(args[5]) if len(args) > 5 else 60.0
        except ValueError:
            return CommandResult(False, "Coordinates must be numbers")
        self.env.add_object(oid, otype, x, y, w, h, oid)
        return CommandResult(True, f"Placed {otype} '{oid}' at ({x:.0f},{y:.0f})")

    def _cmd_remove(self, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult(False, "Usage: remove <object_id>")
        oid = args[0]
        if self.env.remove_object(oid):
            return CommandResult(True, f"Removed '{oid}'")
        return CommandResult(False, f"Object '{oid}' not found")

    def _cmd_help(self, args: List[str]) -> CommandResult:
        text = """
AGENT COMMANDS
  <id> move <x> <y>          Move agent to coordinates
  <id> stop                  Stop agent
  <id> interact <object_id>  Walk to and interact with object
  <id> speed <value>         Set movement speed (10–600)
  <id> color <#hex>          Change agent color
  <id> rename <new_name>     Rename agent
  <id> delete                Remove agent from scene

GROUP COMMANDS
  all move <x> <y>           Move all agents
  all stop                   Stop all agents

SCENE COMMANDS
  status                     List all agents and their state
  history [n]                Show last n commands (default 20)
  reset                      Restore default scene
  create agent <id> <name> <x> <y>
  place <type> <id> <x> <y> [w] [h]   Types: table chair wall computer door
  remove <object_id>
  help                       Show this message
""".strip()
        return CommandResult(True, text)
