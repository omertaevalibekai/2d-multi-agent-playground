import asyncio
import io
import json
import sys
import time
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Set

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import ai_chat
from api_integration import AIIntegration
from command_processor import CommandProcessor
from config import AI_MODELS, API_HOST, API_PORT, MCP_PRESETS, AGENT_TOOLS, SIM_TICK_RATE
from environment import Environment
from orchestrator import auto_plan_task, run_task as orchestrate_task

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
env     = Environment()
proc    = CommandProcessor(env)
ai      = AIIntegration()
clients: Set[WebSocket] = set()

FRONTEND = Path(__file__).parent.parent / "frontend"

# ---------------------------------------------------------------------------
async def broadcast_raw(text: str):
    dead: Set[WebSocket] = set()
    for ws in list(clients):
        try:
            await ws.send_text(text)
        except Exception:
            dead.add(ws)
    clients.difference_update(dead)

async def broadcast():
    if not clients:
        return
    await broadcast_raw(json.dumps({"type": "state", "data": env.snapshot()}))


async def sim_loop():
    interval = 1.0 / SIM_TICK_RATE
    while True:
        env.tick()
        await broadcast()
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(application: FastAPI):
    asyncio.create_task(sim_loop())
    url = f"http://localhost:{API_PORT}"
    print(f"\n{'='*52}")
    print(f"  Agent Simulator  ->  {url}")
    print(f"  AI smart mode    ->  {'enabled' if ai.enabled else 'disabled'}")
    print(f"{'='*52}\n")

    async def _open():
        await asyncio.sleep(1.2)
        webbrowser.open(url)
    asyncio.create_task(_open())
    yield


