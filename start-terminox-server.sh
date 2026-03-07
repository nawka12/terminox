#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

# Load configuration
# shellcheck source=config.sh
source "$DIR/config.sh"

[[ "$MODEL_PATH"  == /* ]] && MODEL="$MODEL_PATH"   || MODEL="$DIR/$MODEL_PATH"
[[ "$SERVER_PATH" == /* ]] && SERVER="$SERVER_PATH" || SERVER="$DIR/$SERVER_PATH"
LOG="$DIR/ft-server.log"
PID_FILE="$DIR/ft-server.pid"

start() {
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Server already running (PID $(cat "$PID_FILE"))"
        return 1
    fi

    # Build optional flags
    EXTRA_ARGS=()
    [[ -n "${FLASH_ATTN:-}"             ]] && EXTRA_ARGS+=(--flash-attn "$FLASH_ATTN")
    [[ -n "${CACHE_TYPE_K:-}"           ]] && EXTRA_ARGS+=(--cache-type-k "$CACHE_TYPE_K")
    [[ -n "${CACHE_TYPE_V:-}"           ]] && EXTRA_ARGS+=(--cache-type-v "$CACHE_TYPE_V")
    [[ -n "${REASONING_BUDGET:-}"       ]] && EXTRA_ARGS+=(--reasoning-budget "$REASONING_BUDGET")
    [[ -n "${CHAT_TEMPLATE_KWARGS:-}"   ]] && EXTRA_ARGS+=(--chat-template-kwargs "$CHAT_TEMPLATE_KWARGS")
    if [[ -n "${TEMPLATE_PATH:-}" ]]; then
        [[ "$TEMPLATE_PATH" == /* ]] && TMPL="$TEMPLATE_PATH" || TMPL="$DIR/$TEMPLATE_PATH"
        [[ -f "$TMPL" ]] && EXTRA_ARGS+=(--chat-template-file "$TMPL")
    fi
    if [[ -n "${MMPROJ_PATH:-}" ]]; then
        [[ "$MMPROJ_PATH" == /* ]] && MMPROJ="$MMPROJ_PATH" || MMPROJ="$DIR/$MMPROJ_PATH"
        [[ -f "$MMPROJ" ]] && EXTRA_ARGS+=(--mmproj "$MMPROJ")
    fi

    > "$LOG"
    "$SERVER" \
        -m "$MODEL" \
        --ctx-size "$CTX_SIZE" \
        --temp "$TEMP" \
        --top-p "$TOP_P" \
        --top-k "$TOP_K" \
        --min-p "$MIN_P" \
        --presence-penalty "$PRESENCE_PENALTY" \
        --alias "$MODEL_ALIAS" \
        --port "$PORT" \
        "${EXTRA_ARGS[@]}" \
        >> "$LOG" 2>&1 &

    echo $! > "$PID_FILE"
    echo "Starting server (PID $!) on port $PORT..."

    for i in $(seq 1 "$STARTUP_ITERS"); do
        if curl -sf "http://$HOST:$PORT/health" | grep -q '"ok"'; then
            VRAM=""
            if command -v nvidia-smi &>/dev/null; then
                VRAM=" — $(nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader,nounits | awk -F', ' '{print "VRAM: "$1"/"($1+$2)"MiB used"}')"
            fi
            echo "Ready in $((i * STARTUP_SLEEP))s${VRAM}"
            return 0
        fi
        sleep "$STARTUP_SLEEP"
    done

    echo "Timed out waiting for server. Check $LOG"
    return 1
}

stop() {
    if [[ ! -f "$PID_FILE" ]]; then
        echo "No PID file found"
        return 1
    fi
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" && rm -f "$PID_FILE"
        echo "Stopped (PID $PID)"
    else
        echo "Process $PID not running"
        rm -f "$PID_FILE"
    fi
}

status() {
    if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Running (PID $(cat "$PID_FILE"))"
        curl -sf "http://$HOST:$PORT/health" && echo
        if command -v nvidia-smi &>/dev/null; then
            nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader,nounits \
                | awk -F', ' '{print "VRAM: "$1"MiB used, "$2"MiB free"}'
        fi
    else
        echo "Not running"
    fi
}

case "${1:-start}" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 1; start ;;
    status)  status ;;
    logs)    tail -f "$LOG" ;;
    *)       echo "Usage: $0 {start|stop|restart|status|logs}" ;;
esac
