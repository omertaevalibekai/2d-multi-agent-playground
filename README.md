# Agent Simulator

Interactive 2-D multi-agent simulator with a real-time web interface.

## Quick Start

```bash
cd playground
pip install -r requirements.txt
python backend/main.py
```

The browser opens automatically at **http://localhost:8000**.

## Commands

| Command | Description |
|---|---|
| `agent1 move 400 300` | Move agent to coordinates |
| `agent1 stop` | Stop agent |
| `agent1 interact table1` | Walk to and interact with object |
| `agent1 speed 200` | Set speed (10–600) |
| `agent1 color #ff6600` | Change color |
| `agent1 rename Neo` | Rename agent |
| `agent1 delete` | Remove agent |
| `all move 400 300` | Move **all** agents |
| `all stop` | Stop all agents |
| `status` | Show agent states |
| `history [n]` | Show last n commands |
| `reset` | Restore defaults |
| `create agent agent4 Delta 200 200` | Create new agent |
| `place table desk1 500 200` | Place an object |
| `remove desk1` | Remove object |
| `help` | Show all commands |

## UI Controls

- **Click** on the scene (select tool) with an agent selected → moves that agent
- **Drag tool** → drag objects to reposition them
- **⏺ Record** → record a sequence of commands
- **▶ Play** → replay the recording at chosen speed
- **Tab** in the command input → autocomplete
- **↑/↓** in the command input → navigate command history
- **/** → focus command input
- **Esc** → deselect agent
- **Ctrl+L** → clear log

## Smart Mode (AI)

Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in your environment and enable
the **Smart** toggle. Natural-language input is then translated to commands:

> *"send everyone to the center"* → `all move 400 300`

## Project Structure

```
playground/
├── backend/
│   ├── main.py              FastAPI server + WebSocket sim loop
│   ├── agents.py            Agent class (movement, state)
│   ├── environment.py       Scene management (agents + objects)
│   ├── command_processor.py Command parser & dispatcher
│   ├── api_integration.py   Claude / OpenAI smart-command bridge
│   └── config.py            Constants and defaults
├── frontend/
│   ├── index.html           App shell
│   ├── styles.css           Dark-theme design system
│   └── script.js            Canvas renderer + WS client + UI
└── requirements.txt
```
