import asyncio
import inspect
import json

from .model import call_model
from .tools.registry import TOOL_DEFINITIONS, TOOL_FUNCTIONS
from .prompt import SYSTEM_PROMPT
from .permissions import PermissionRequired, check, grant


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

# Holds state while we're waiting on a user's yes/no for a
# permission-gated tool call. None when nothing is pending.
#
# Shape when set:
# {
#     "messages": [...],        # in-progress messages list for this turn
#     "user_input": str,        # the ORIGINAL message that triggered the tool call
#     "tool_call": {...},       # the tool call awaiting approval
#     "tool_name": str,
#     "args": dict,
#     "remaining": [...],       # other tool calls still to run in this batch
# }
_pending_approval = None

APPROVE_WORDS = {
    "yes", "y", "approve", "approved", "ok", "okay",
    "sure", "go ahead", "confirm", "do it", "run it",
}


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

def _tool_call_args(tool_call) -> dict:
    """Parse a tool call's arguments, tolerating bad JSON."""

    raw_arguments = tool_call["function"].get("arguments", "{}")

    try:
        return json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {}


async def _execute_tool(tool_call):
    """
    Execute one tool call.

    Supports both synchronous and asynchronous tools.

    NOTE: this does NOT check permissions — that happens earlier,
    in _run_tool_calls, before this is ever invoked.
    """

    tool_name = tool_call["function"]["name"]
    arguments = _tool_call_args(tool_call)

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


def _append_tool_result(messages, tool_call, result) -> None:
    """Serialize a tool result and append it to messages, truncating
    if needed so one tool can't consume the whole context."""

    content = json.dumps(
        result,
        ensure_ascii=False,
        default=str,
    )

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


async def _run_tool_calls(tool_calls, messages):
    """
    Run tool_calls in order, appending results to messages.

    Tools run sequentially (not concurrently) so that if one needs
    permission, we can stop cleanly without losing track of results
    already produced earlier in the same batch.

    Returns None once every tool call has run. Otherwise returns a
    dict describing the tool call that needs approval, plus whatever
    tool calls in this batch hadn't run yet ("remaining"), so the
    caller can pick up exactly where we left off after approval.
    """

    for i, tool_call in enumerate(tool_calls):
        tool_name = tool_call["function"]["name"]
        arguments = _tool_call_args(tool_call)

        try:
            check(tool_name, arguments)
        except PermissionRequired as e:
            return {
                "tool_call": tool_call,
                "tool_name": tool_name,
                "args": arguments,
                "message": str(e),
                "remaining": tool_calls[i + 1:],
            }

        result = await _execute_tool(tool_call)
        _append_tool_result(messages, tool_call, result)

    return None


def _permission_prompt(tool_name, args) -> str:
    return (
        f"I need your permission to run **{tool_name}** with args "
        f"`{args}`. Reply **yes** to approve (stays valid 5 minutes) "
        f"or **no** to cancel."
    )


async def _agent_loop(messages):
    """
    Call the model, running any tool calls it requests, until it
    gives a final text reply or a tool call hits a permission gate.

    Returns (response, pending):
      - (response, None) on a normal final reply
      - (None, pending)  if a permission gate was hit
    """

    while True:
        response = call_model(messages, tools=TOOL_DEFINITIONS)

        if not response.get("tool_calls"):
            return response, None

        # Assistant tool-call message MUST remain in context.
        messages.append(response)

        pending = await _run_tool_calls(response["tool_calls"], messages)
        if pending is not None:
            return None, pending

        # else: all tool results appended, loop back to the model


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
    - tool calls (async + sync)
    - multiple tool calls
    - permission-gated tools, pausing for user yes/no
    """

    global _pending_approval

    # --------------------------------------------------------
    # Resuming after a permission question
    # --------------------------------------------------------
    if _pending_approval is not None:
        pending = _pending_approval
        _pending_approval = None
        messages = pending["messages"]
        original_input = pending["user_input"]

        if user_input.strip().lower() not in APPROVE_WORDS:
            reply = "Understood — I cancelled that command."
            history.append({"role": "user", "content": original_input})
            history.append({"role": "assistant", "content": reply})
            _make_room()
            return reply

        grant(pending["tool_name"], pending["args"])
        result = await _execute_tool(pending["tool_call"])
        _append_tool_result(messages, pending["tool_call"], result)

        # Finish any other tool calls that were queued in the same batch.
        remaining_pending = await _run_tool_calls(pending["remaining"], messages)
        if remaining_pending is not None:
            _pending_approval = {
                "messages": messages,
                "user_input": original_input,
                **remaining_pending,
            }
            return _permission_prompt(
                remaining_pending["tool_name"], remaining_pending["args"]
            )

        response, new_pending = await _agent_loop(messages)

        if new_pending is not None:
            _pending_approval = {
                "messages": messages,
                "user_input": original_input,
                **new_pending,
            }
            return _permission_prompt(new_pending["tool_name"], new_pending["args"])

    # --------------------------------------------------------
    # Normal flow
    # --------------------------------------------------------
    else:
        original_input = user_input

        # Make room BEFORE adding the new message.
        _make_room(incoming=count_tokens(user_input) + 1_000)

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

        response, pending = await _agent_loop(messages)

        if pending is not None:
            _pending_approval = {
                "messages": messages,
                "user_input": original_input,
                **pending,
            }
            return _permission_prompt(pending["tool_name"], pending["args"])

    # --------------------------------------------------------
    # Persist compact conversation
    # --------------------------------------------------------

    reply = response.get("content") or ""

    history.append({
        "role": "user",
        "content": original_input,
    })

    history.append({
        "role": "assistant",
        "content": reply,
    })

    # Make sure persistent history doesn't grow forever.
    _make_room()

    return reply