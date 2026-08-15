import asyncio
import inspect
import json

from .model import call_model
from .tools.registry import TOOL_DEFINITIONS, TOOL_FUNCTIONS
from .prompt import SYSTEM_PROMPT


# ============================================================
# CONFIG
# ============================================================

MAX_CONTEXT_TOKENS = 16_000

# Number of user/assistant messages kept verbatim.
# 16 messages ≈ 8 normal conversation turns.
KEEP_RECENT_MESSAGES = 16

# Maximum size of ONE tool result in characters.
# 6000 chars is roughly 1500 tokens for normal English text.
MAX_TOOL_RESULT_CHARS = 6_000

# Summary gets condensed once it exceeds this many tokens.
SUMMARY_LIMIT = 1_500

# Reserve space for the model's answer + some safety margin.
OUTPUT_HEADROOM = 2_000


# ============================================================
# TOKEN COUNTING
# ============================================================

try:
    import tiktoken

    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        if not text:
            return 0

        return len(_enc.encode(str(text)))

except ImportError:

    def count_tokens(text: str) -> int:
        if not text:
            return 0

        # Rough fallback:
        # ~4 characters per token
        return max(1, len(str(text)) // 4)


# ============================================================
# STATE
# ============================================================

history = []
summary = ""


# ============================================================
# TOKEN COST HELPERS
# ============================================================

def _msg_cost(message) -> int:
    """
    Rough token cost of a message.
    """

    content = message.get("content") or ""

    return count_tokens(content) + 4


def _history_cost() -> int:
    return sum(
        _msg_cost(message)
        for message in history
    )


def _tool_definition_cost() -> int:
    """
    Count tokens used by tool definitions.

    Tool definitions are sent to the model on every call,
    so they need to be included in our context budget.
    """

    try:
        serialized = json.dumps(
            TOOL_DEFINITIONS,
            ensure_ascii=False,
        )

        return count_tokens(serialized)

    except Exception:
        return 0


# ============================================================
# SUMMARY
# ============================================================

def _fold_into_summary(turn) -> None:
    """
    Add an old conversation message to the rolling summary.

    If the summary becomes too large, ask the model to
    condense it.
    """

    global summary

    role = turn.get("role", "unknown")
    content = turn.get("content") or ""

    line = f"{role}: {content}"

    if summary:
        summary = f"{summary}\n{line}"
    else:
        summary = line

    if count_tokens(summary) <= SUMMARY_LIMIT:
        return

    try:
        response = call_model([
            {
                "role": "user",
                "content": (
                    "Condense the following conversation memory "
                    "into a compact summary.\n\n"
                    "Keep:\n"
                    "- important facts\n"
                    "- user preferences\n"
                    "- ongoing tasks\n"
                    "- important decisions\n"
                    "- unresolved questions\n\n"
                    "Remove:\n"
                    "- repetition\n"
                    "- filler\n"
                    "- unnecessary wording\n\n"
                    f"Conversation memory:\n{summary}"
                ),
            }
        ])

        new_summary = response.get("content")

        if new_summary:
            summary = new_summary

        else:
            # Character fallback ≈ 1500 tokens
            summary = summary[-6_000:]

    except Exception:
        # ~1500 tokens max using the chars/4 approximation.
        summary = summary[-6_000:]


# ============================================================
# CONTEXT MANAGEMENT
# ============================================================

def _context_budget() -> int:
    """
    Calculate how many tokens are available for conversation
    history and summary.
    """

    system_tokens = count_tokens(SYSTEM_PROMPT)
    tool_tokens = _tool_definition_cost()

    budget = (
        MAX_CONTEXT_TOKENS
        - system_tokens
        - tool_tokens
        - OUTPUT_HEADROOM
    )

    return max(1_000, budget)


def _make_room(incoming: int = 0) -> None:
    """
    Remove old messages until the context fits the budget.

    Old messages are folded into the rolling summary.
    Recent messages are preserved.
    """

    budget = _context_budget()

    while (
        _history_cost()
        + count_tokens(summary)
        + incoming
        > budget
        and len(history) > KEEP_RECENT_MESSAGES
    ):
        oldest = history.pop(0)

        _fold_into_summary(oldest)


# ============================================================
# TOOL EXECUTION
# ============================================================

async def _execute_tool(tool_call):
    """
    Execute one tool call.

    Supports both synchronous and asynchronous tools.
    """

    tool_name = tool_call["function"]["name"]

    raw_arguments = tool_call["function"].get(
        "arguments",
        "{}",
    )

    try:
        arguments = json.loads(raw_arguments)

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Invalid tool arguments: {e}",
        }

    function = TOOL_FUNCTIONS.get(tool_name)

    if not function:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}",
        }

    try:
        result = function(**arguments)

        if inspect.isawaitable(result):
            result = await result

        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# ============================================================
# MAIN AGENT
# ============================================================

async def handle_message(user_input: str) -> str:
    """
    Process one user message.

    Handles:
    - conversation history
    - rolling summaries
    - context limits
    - tool calls
    - async tools
    - multiple tool calls
    """

    # Make room BEFORE adding the new message.
    _make_room(
        incoming=count_tokens(user_input) + 1_000
    )

    # --------------------------------------------------------
    # Build context
    # --------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    if summary:
        messages.append({
            "role": "system",
            "content": (
                "Prior conversation context:\n"
                + summary
            ),
        })

    messages.extend(history)

    messages.append({
        "role": "user",
        "content": user_input,
    })

    # --------------------------------------------------------
    # Model / tool loop
    # --------------------------------------------------------

    while True:

        response = call_model(
            messages,
            tools=TOOL_DEFINITIONS,
        )

        # Normal response
        if not response.get("tool_calls"):
            break

        # Assistant tool-call message MUST remain in context.
        messages.append(response)

        tool_calls = response["tool_calls"]

        # ----------------------------------------------------
        # Execute tools
        # ----------------------------------------------------

        # Run multiple async tools concurrently when possible.
        results = await asyncio.gather(
            *[
                _execute_tool(tool_call)
                for tool_call in tool_calls
            ]
        )

        for tool_call, result in zip(
            tool_calls,
            results,
        ):
            content = json.dumps(
                result,
                ensure_ascii=False,
                default=str,
            )

            # Prevent one tool from consuming the entire context.
            if len(content) > MAX_TOOL_RESULT_CHARS:
                content = (
                    content[:MAX_TOOL_RESULT_CHARS]
                    + "\n...[tool result truncated]"
                )

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": content,
            })

    # --------------------------------------------------------
    # Persist compact conversation
    # --------------------------------------------------------

    history.append({
        "role": "user",
        "content": user_input,
    })

    history.append({
        "role": "assistant",
        "content": response.get("content") or "",
    })

    # Make sure persistent history doesn't grow forever.
    _make_room()

    return response.get("content") or ""