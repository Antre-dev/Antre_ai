from .system.get_time import get_time

from .web.search_web import search_web
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
}
]


TOOL_FUNCTIONS = {
    "get_time": get_time,
    "search_web": search_web
}