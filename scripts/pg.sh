#!/usr/bin/env bash
# User-space PostgreSQL for the backend (no sudo needed). Usage: scripts/pg.sh init|start|stop|status|psql
set -euo pipefail
cd "$(dirname "$0")/.."

source "${CONDA_ROOT:-$HOME/miniconda3}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV:-k9x}"

PGDATA="${PGDATA:-$PWD/pgdata}"
PGPORT="${PGPORT:-5433}"
LOG="$PWD/logs/postgres.log"
mkdir -p logs

case "${1:-}" in
  init)
    [ -d "$PGDATA" ] && { echo "already initialised: $PGDATA"; exit 0; }
    PASS="$(python -c 'import secrets; print(secrets.token_hex(16))')"
    PWFILE="$(mktemp)"; trap 'rm -f "$PWFILE"' EXIT
    echo "$PASS" > "$PWFILE"
    initdb -D "$PGDATA" -U k9x --auth=scram-sha-256 --pwfile="$PWFILE" >/dev/null
    cat >> "$PGDATA/postgresql.conf" <<CONF
listen_addresses = '127.0.0.1'
port = $PGPORT
unix_socket_directories = ''
CONF
    pg_ctl -D "$PGDATA" -l "$LOG" -w start
    PGPASSWORD="$PASS" createdb -h 127.0.0.1 -p "$PGPORT" -U k9x k9x
    [ -f .env ] || cp .env.example .env
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://k9x:$PASS@127.0.0.1:$PGPORT/k9x|" .env
    chmod 600 .env
    echo "PostgreSQL ready on 127.0.0.1:$PGPORT, credentials written to .env"
    ;;
  start)  pg_ctl -D "$PGDATA" -l "$LOG" -w start ;;
  stop)   pg_ctl -D "$PGDATA" -m fast stop ;;
  status) pg_ctl -D "$PGDATA" status ;;
  psql)
    PASS="$(sed -n 's|^DATABASE_URL=.*://k9x:\([^@]*\)@.*|\1|p' .env)"
    PGPASSWORD="$PASS" psql -h 127.0.0.1 -p "$PGPORT" -U k9x k9x
    ;;
  *) echo "usage: $0 init|start|stop|status|psql"; exit 1 ;;
esac