app = FastAPI(title="Agent Simulator", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")

# ---------------------------------------------------------------------------
class CmdRequest(BaseModel):
    command: str
    smart:   bool = False

# ---------------------------------------------------------------------------  pages
@app.get("/")
async def root():
    return FileResponse(str(FRONTEND / "index.html"))

# ---------------------------------------------------------------------------  command
@app.post("/api/command")
async def cmd(req: CmdRequest):
    command = req.command.strip()
    if not command:
        raise HTTPException(400, "Empty command")

    if req.smart and ai.enabled:
        interpreted = await ai.interpret(command, env.snapshot())
        if interpreted:
            results = []
            for line in interpreted.splitlines():
                line = line.strip()
                if line:
                    r = proc.run(line)
                    results.append(r.to_dict())
            await broadcast()
            return {"ok": True, "smart": True,
                    "interpreted": interpreted, "results": results}

    result = proc.run(command)
    await broadcast()
    return result.to_dict()

# ---------------------------------------------------------------------------  state
@app.get("/api/state")
async def get_state():
    return env.snapshot()

@app.get("/api/models")
async def get_models():
    return AI_MODELS

@app.get("/api/config")
async def get_config():
    return {"mcp_presets": MCP_PRESETS, "agent_tools": AGENT_TOOLS, "ai_models": AI_MODELS}

# ---------------------------------------------------------------------------  task
class TaskRequest(BaseModel):
    agents:  list
    message: str
    auto:    bool = False

@app.post("/api/task")
async def run_task_endpoint(req: TaskRequest):
    if not req.message.strip():
        raise HTTPException(400, "message required")
    if not req.auto:
        if not req.agents:
            raise HTTPException(400, "agents required (or set auto=true)")
        for aid in req.agents:
            if aid not in env.agents:
                raise HTTPException(404, f"Agent '{aid}' not found")

    async def _move(aid: str, x: float, y: float, obj_id: str = None):
        if aid in env.agents:
            a = env.agents[aid]
            a.target_x = x
            a.target_y = y
            a.state    = "moving"
            a.interaction_target = obj_id

    async def _bc(msg: dict):
        await broadcast_raw(json.dumps(msg))

    objects_snap = {oid: o.to_dict() for oid, o in env.objects.items()}

    if req.auto:
        asyncio.create_task(
            auto_plan_task(req.message, env.agents, objects_snap, _bc, _move)
        )
        return {"ok": True, "agents": [], "auto": True}

    asyncio.create_task(
        orchestrate_task(req.agents, req.message, env.agents, objects_snap, _bc, _move)
    )
    return {"ok": True, "agents": req.agents}

# ---------------------------------------------------------------------------  agents CRUD
@app.post("/api/agents")
async def create_agent(body: dict):
    aid   = body.get("id",    f"agent{len(env.agents)+1}")
    name  = body.get("name",  f"Agent {len(env.agents)+1}")
    x     = float(body.get("x", 100))
    y     = float(body.get("y", 100))
    color = body.get("color")
    if aid in env.agents:
        raise HTTPException(400, f"Agent '{aid}' already exists")
    a = env.add_agent(aid, name, x, y, color)
    await broadcast()
    return a.to_dict()

@app.delete("/api/agents/{aid}")
async def delete_agent(aid: str):
    if not env.remove_agent(aid):
        raise HTTPException(404, f"Agent '{aid}' not found")
    await broadcast()
    return {"ok": True}

# ---------------------------------------------------------------------------  agent config
@app.put("/api/agents/{aid}/config")
async def update_agent_config(aid: str, body: dict):
    if aid not in env.agents:
        raise HTTPException(404, f"Agent '{aid}' not found")
    a = env.agents[aid]
    if "name"   in body: a.name  = body["name"]
    if "color"  in body: a.color = body["color"]
    if "speed"  in body: a.speed = max(10.0, min(float(body["speed"]), 600.0))
    if "x"      in body: a.x     = float(body["x"])
    if "y"      in body: a.y     = float(body["y"])
    if "ai_config" in body:
        a.ai_config.update(body["ai_config"])
    if "mcp_servers" in body:
        a.mcp_servers = body["mcp_servers"]
    await broadcast()
    return a.to_dict()

# ---------------------------------------------------------------------------  agent chat
@app.post("/api/agents/{aid}/chat")
async def agent_chat(aid: str, body: dict):
    if aid not in env.agents:
        raise HTTPException(404, f"Agent '{aid}' not found")
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(400, "message is required")

    history = body.get("history", [])
    agent   = env.agents[aid]

    # Task context when agent is interacting with an object
    scene_ctx = ""
    if agent.interaction_target and agent.interaction_target in env.objects:
        obj = env.objects[agent.interaction_target]
        if obj.task:
            scene_ctx = (
                f"You are currently working at: {obj.label}\n"
                f"Task: {obj.task} — {obj.task_desc}"
            )

    result = await ai_chat.chat(agent.to_dict(), message, history, scene_ctx)

    if result["ok"]:
        agent.chat_history.append({"role": "user",      "content": message,
                                    "ts": round(time.time(), 3)})
        agent.chat_history.append({"role": "assistant", "content": result["response"],
                                    "ts": round(time.time(), 3)})
        if len(agent.chat_history) > 60:
            agent.chat_history = agent.chat_history[-60:]

    return result

@app.delete("/api/agents/{aid}/chat")
async def clear_agent_chat(aid: str):
    if aid not in env.agents:
        raise HTTPException(404)
    env.agents[aid].chat_history = []
    return {"ok": True}

# ---------------------------------------------------------------------------  objects CRUD
@app.post("/api/objects")
async def create_object(body: dict):
    oid  = body.get("id",    f"obj{len(env.objects)+1}")
    typ  = body.get("type",  "table")
    x    = float(body.get("x", 300))
    y    = float(body.get("y", 300))
    w    = float(body.get("w", 80))
    h    = float(body.get("h", 60))
    lbl  = body.get("label", "")
    task = body.get("task",  "")
    tdsc = body.get("task_desc", "")
    o = env.add_object(oid, typ, x, y, w, h, lbl, task, tdsc)
    await broadcast()
    return o.to_dict()

@app.put("/api/objects/{oid}")
async def update_object(oid: str, body: dict):
    if oid not in env.objects:
        raise HTTPException(404, f"Object '{oid}' not found")
    obj = env.objects[oid]
    if "x"         in body: obj.x         = float(body["x"])
    if "y"         in body: obj.y         = float(body["y"])
    if "label"     in body: obj.label     = body["label"]
    if "task"      in body: obj.task      = body["task"]
    if "task_desc" in body: obj.task_desc = body["task_desc"]
    await broadcast()
    return obj.to_dict()

@app.delete("/api/objects/{oid}")
async def delete_object(oid: str):
    if not env.remove_object(oid):
        raise HTTPException(404, f"Object '{oid}' not found")
    await broadcast()
    return {"ok": True}

# ---------------------------------------------------------------------------  misc
@app.post("/api/reset")
async def reset():
    env.reset()
    await broadcast()
    return {"ok": True}

@app.get("/api/export")
async def export_history():
    return {
        "exported_at": time.time(),
        "command_log": env.cmd_log,
        "agents":      [a.to_dict() for a in env.agents.values()],
        "objects":     [o.to_dict() for o in env.objects.values()],
    }

# ---------------------------------------------------------------------------  WS
@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    await websocket.send_text(json.dumps({"type": "state", "data": env.snapshot()}))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(websocket)

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host=API_HOST, port=API_PORT,
                reload=False, log_level="warning")
