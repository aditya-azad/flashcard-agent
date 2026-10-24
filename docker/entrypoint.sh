#!/usr/bin/env bash
# Container entrypoint for the flashcard-agent MCP server.
#
# Seeds the Anki base dir (skipping Anki's interactive first-run dialogs),
# signs in to AnkiWeb from ANKIWEB_EMAIL/ANKIWEB_PASSWORD if provided, starts
# Anki (official desktop build) under Xvfb with AnkiConnect, then serves the
# MCP server over Streamable HTTP.
set -euo pipefail

ANKI_BASE="${ANKI_BASE:-/data/anki}"
ANKI_DIR="/opt/anki"
MCP_HOST="${MCP_HOST:-0.0.0.0}"
MCP_PORT="${MCP_PORT:-8000}"
ANKIWEB_SYNC_INTERVAL="${ANKIWEB_SYNC_INTERVAL:-300}"
export ANKI_BASE
export DISPLAY="${DISPLAY:-:99}"
export LANG="${LANG:-C.UTF-8}"

log() { echo "[entrypoint] $*"; }

start_xvfb() {
    Xvfb :99 -screen 0 1024x768x24 -nolisten tcp >/dev/null 2>&1 &
    until [ -S /tmp/.X11-unix/X99 ]; do sleep 0.2; done
}

wait_anki_connect() {
    local timeout="${1:-180}" waited=0
    until curl -s -m 2 -X POST -d '{"action":"version","version":6}' \
            http://127.0.0.1:8765 | grep -q '"result"'; do
        if [ "$waited" -ge "$timeout" ]; then
            return 1
        fi
        sleep 1
        waited=$((waited + 1))
    done
}

start_xvfb

mkdir -p "$ANKI_BASE/addons21/AnkiConnect"
cp -r /opt/AnkiConnect/. "$ANKI_BASE/addons21/AnkiConnect/"
# Auto-answers Anki's full-sync confirmation modals (headless: nobody to click)
cp -r /app/docker/anki_addons/headless-sync "$ANKI_BASE/addons21/"

log "Setting up Anki base dir at $ANKI_BASE"
if ! PYTHONPATH="$ANKI_DIR/app_packages" \
    "$ANKI_DIR/python/bin/python3" /app/docker/anki_setup.py; then
    log "ERROR: Anki setup / AnkiWeb sign-in failed; check your credentials in .env"
    exit 1
fi

log "Starting Anki"
"$ANKI_DIR/anki" >/tmp/anki.log 2>&1 &
log "Waiting for AnkiConnect"
if ! wait_anki_connect; then
    log "ERROR: AnkiConnect did not come up"
    exit 1
fi
log "AnkiConnect is up"

# While signed in, periodically push/pull the collection through Anki's own
# sync routine, so cards added via the MCP server reach AnkiWeb (or a
# self-hosted server) without waiting for a restart. Fire-and-forget: the
# call returns immediately and Anki syncs in the background.
if [ -n "${ANKIWEB_EMAIL:-}" ] && [ -n "${ANKIWEB_PASSWORD:-}" ]; then
    (
        while true; do
            sleep "$ANKIWEB_SYNC_INTERVAL"
            RESULT=$(curl -s -m 120 -X POST -d '{"action":"sync","version":6}' \
                http://127.0.0.1:8765 || true)
            if echo "$RESULT" | grep -q '"error": null'; then
                echo "[entrypoint] $(date -u '+%Y-%m-%dT%H:%M:%SZ') sync triggered"
            else
                echo "[entrypoint] WARNING: periodic sync failed: $RESULT"
            fi
        done
    ) &
    log "Periodic sync with AnkiWeb enabled (every ${ANKIWEB_SYNC_INTERVAL}s)"
fi

log "Serving MCP over Streamable HTTP on ${MCP_HOST}:${MCP_PORT}"
exec flashcard-agent --http --host "$MCP_HOST" --port "$MCP_PORT"
