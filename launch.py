#!/usr/bin/env python3
"""
ANTRE — native window launcher (replaces the kiosk-browser launch.sh)

Starts the core FastAPI server if it isn't already running, opens the
interface in a native desktop window (system webview — NOT a browser,
no kiosk mode, no tabs, no URL bar), and shuts the server back down
when the window is closed.

Usage:
  ./launch.py [--fullscreen] [--debug]

Env overrides:
  ANTRE_HOST   bind address (default 127.0.0.1)
  ANTRE_PORT   port        (default 8000)
"""

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("ANTRE_HOST", "127.0.0.1")
PORT = int(os.environ.get("ANTRE_PORT", "8000"))
URL = f"http://{HOST}:{PORT}"
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "server.log"


def pick_python() -> str:
    """Use the project venv if it exists, else whatever runs us."""
    venv = ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.is_file() else sys.executable


def server_running() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/api/status", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_server(python: str) -> subprocess.Popen:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG_FILE, "ab", buffering=0)
    proc = subprocess.Popen(
        [python, "-m", "uvicorn", "antre.web_app.app:app",
         "--host", HOST, "--port", str(PORT)],
        cwd=ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    for _ in range(120):  # up to 60s
        if server_running():
            return proc
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    raise RuntimeError(f"server failed to start — see {LOG_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ANTRE native window launcher")
    parser.add_argument("--fullscreen", action="store_true",
                         help="open the window fullscreen (still a native window)")
    parser.add_argument("--debug", action="store_true",
                         help="enable webview devtools / debug mode")
    args = parser.parse_args()

    # 1. Make sure the core server is up
    started = False
    server = None
    if not server_running():
        print(f"[antre] core server not running — starting on {URL}")
        server = start_server(pick_python())
        started = True
        print(f"[antre] core online (pid {server.pid})")
    else:
        print(f"[antre] core already running on {URL}")

    # 2. Open the native window. Blocks until the window is closed.
    try:
        import webview  # heavy import: only needed for the window
    except ImportError:
        print("[antre] ERROR: pywebview is not installed.", file=sys.stderr)
        print("  Install it with:  pip install pywebview", file=sys.stderr)
        print("  On Debian/Ubuntu you also need the WebKit2 GTK packages:", file=sys.stderr)
        print("    sudo apt install python3-gi gir1.2-webkit2-4.1", file=sys.stderr)
        sys.exit(1)

    window = webview.create_window(
        "Antre",
        URL,
        width=1280,
        height=800,
        min_size=(900, 600),
        fullscreen=args.fullscreen,
        resizable=True,
    )
    webview.start(debug=args.debug)

    # 3. Window closed — take the server down with it (only if we started it)
    if started and server is not None:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        print("[antre] core server stopped")

    print("[antre] interface closed — bye")


if __name__ == "__main__":
    main()