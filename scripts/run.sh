#!/usr/bin/env bash
# Run the API server in the background. Usage: scripts/run.sh start|stop|restart|status|logs
set -euo pipefail
cd "$(dirname "$0")/.."

source "${CONDA_ROOT:-$HOME/miniconda3}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-k9x}"

PIDFILE="$PWD/logs/api.pid"
LOG="$PWD/logs/api.log"
mkdir -p logs
HOST="$(sed -n 's/^HOST=//p' .env 2>/dev/null)"; HOST="${HOST:-127.0.0.1}"
PORT="$(sed -n 's/^PORT=//p' .env 2>/dev/null)"; PORT="${PORT:-8077}"

running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

start() {
  running && { echo "already running (pid $(cat "$PIDFILE"))"; return; }
  nohup uvicorn app.main:app --host "$HOST" --port "$PORT" >> "$LOG" 2>&1 &
  echo $! > "$PIDFILE"
  sleep 3
  running && echo "API running on http://$HOST:$PORT (pid $(cat "$PIDFILE"))" || { echo "failed to start:"; tail -20 "$LOG"; exit 1; }
}

stop() {
  running && kill "$(cat "$PIDFILE")" && echo "stopped"
  rm -f "$PIDFILE"
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop; sleep 1; start ;;
  status) running && echo "running (pid $(cat "$PIDFILE"))" || echo "stopped" ;;
  logs) tail -f "$LOG" ;;
  *) echo "usage: $0 start|stop|restart|status|logs"; exit 1 ;;
esac
