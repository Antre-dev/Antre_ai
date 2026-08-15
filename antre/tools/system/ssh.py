from __future__ import annotations

import asyncssh


async def run_ssh(host: str, command: str, user: str = "ubuntu", port: int = 22) -> dict:
    """Run `command` on `host` over SSH.

    Returns dict with stdout / stderr / exit_status, or {"success": False, "error": ...}.
    """
    try:
        async with asyncssh.connect(
            host, username=user, port=port, known_hosts=None
        ) as conn:
            result = await conn.run(command, check=False)
        return {
            "success": True,
            "host": host,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_status": result.exit_status,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}