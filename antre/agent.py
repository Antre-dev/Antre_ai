import json

from .model import call_model
from .tools.registry import TOOL_DEFINITIONS, TOOL_FUNCTIONS
from .prompt import SYSTEM_PROMPT


messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT
    }
]


def handle_message(user_input):
    messages.append({
        "role": "user",
        "content": user_input
    })

    response = call_model(
        messages,
        tools=TOOL_DEFINITIONS
    )

    if not response.get("tool_calls"):
        messages.append(response)
        return response["content"]

    messages.append(response)

    for tool_call in response["tool_calls"]:
        tool_name = tool_call["function"]["name"]
        arguments = json.loads(
            tool_call["function"]["arguments"]
        )

        function = TOOL_FUNCTIONS.get(tool_name)

        if not function:
            result = {
                "success": False,
                "error": "Unknown tool"
            }
        else:
            result = function(**arguments)

        messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": json.dumps(result)
        })

    final_response = call_model(
        messages,
        tools=TOOL_DEFINITIONS
    )

    messages.append(final_response)

    return final_response["content"]