"""
Permission policy and the user-approval gate.

Tools are classified by danger level. By default anything at or above
AUTO_CONFIRM_THRESHOLD (or explicitly flagged) requires the user to
approve before it runs.

AUTO MODE relaxes this: with auto mode enabled, every tool below the top
danger tier runs automatically — file edits, web browsing, searches,
memory ops, and routine SSH commands — while anything that can genuinely
break the machine (destructive remote commands, destructive ops) still
stops and asks first.

User-facing danger is "level 1 (safest) … level 5 (most dangerous)".
Internally that maps to DangerLevel.SAFE(0) … CRITICAL(4), so "level 5"
== CRITICAL == the only tier that always requires approval in auto mode.
"""

from __future__ import annotations

import hashlib
import json
import re
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
# run_ssh is NOT here anymore: it is classified dynamically by what the
# actual command does (see ssh_command_danger below).
AUTO_MODE_ALWAYS_CONFIRM = set()

_auto_mode = False


def auto_mode() -> bool:
    """Is auto mode currently enabled?"""
    return _auto_mode


def set_auto_mode(on: bool) -> None:
    """Enable or disable auto mode."""
    global _auto_mode
    _auto_mode = bool(on)


# ============================================================
# SSH command classification (tiered permissions)
# ============================================================

# Command verbs that can destroy data, kill processes, or break the box.
# Matched per command segment (after splitting compounds on ; && || | \n).
_DESTRUCTIVE_PREFIXES = (
    # deletion / data loss
    "rm ", "rmdir ", "mv ", "dd ", "wipefs ", "truncate ",
    "mkfs", "fdisk", "parted ",
    # power / process control
    "shutdown", "reboot", "poweroff", "halt", "init ",
    "kill ", "pkill", "killall", "kill -9",
    # users / ownership / perms
    "userdel", "groupdel", "passwd ", "chown ", "chmod ", "chroot ",
    # service disruption
    "systemctl stop", "systemctl disable", "systemctl mask",
    "systemctl reboot", "systemctl poweroff", "service stop",
    # package removal
    "apt remove", "apt purge", "apt autoremove",
    "apt-get remove", "apt-get purge", "apt-get autoremove",
    "dpkg -r", "dpkg -p", "dpkg --purge",
    "yum remove", "dnf remove", "pacman -r", "snap remove",
    "pip uninstall", "pip3 uninstall",
    # git / docker / containers — history or container destruction
    "git reset --hard", "git clean", "git push --force", "git push -f",
    "docker rm", "docker rmi", "docker stop", "docker kill",
    "docker system prune", "docker volume rm",
    "podman rm", "podman rmi", "helm delete",
)

# Commands that only read state — harmless to auto-run.
_READONLY_PREFIXES = {
    "ls", "cat", "head", "tail", "less", "more", "pwd", "whoami", "id",
    "df", "du", "free", "ps", "top", "htop", "uptime", "uname",
    "hostname", "date", "echo", "env", "which", "stat", "find", "grep",
    "git status", "git log", "git diff", "git branch",
    "systemctl status", "systemctl is-active", "systemctl is-enabled",
    "docker ps", "docker images",
}


def ssh_command_danger(command: str) -> DangerLevel:
    """Classify an SSH command by what it actually does.

    Returns CRITICAL for anything destructive (level 5), SAFE if EVERY
    segment is read-only / reporting, and MEDIUM for anything in between
    (routine mutating commands like apt install, mkdir, touch, systemctl
    restart — these run automatically in auto mode).

    Heuristic: compound commands (``;`` ``&&`` ``||`` ``|`` newline) are
    split and each segment is checked, so ``ls; rm -rf /tmp/x`` is caught.
    ``sudo`` prefixes are ignored.
    """
    if not command or not command.strip():
        # Empty command shouldn't happen — be strict rather than sorry.
        return DangerLevel.CRITICAL

    saw_mutating = False

    for segment in re.split(r"[;&|\n]+", command):
        seg = re.sub(r"^\s*sudo\s+", "", segment).strip().lower()
        if not seg:
            continue

        for prefix in _DESTRUCTIVE_PREFIXES:
            if seg == prefix.rstrip() or seg.startswith(prefix):
                return DangerLevel.CRITICAL

        # find can delete/execute too: `find / -name x -delete`, `-exec rm`.
        if seg.startswith("find ") and any(
            token in seg for token in ("-delete", "-exec", "-ok")
        ):
            return DangerLevel.CRITICAL

        # `... | xargs rm` pipelines — check what xargs actually runs.
        if seg.startswith("xargs") and any(
            verb in seg for verb in ("rm", "kill", "mv ", "chmod", "chown", "dd")
        ):
            return DangerLevel.CRITICAL

        # Read-only reporting commands — exact verb or verb + args.
        # (Prefix + space so `ls` matches `ls -la` but not `lsof`.)
        if seg in _READONLY_PREFIXES or any(
            seg.startswith(rp + " ") for rp in _READONLY_PREFIXES
        ):
            continue

        saw_mutating = True

    return DangerLevel.MEDIUM if saw_mutating else DangerLevel.SAFE


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

    AUTO MODE: everything below CRITICAL danger (and not in the
    always-confirm list) is auto-approved — no prompt. SSH is tiered by
    the actual command: read-only and routine commands run free, only
    destructive commands (level 5 / CRITICAL) stop and ask.

    Already-approved calls (same tool + args, within TTL) pass silently.
    """
    args = args or {}

    if auto_mode():
        # SSH is tiered by what the command actually does.
        if tool_name == "run_ssh":
            level = ssh_command_danger(str(args.get("command", "")))
            if level < DangerLevel.CRITICAL:
                return
        elif tool_name not in AUTO_MODE_ALWAYS_CONFIRM:
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
