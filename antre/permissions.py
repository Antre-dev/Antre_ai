"""
Permission policy and the user-approval gate.

Tools are classified by danger level. By default anything at or above
AUTO_CONFIRM_THRESHOLD (or explicitly flagged) requires the user to
approve before it runs.

AUTO MODE relaxes this: with auto mode enabled, every tool below
CRITICAL danger runs automatically — file edits, web browsing, searches,
memory ops — while anything that can genuinely break the machine (SSH
command execution, destructive ops) still stops and asks first.
"""

from __future__ import annotations

import hashlib
import json
import time
from enum import IntEnum


class DangerLevel(IntEnum):
    SAFE = 0      # read-only, no side effects
    LOW = 1       # minor side effects (network reads)
    MEDIUM = 2    # mutates external state (posts, clicks, writes)
    HIGH = 3      # can affect the host machine (installs, file writes)
    CRITICAL = 4  # arbitrary remote code execution / destructive ops


# Tools that must ALWAYS be confirmed, regardless of level.
ALWAYS_CONFIRM = {"run_ssh", "browse_web"}

# tool name -> (danger level, requires confirmation)
TOOL_POLICY = {
    "get_time":      (DangerLevel.SAFE,    False),
    "memory_recall": (DangerLevel.SAFE,    False),
    "memory_save":   (DangerLevel.LOW,     False),
    "search_web":    (DangerLevel.LOW,     False),
    "browse_web":    (DangerLevel.MEDIUM,  True),
    "run_ssh":       (DangerLevel.CRITICAL, True),
    "file_read":     (DangerLevel.SAFE,     False),
    "file_write":    (DangerLevel.HIGH,     True),
}

# Any tool at or above this level requires confirmation by default.
AUTO_CONFIRM_THRESHOLD = DangerLevel.HIGH

# How long a granted approval stays valid (seconds).
APPROVAL_TTL = 300  # 5 minutes


# ============================================================
# AUTO MODE
# ============================================================

# In auto mode, tools BELOW this level run without asking.
AUTO_MODE_THRESHOLD = DangerLevel.CRITICAL

# Even in auto mode, these tools always stop and ask.
# run_ssh = arbitrary remote command execution → always confirm.
AUTO_MODE_ALWAYS_CONFIRM = {"run_ssh"}

_auto_mode = False


def auto_mode() -> bool:
    """Is auto mode currently enabled?"""
    return _auto_mode


def set_auto_mode(on: bool) -> None:
    """Enable or disable auto mode."""
    global _auto_mode
    _auto_mode = bool(on)


class PermissionRequired(Exception):
    """Raised when a tool call needs manual user confirmation."""


class ApprovalStore:
    """Tracks user-approved tool calls in memory (not persisted)."""

    def __init__(self, ttl: int = APPROVAL_TTL):
        self._ttl = ttl
        self._approved: dict[str, float] = {}  # fingerprint -> timestamp

    def _fingerprint(self, tool_name: str, args: dict) -> str:
        blob = json.dumps({"tool": tool_name, "args": args}, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()

    def is_approved(self, tool_name: str, args: dict) -> bool:
        fp = self._fingerprint(tool_name, args)
        ts = self._approved.get(fp)
        if ts is None:
            return False
        if time.time() - ts > self._ttl:
            del self._approved[fp]
            return False
        return True

    def grant(self, tool_name: str, args: dict) -> None:
        self._approved[self._fingerprint(tool_name, args)] = time.time()

    def revoke_all(self) -> None:
        self._approved.clear()


# Singleton shared across the process.
approval_store = ApprovalStore()


def get_policy(tool_name: str) -> tuple[DangerLevel, bool]:
    if tool_name in TOOL_POLICY:
        return TOOL_POLICY[tool_name]
    # Unknown tools default to the most restrictive handling.
    return DangerLevel.CRITICAL, True


def requires_approval(tool_name: str, args: dict | None = None) -> bool:
    level, explicit = get_policy(tool_name)
    return explicit or tool_name in ALWAYS_CONFIRM or level >= AUTO_CONFIRM_THRESHOLD


def check(tool_name: str, args: dict | None = None) -> None:
    """Gate a tool call. Raises PermissionRequired if the user must confirm.

    AUTO MODE: anything below CRITICAL danger (and not in the
    always-confirm list) is auto-approved — no prompt. Only genuinely
    dangerous calls still stop and ask.

    Already-approved calls (same tool + args, within TTL) pass silently.
    """
    args = args or {}

    # Auto mode bypass for everything that can't break the machine.
    if auto_mode() and tool_name not in AUTO_MODE_ALWAYS_CONFIRM:
        level, _explicit = get_policy(tool_name)
        if level < AUTO_MODE_THRESHOLD:
            return

    if requires_approval(tool_name, args) and not approval_store.is_approved(tool_name, args):
        raise PermissionRequired(
            f"Tool '{tool_name}' needs confirmation. Args: {args}"
        )


def grant(tool_name: str, args: dict | None = None) -> None:
    """Mark a tool call as user-approved so it can execute."""
    approval_store.grant(tool_name, args or {})


def revoke_all() -> None:
    approval_store.revoke_all()
