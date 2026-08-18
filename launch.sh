#!/usr/bin/env bash
#
# ANTRE — fullscreen launcher (Linux)
#
# Starts the core server (if it isn't already running) and opens the
# interface fullscreen in a kiosk browser. Close the browser window to
# shut everything back down.
#
# Usage:
#   ./launch.sh
#
# Env overrides:
#   ANTRE_HOST   bind address (default 127.0.0.1)
#   ANTRE_PORT   port        (default 8000)
#
set -euo pipefail
cd "$(dirname "$0")"

HOST="${ANTRE_HOST:-127.0.0.1}"
PORT="${ANTRE_PORT:-8000}"
URL="http://${HOST}:${PORT}"
LOG_DIR="$(dirname "$0")/logs"

PY="python3"
if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; fi

# ---------------------------------------------------------------
# 1. Make sure the core server is up
# ---------------------------------------------------------------
STARTED=0
SERVER_PID=""
if ! curl -sf --max-time 2 "${URL}/api/status" >/dev/null 2>&1; then
    echo "[antre] core server not running — starting on ${URL}"
    mkdir -p "${LOG_DIR}"
    nohup "${PY}" -m uvicorn antre.web_app.app:app \
        --host "${HOST}" --port "${PORT}" \
        >> "${LOG_DIR}/server.log" 2>&1 &
    SERVER_PID=$!
    STARTED=1
    echo "[antre] server pid ${SERVER_PID} — waiting for readiness"
    for _ in $(seq 1 60); do
        if curl -sf --max-time 1 "${URL}/api/status" >/dev/null 2>&1; then
            break
        fi
        sleep 0.5
    done
    if ! curl -sf --max-time 2 "${URL}/api/status" >/dev/null 2>&1; then
        echo "[antre] ERROR: server failed to start — see ${LOG_DIR}/server.log" >&2
        exit 1
    fi
    echo "[antre] core online"
fi

# ---------------------------------------------------------------
# 2. Pick a fullscreen-capable browser
#    Prefer the system default web browser; fall back to a list.
# ---------------------------------------------------------------
BROWSER=""
DEFAULT_BROWSER="$(xdg-mime query default x-scheme-handler/https 2>/dev/null || true)"

# Map the .desktop file name (e.g. "firefox.desktop") to a command name
for candidate in "${DEFAULT_BROWSER%.desktop}" chromium chromium-browser \
                 google-chrome google-chrome-stable microsoft-edge \
                 brave-browser firefox; do
    [ -n "${candidate}" ] || continue
    if command -v "${candidate}" >/dev/null 2>&1; then
        BROWSER="${candidate}"
        break
    fi
done

if [ -z "${BROWSER}" ]; then
    echo "[antre] no supported browser found — open ${URL} manually" >&2
    exit 1
fi
echo "[antre] launching ${BROWSER} fullscreen → ${URL}"

# ---------------------------------------------------------------
# 3. Launch fullscreen (kiosk). Blocks until the browser exits,
#    then takes the server down with it (only if we started it).
# ---------------------------------------------------------------
cleanup() {
    if [ "${STARTED}" = "1" ] && [ -n "${SERVER_PID}" ]; then
        kill "${SERVER_PID}" 2>/dev/null || true
        echo "[antre] core server stopped"
    fi
}
trap cleanup EXIT

case "${BROWSER}" in
    chromium*|google-chrome*|microsoft-edge|brave-browser)
        "${BROWSER}" --kiosk --app="${URL}" \
            --noerrdialogs --disable-infobars --no-first-run \
            --disable-session-crashed-bubble --disable-translate \
            --check-for-update-interval=31536000 >/dev/null 2>&1
        ;;
    firefox)
        "${BROWSER}" --kiosk "${URL}" >/dev/null 2>&1
        ;;
esac

echo "[antre] interface closed — bye"
