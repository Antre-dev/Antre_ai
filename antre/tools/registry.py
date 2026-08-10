from .system.get_time import get_time


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
    }
]


TOOL_FUNCTIONS = {
    "get_time": get_time
}