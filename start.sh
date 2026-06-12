#!/usr/bin/env bash
# TTB COLA Label Review — local launcher
# Starts model_server, app server, and ngrok tunnel in one command.
# Usage:  ./start.sh [dev|stage|prod]   (default: dev)

set -euo pipefail

ENV="${1:-dev}"
export TTB_ENV="$ENV"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

MODEL_LOG="$LOG_DIR/model_server.log"
SERVER_LOG="$LOG_DIR/server.log"
NGROK_LOG="$LOG_DIR/ngrok.log"
PID_FILE="$LOG_DIR/pids.txt"

# ── helpers ─────────────────────────────────────────────────────────────────

die()  { echo "[error] $*" >&2; exit 1; }
info() { echo "[start.sh] $*"; }

cleanup() {
    info "Shutting down..."
    if [[ -f "$PID_FILE" ]]; then
        while read -r pid; do
            kill "$pid" 2>/dev/null || true
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    info "Done."
}
trap cleanup EXIT INT TERM

# ── check dependencies ───────────────────────────────────────────────────────

command -v python3 >/dev/null || die "python3 not found"
command -v ngrok   >/dev/null || die "ngrok not found — run: pip install ngrok  or  install from https://ngrok.com/download"

# Warn if ngrok authtoken is not set
if ! ngrok config check 2>&1 | grep -q "authtoken"; then
    echo ""
    echo "  ⚠  ngrok authtoken not configured."
    echo "     Get your free token at: https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "     Then run:  ngrok config add-authtoken <your-token>"
    echo ""
fi

# ── start model inference server ─────────────────────────────────────────────

info "Starting model_server (TTB_ENV=$ENV)..."
python3 "$SCRIPT_DIR/src/model_server.py" >"$MODEL_LOG" 2>&1 &
MODEL_PID=$!
echo "$MODEL_PID" > "$PID_FILE"
info "model_server PID=$MODEL_PID  log=$MODEL_LOG"

# Wait for model server to be ready (up to 3 minutes for model load)
info "Waiting for model_server to become ready..."
for i in $(seq 1 90); do
    if curl -sf "http://localhost:9009/" >/dev/null 2>&1; then
        info "model_server is ready."
        break
    fi
    if ! kill -0 "$MODEL_PID" 2>/dev/null; then
        die "model_server exited unexpectedly. Check $MODEL_LOG"
    fi
    sleep 2
done

# ── start main application server ────────────────────────────────────────────

info "Starting application server (TTB_ENV=$ENV)..."
python3 "$SCRIPT_DIR/src/server.py" >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" >> "$PID_FILE"
info "server PID=$SERVER_PID  log=$SERVER_LOG"

# Wait for app server to be ready
for i in $(seq 1 15); do
    if curl -sf "http://localhost:8080/" >/dev/null 2>&1; then
        info "Application server is ready."
        break
    fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        die "Application server exited unexpectedly. Check $SERVER_LOG"
    fi
    sleep 1
done

# ── start ngrok tunnel ───────────────────────────────────────────────────────

info "Starting ngrok tunnel for http://localhost:8080..."
ngrok http 8080 --log "$NGROK_LOG" --log-format json &
NGROK_PID=$!
echo "$NGROK_PID" >> "$PID_FILE"

# Extract public URL from ngrok API (give it a moment to start)
sleep 3
PUBLIC_URL=$(curl -sf http://localhost:4040/api/tunnels 2>/dev/null \
    | python3 -c "import sys,json; t=json.load(sys.stdin)['tunnels']; print(next(t['public_url'] for t in t if t['proto']=='https'), end='')" \
    2>/dev/null || true)

echo ""
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│  TTB COLA Label Review is running                            │"
echo "├──────────────────────────────────────────────────────────────┤"
if [[ -n "$PUBLIC_URL" ]]; then
echo "│  Public URL  : $PUBLIC_URL"
else
echo "│  Public URL  : check http://localhost:4040 (ngrok dashboard)  │"
fi
echo "│  Local URL   : http://localhost:8080                          │"
echo "│  Environment : $ENV                                            │"
echo "│  ngrok UI    : http://localhost:4040                          │"
echo "├──────────────────────────────────────────────────────────────┤"
echo "│  Logs        : logs/model_server.log                          │"
echo "│                logs/server.log                                │"
echo "│                logs/ngrok.log                                 │"
echo "├──────────────────────────────────────────────────────────────┤"
echo "│  Press Ctrl+C to stop all processes                          │"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""

# Keep running until interrupted
wait
