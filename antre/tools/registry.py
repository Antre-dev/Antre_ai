
from .system.get_time import get_time
from .web.search_web import search_web, browse_web

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current local time.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the internet for current information, news, "
                "documentation, facts, websites, or anything that may "
                "have changed recently."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The web search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browse_web",
            "description": (
                "Agent-style browser control with a persistent session. "
                "Actions: goto (navigate to a URL), click (click a CSS/XPath "
                "selector), type (fill a text field), extract (read current "
                "page text), links (list page links), screenshot (save a "
                "screenshot), close (shut down the session). Chain calls "
                "across steps to interact with websites like a browsing agent."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["goto", "click", "type", "extract", "links", "screenshot", "close"],
                        "description": "The browser action to perform"
                    },
                    "url": {
                        "type": "string",
                        "description": "URL to navigate to (goto) or output path (screenshot)"
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS selector or XPath of the element (click, type)"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type into a field (type)"
                    },
                    "max_content": {
                        "type": "integer",
                        "description": "Max characters of page text to return",
                        "default": 8000
                    }
                },
                "required": ["action"]
            }
        }
    }
]

TOOL_FUNCTIONS = {
    "get_time": get_time,
    "search_web": search_web,
    "browse_web": browse_web
}
