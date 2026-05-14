"""
LangChain tool definitions for the agent simulator.
All tools are synchronous — LangGraph runs them in a thread pool.
"""
import re
import httpx
from typing import Dict, List

from langchain_core.tools import tool


def _strip_html(html: str) -> str:
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>',  '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&[a-zA-Z]+;', '', text)
    return re.sub(r'\s+', ' ', text).strip()


@tool
def web_search(query: str) -> str:
    """Search the internet for current information, news, and facts.
    Returns real search results. Use this whenever you need to find information."""
    try:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=6):
                results.append(
                    f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}"
                )
        if results:
            return "\n\n---\n\n".join(results)
        return "No results found. Try a different search query."
    except Exception as e:
        return f"Search failed: {e}. Try read_url with a direct URL."


@tool
def read_url(url: str) -> str:
    """Fetch and read the full text content of a web page.
    Use this to get detailed information from a specific URL."""
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            r = client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AgentBot/1.0)"})
            r.raise_for_status()
            text = _strip_html(r.text)
            if len(text) > 6000:
                text = text[:6000] + "…"
            return text or "(empty page)"
    except Exception as e:
        return f"Could not read URL: {e}"


def make_send_message_tool(inter_agent_messages: Dict[str, List[str]]):
    """Factory: creates a send_message_to_agent tool bound to the current inter_agent_messages dict."""
    @tool
    def send_message_to_agent(target_agent_id: str, message: str) -> str:
        """Send a message or result to another agent so they can use it in their work.
        Use the agent's exact ID (e.g. 'agent2')."""
        inter_agent_messages.setdefault(target_agent_id, []).append(message)
        return f"Message queued for agent '{target_agent_id}'."
    return send_message_to_agent


# Base tool registry (tools that don't need per-run state)
BASE_TOOL_MAP = {
    "web_search": web_search,
    "read_url":   read_url,
}
