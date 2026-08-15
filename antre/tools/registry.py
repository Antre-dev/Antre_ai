from .system.get_time import get_time
from .web.search_web import search_web, browse_web
from .system.memory import memory_save, memory_recall
from antre.tools.system.ssh import run_ssh
from antre.tools.system.file_edit import file_read, file_write

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current local time.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
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
                        "description": "The web search query",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results",
                    },
                },
                "required": ["query"],
            },
        },
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
                        "enum": [
                            "goto",
                            "click",
                            "type",
                            "extract",
                            "links",
                            "screenshot",
                            "close",
                        ],
                        "description": "The browser action to perform",
                    },
                    "url": {
                        "type": "string",
                        "description": (
                            "URL to navigate to (goto) or output "
                            "path (screenshot)"
                        ),
                    },
                    "selector": {
                        "type": "string",
                        "description": (
                            "CSS selector or XPath of the element "
                            "(click, type)"
                        ),
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type into a field (type)",
                    },
                    "max_content": {
                        "type": "integer",
                        "description": "Max characters of page text to return",
                        "default": 8000,
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_save",
            "description": (
                "Save an important fact, preference, or decision to "
                "long-term memory so it can be recalled in future sessions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The fact or information to remember",
                    },
                    "tags": {
                        "type": "string",
                        "description": "Comma-separated keywords for retrieval",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_recall",
            "description": (
                "Search long-term memory for information saved in past "
                "conversations or sessions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords to search for",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max entries to return",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
    "type": "function",
    "function": {
        "name": "run_ssh",
        "description": "Run a command on a remote host over SSH (e.g. the homelab server). Requires user approval.",
        "parameters": {
            "type": "object",
            "properties": {
                "host":    {"type": "string", "description": "Remote host IP or hostname"},
                "command": {"type": "string", "description": "Shell command to execute"},
                "user":    {"type": "string", "description": "SSH username", "default": "ubuntu"},
                "port":    {"type": "integer", "description": "SSH port", "default": 22},
            },
            "required": ["host", "command"],
        },
    },
},
    {
    "type": "function",
    "function": {
        "name": "file_read",
        "description": (
            "Read a text file (relative to the project root) or list a directory. "
            "Safer than cat: paths resolve inside the project, .env is blocked."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path, relative to project root"},
                "limit": {"type": "integer", "description": "Show only the first N lines (0 = all)", "default": 0},
            },
            "required": ["path"],
        },
    },
    },
    {
    "type": "function",
    "function": {
        "name": "file_write",
        "description": (
            "Write or append to a file inside the project. Snapshots a timestamped .bak "
            "first. dry_run=True previews a diff without writing. .env is blocked."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path, relative to project root"},
                "content": {"type": "string", "description": "Full new content (write) or text to add (append)"},
                "action": {"type": "string", "enum": ["write", "append"], "description": "Replace or append", "default": "write"},
                "dry_run": {"type": "boolean", "description": "Preview the change as a diff without writing", "default": False},
            },
            "required": ["path", "content"],
        },
    },
    },
]


TOOL_FUNCTIONS = {
    "get_time": get_time,
    "search_web": search_web,
    "browse_web": browse_web,
    "memory_save": memory_save,
    "memory_recall": memory_recall,
    "run_ssh": run_ssh,
    "file_read": file_read,
    "file_write": file_write,
}