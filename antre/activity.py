"""Live activity bus.

The agent logs every tool call, chat message and permission event here.
The web app exposes this over SSE (/activity/stream), as history
(/activity/history) and as live stats (/api/status) so the MONITOR page
can show a real-time view of what Antre is doing — terminal commands,
browser actions, screenshots, file edits, memory writes.

In-memory only: a bounded ring buffer of recent events plus a set of
asyncio queues for live subscribers. No persistence, no disk writes.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from datetime import datetime, timezone

MAX_HISTORY = 500
MAX_RESULT_CHARS = 4000
MAX_ARGS_CHARS = 1500

# tool name -> category shown in the monitor
TOOL_CATEGORY = {
    "get_time": "system",
    "search_web": "search",
    "browse_web": "browser",
    "memory_save": "memory",
    "memory_recall": "memory",
    "run_ssh": "terminal",
    "file_read": "files",
    "file_write": "files",
}


class ActivityStore:
    """Bounded ring buffer of events + asyncio subscriber queues."""

    def __init__(self, maxlen: int = MAX_HISTORY):
        self._events: deque = deque(maxlen=maxlen)
        self._subscribers: set[asyncio.Queue] = set()
        self._counter = 0
        self._active_tools = 0
        self.started_at = time.time()

    # ----------------------------------------------------------
    # Subscription
    # ----------------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    # ----------------------------------------------------------
    # Emit / history
    # ----------------------------------------------------------

    def _next_id(self) -> int:
        self._counter += 1
        return self._counter

    def emit(self, event: dict) -> None:
        event = dict(event)
        event.setdefault("id", self._next_id())
        event.setdefault("ts", datetime.now(timezone.utc).isoformat())
        self._events.append(event)

        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Subscriber is too slow: drop the oldest buffered event
                # so it keeps getting the freshest ones.
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    pass

    def history(self, limit: int = MAX_HISTORY) -> list:
        events = list(self._events)
        if limit:
            events = events[-limit:]
        return events

    # ----------------------------------------------------------
    # Busy tracking (how many tools are running right now)
    # ----------------------------------------------------------

    def tool_started(self) -> None:
        self._active_tools += 1

    def tool_finished(self) -> None:
        self._active_tools = max(0, self._active_tools - 1)

    @property
    def busy(self) -> bool:
        return self._active_tools > 0

    @property
    def active_tools(self) -> int:
        return self._active_tools

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.started_at


# Singleton shared across the whole process.
store = ActivityStore()


# ============================================================
# Helpers used by the agent to log events
# ============================================================

def _cap(obj, n: int) -> str:
    """Serialize an object to JSON, capped at n characters."""
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    if len(s) > n:
        s = s[:n] + "...[truncated]"
    return s


def _screenshot_url(result) -> str | None:
    """Best-effort screenshot URL from a tool result dict."""
    if not isinstance(result, dict):
        return None
    url = result.get("screenshot_url")
    if url:
        return url
    path = result.get("screenshot")
    if path:
        return "/screenshots/" + os.path.basename(str(path))
    return None


def log_tool_start(tool: str, args: dict) -> None:
    store.tool_started()
    store.emit({
        "type": "tool.start",
        "category": TOOL_CATEGORY.get(tool, "system"),
        "tool": tool,
        "args": _cap(args, MAX_ARGS_CHARS),
        "status": "running",
        "t0": time.time(),
    })


def log_tool_done(tool: str, args: dict, result, started_at: float) -> None:
    store.tool_finished()
    ok = not isinstance(result, dict) or result.get("success") in (None, True)

    event = {
        "type": "tool.done",
        "category": TOOL_CATEGORY.get(tool, "system"),
        "tool": tool,
        "args": _cap(args, MAX_ARGS_CHARS),
        "status": "ok" if ok else "error",
        "result": _cap(result, MAX_RESULT_CHARS),
        "duration_ms": int((time.time() - started_at) * 1000),
    }

    if isinstance(result, dict):
        host = result.get("host")
        if host:
            event["host"] = host
        if tool == "run_ssh":
            event["command"] = str(args.get("command", ""))
        if tool == "browse_web":
            event["action"] = str(args.get("action", ""))
            event["url"] = str(args.get("url") or "") or result.get("url", "")
            event["title"] = str(result.get("title") or "")
        url = _screenshot_url(result)
        if url:
            event["screenshot_url"] = url

    store.emit(event)


def log_permission(tool: str, args: dict, message: str) -> None:
    store.emit({
        "type": "permission",
        "category": TOOL_CATEGORY.get(tool, "system"),
        "tool": tool,
        "args": _cap(args, MAX_ARGS_CHARS),
        "status": "waiting",
        "message": message,
    })


def log_cancel(tool: str, args: dict) -> None:
    store.emit({
        "type": "tool.cancel",
        "category": TOOL_CATEGORY.get(tool, "system"),
        "tool": tool,
        "args": _cap(args, MAX_ARGS_CHARS),
        "status": "cancelled",
    })


def log_chat(role: str, content: str) -> None:
    store.emit({
        "type": "chat",
        "category": "chat",
        "role": role,
        "content": str(content)[:MAX_RESULT_CHARS],
    })



def log_mode_change(enabled: bool) -> None:
    """Log an auto-mode on/off switch so the monitor shows it."""
    store.emit({
        "type": "mode",
        "category": "system",
        "mode": "auto" if enabled else "manual",
        "status": "enabled" if enabled else "disabled",
    })
