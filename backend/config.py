SCENE_WIDTH = 800
SCENE_HEIGHT = 600

AGENT_SPEED = 120
AGENT_RADIUS = 16
MAX_AGENTS = 20

AGENT_COLORS = [
    "#6366f1", "#22c55e", "#f59e0b", "#ef4444",
    "#8b5cf6", "#06b6d4", "#ec4899", "#14b8a6",
    "#f97316", "#84cc16", "#a855f7",
]

# ── Startup War Room preset ─────────────────────────────────────────────
DEFAULT_AGENTS = [
    {
        "id": "ceo", "name": "CEO", "x": 65, "y": 100, "color": "#6366f1",
        "system_prompt": "You are the CEO of a fast-growing AI startup. Make strategic decisions, align the team on vision, and unblock execution. Be decisive and concise.",
    },
    {
        "id": "cto", "name": "CTO", "x": 175, "y": 100, "color": "#8b5cf6",
        "system_prompt": "You are the CTO. Own the technical architecture, oversee engineering, and make technology decisions that scale. Prioritise AI infrastructure.",
    },
    {
        "id": "ai_eng", "name": "AI Engineer", "x": 285, "y": 100, "color": "#06b6d4",
        "system_prompt": "You are the AI Lead Engineer. Design and implement ML systems, fine-tune models, and advise on AI architecture. Bridge research and production.",
    },
    {
        "id": "cmo", "name": "CMO", "x": 488, "y": 100, "color": "#ec4899",
        "system_prompt": "You are the CMO. Drive go-to-market strategy, brand positioning, and growth campaigns. Focus on pipeline and market awareness.",
    },
    {
        "id": "sales", "name": "Head of Sales", "x": 603, "y": 100, "color": "#22c55e",
        "system_prompt": "You are the Head of Sales. Close deals, manage the pipeline, and grow enterprise accounts. Be metrics-driven and customer-focused.",
    },
    {
        "id": "finance", "name": "Head of Finance", "x": 600, "y": 175, "color": "#f59e0b",
        "system_prompt": "You are the Head of Finance. Manage runway, forecasts, and budgets. Flag risks, model scenarios, and ensure healthy unit economics.",
    },
    {
        "id": "legal", "name": "Legal", "x": 600, "y": 285, "color": "#ef4444",
        "system_prompt": "You are the company's legal counsel. Review contracts, assess regulatory risk, and ensure compliance. Be thorough but pragmatic.",
    },
    {
        "id": "pr", "name": "PR", "x": 600, "y": 395, "color": "#84cc16",
        "system_prompt": "You are the PR lead. Manage media relationships, craft narratives, and handle communications. Protect and grow the brand's public image.",
    },
    {
        "id": "analyst", "name": "Data Analyst", "x": 195, "y": 535, "color": "#14b8a6",
        "system_prompt": "You are the Data Analyst. Surface insights from metrics, build dashboards, and support data-driven decisions across the company.",
    },
    {
        "id": "product", "name": "Product", "x": 335, "y": 535, "color": "#f97316",
        "system_prompt": "You are the Head of Product. Own the roadmap, write specs, and align engineering with customer needs. Balance speed with quality.",
    },
    {
        "id": "strategy", "name": "Strategy", "x": 475, "y": 535, "color": "#a855f7",
        "system_prompt": "You are the Head of Strategy. Identify growth opportunities, analyse competition, and shape long-term direction. Think 3–5 years ahead.",
    },
]

DEFAULT_OBJECTS = [
    # ── Top workstations ──────────────────────────────────────────────
    {"id": "desk_ceo",     "type": "computer", "x": 15,  "y": 15, "w": 100, "h": 65,
     "label": "CEO Station",  "task": "Leadership", "task_desc": "Executive decisions and company direction"},
    {"id": "desk_tech",    "type": "computer", "x": 125, "y": 15, "w": 100, "h": 65,
     "label": "Tech Hub",     "task": "Code",       "task_desc": "Engineering architecture and development"},
    {"id": "desk_ai",      "type": "computer", "x": 235, "y": 15, "w": 100, "h": 65,
     "label": "AI Lab",       "task": "Research",   "task_desc": "AI model development and experimentation"},
    {"id": "desk_mkt",     "type": "table",    "x": 435, "y": 15, "w": 105, "h": 65,
     "label": "Marketing",    "task": "Marketing",  "task_desc": "Campaign planning and go-to-market strategy"},
    {"id": "desk_sales",   "type": "table",    "x": 550, "y": 15, "w": 105, "h": 65,
     "label": "Sales Floor",  "task": "Sales",      "task_desc": "Pipeline management and deal closing"},
    # ── Central war room table ────────────────────────────────────────
    {"id": "war_room",     "type": "table",    "x": 140, "y": 135, "w": 400, "h": 210,
     "label": "War Room",     "task": "Strategy",   "task_desc": "High-level planning, OKRs and cross-team alignment"},
    # ── Right-side desks ──────────────────────────────────────────────
    {"id": "desk_fin",     "type": "computer", "x": 670, "y": 130, "w": 115, "h": 65,
     "label": "Finance",      "task": "Finance",    "task_desc": "Budget, runway and financial modelling"},
    {"id": "desk_legal",   "type": "table",    "x": 670, "y": 245, "w": 115, "h": 65,
     "label": "Legal",        "task": "Legal",      "task_desc": "Contracts, compliance and risk assessment"},
    {"id": "desk_pr",      "type": "table",    "x": 670, "y": 360, "w": 115, "h": 65,
     "label": "PR & Comms",   "task": "PR",         "task_desc": "Media relations and brand communications"},
    # ── Bottom workstations ───────────────────────────────────────────
    {"id": "desk_data",    "type": "computer", "x": 140, "y": 445, "w": 120, "h": 65,
     "label": "Data Station", "task": "Analysis",   "task_desc": "Metrics, dashboards and business intelligence"},
    {"id": "desk_product", "type": "table",    "x": 280, "y": 445, "w": 120, "h": 65,
     "label": "Product",      "task": "Product",    "task_desc": "Roadmap, specs and customer feedback"},
    {"id": "desk_strat",   "type": "table",    "x": 420, "y": 445, "w": 120, "h": 65,
     "label": "Strategy",     "task": "Strategy",   "task_desc": "Competitive analysis and long-term planning"},
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
