SCENE_WIDTH = 800
SCENE_HEIGHT = 600

AGENT_SPEED = 120
AGENT_RADIUS = 16
MAX_AGENTS = 20

AGENT_COLORS = [
    "#6366f1", "#22c55e", "#f59e0b", "#ef4444",
    "#8b5cf6", "#06b6d4", "#ec4899", "#14b8a6",
    "#f97316", "#84cc16",
]

DEFAULT_AGENTS = [
    {"id": "agent1", "name": "Alpha",  "x": 120, "y": 120, "color": "#6366f1"},
    {"id": "agent2", "name": "Beta",   "x": 220, "y": 200, "color": "#22c55e"},
    {"id": "agent3", "name": "Gamma",  "x": 160, "y": 320, "color": "#f59e0b"},
]

DEFAULT_OBJECTS = [
    {
        "id": "table1", "type": "table",
        "x": 380, "y": 160, "w": 100, "h": 70, "label": "Table 1",
        "task": "Research",
        "task_desc": "Research & Analysis — find information, summarise sources, answer questions",
    },
    {
        "id": "table2", "type": "table",
        "x": 560, "y": 300, "w": 100, "h": 70, "label": "Table 2",
        "task": "Writing",
        "task_desc": "Writing & Documentation — draft texts, create reports, edit content",
    },
    {
        "id": "pc1", "type": "computer",
        "x": 390, "y": 420, "w": 80,  "h": 55,  "label": "PC 1",
        "task": "Code",
        "task_desc": "Code Development — write, review and debug code",
    },
    {
        "id": "wall1", "type": "wall",
        "x": 320, "y": 80,  "w": 12,  "h": 440, "label": "Wall",
        "task": "", "task_desc": "",
    },
]

# Available AI models exposed to the frontend
AI_MODELS = {
    "claude": [
        {"id": "claude-opus-4-7",           "name": "Claude Opus 4.7"},
        {"id": "claude-sonnet-4-6",         "name": "Claude Sonnet 4.6"},
        {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5"},
    ],
    "openai": [
        {"id": "gpt-4o",       "name": "GPT-4o"},
        {"id": "gpt-4o-mini",  "name": "GPT-4o mini"},
        {"id": "gpt-4-turbo",  "name": "GPT-4 Turbo"},
    ],
}

API_HOST = "0.0.0.0"
API_PORT = 8000

SIM_TICK_RATE = 30
ARRIVE_THRESHOLD = 3

MCP_PRESETS = [
    {"id": "gmail",      "name": "Gmail",        "url": "mcp://gmail",      "description": "Read and send emails via Gmail API"},
    {"id": "github",     "name": "GitHub",        "url": "mcp://github",     "description": "Manage repos, PRs, and issues on GitHub"},
    {"id": "cursor",     "name": "Cursor",        "url": "mcp://cursor",     "description": "IDE integration — read and write files in Cursor"},
    {"id": "slack",      "name": "Slack",         "url": "mcp://slack",      "description": "Send and read Slack messages"},
    {"id": "notion",     "name": "Notion",        "url": "mcp://notion",     "description": "Read and write Notion pages and databases"},
    {"id": "filesystem", "name": "Filesystem",    "url": "mcp://filesystem", "description": "Read and write local files"},
    {"id": "postgres",   "name": "PostgreSQL",    "url": "mcp://postgres",   "description": "Query PostgreSQL databases"},
    {"id": "tavily",     "name": "Tavily Search", "url": "mcp://tavily",     "description": "Real-time web search via Tavily API"},
    {"id": "browser",    "name": "Browser",       "url": "mcp://browser",    "description": "Control a web browser for automation"},
    {"id": "gcalendar",  "name": "Google Cal",    "url": "mcp://gcalendar",  "description": "Read and create Google Calendar events"},
]

AGENT_TOOLS = [
    {"id": "web_search",            "name": "Web Search",      "description": "Search the internet for information"},
    {"id": "read_url",              "name": "Read URL",         "description": "Fetch and read any web page"},
    {"id": "send_message_to_agent", "name": "Agent Messaging", "description": "Send data to other agents for collaboration"},
]
