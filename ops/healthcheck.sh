#!/usr/bin/env bash
# Every 5 min: if the API health, a service, the disk or the DB state is bad, alert admins via
# the bot once per incident, and once more when everything is back to normal.
#
# DB checks (read-only: sqlite URI mode=ro, never writes the live DB):
#   - a broadcast in status 'running' with no progress for > HC_BROADCAST_STALL_MIN minutes
#     (progress = newest of started_at and the targets' sent_at / claimed_at / last_attempt_at)
#   - more than HC_ERRORS_MAX error_log rows in the last 10 minutes
#   - the DB file larger than HC_DB_MAX_BYTES
#
# Every path and threshold can be overridden from the environment (used by the tests).
# `healthcheck.sh --db-only` prints the DB problem tokens (empty = fine) and exits: no alert,
# no state change, no curl/systemctl — handy for a manual check.
set -u
ENV=${VAKANT_ENV:-/home/vakant/.env}
STATE=${VAKANT_HEALTH_STATE:-/home/vakant/data/.health_state}
DB=${VAKANT_DB:-/home/vakant/data/database.sqlite3}
PY=${VAKANT_PY:-/home/vakant/.venv/bin/python}
HEALTH_URL=${VAKANT_HEALTH_URL:-http://localhost:8001/api/health}
HC_BROADCAST_STALL_MIN=${HC_BROADCAST_STALL_MIN:-30}
HC_ERRORS_MAX=${HC_ERRORS_MAX:-50}
HC_DB_MAX_BYTES=${HC_DB_MAX_BYTES:-1073741824}

db_problems() {
  "$PY" - "$DB" "$HC_BROADCAST_STALL_MIN" "$HC_ERRORS_MAX" "$HC_DB_MAX_BYTES" <<'PY' 2>/dev/null || echo "db_check_failed"
import os, sqlite3, sys, time, urllib.parse
db, stall_min, errors_max, max_bytes = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
out = []
try:
    size = os.path.getsize(db)
except OSError:
    print("db_missing")
    sys.exit(0)
if size > max_bytes:
    out.append(f"db_size_{size // (1024 * 1024)}MB")
try:
    conn = sqlite3.connect(f"file:{urllib.parse.quote(os.path.abspath(db))}?mode=ro", uri=True, timeout=5)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    now = int(time.time())
    if {"broadcasts", "broadcast_targets"} <= tables:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(broadcast_targets)")}
        marks = [c for c in ("sent_at", "claimed_at", "last_attempt_at") if c in cols]
        running = conn.execute(
            "SELECT id, COALESCE(started_at, created_at, 0) FROM broadcasts WHERE status = 'running'"
        ).fetchall()
        for bid, started in running:
            last = int(started or 0)
            if marks:
                sql = "SELECT " + ", ".join(f"MAX({c})" for c in marks) + " FROM broadcast_targets WHERE broadcast_id = ?"
                last = max([last] + [int(v) for v in conn.execute(sql, (bid,)).fetchone() if v])
            if now - last > stall_min * 60:
                out.append(f"broadcast_{bid}_stalled_{(now - last) // 60}min")
    if "error_log" in tables:
        n = conn.execute("SELECT COUNT(*) FROM error_log WHERE created_at >= ?", (now - 600,)).fetchone()[0]
        if n > errors_max:
            out.append(f"errors_{n}_in_10min")
    conn.close()
except sqlite3.Error:
    out.append("db_unreadable")
print(" ".join(out))
PY
}

if [ "${1:-}" = "--db-only" ]; then
  db_problems
  exit 0
fi

TOKEN=$(grep "^TOKEN=" "$ENV" | cut -d= -f2-)
ADMINS=$(grep "^ADMIN_IDS=" "$ENV" | cut -d= -f2- | tr "," " ")
PROBLEMS=""
curl -fs -m 8 "$HEALTH_URL" >/dev/null || PROBLEMS="$PROBLEMS api_health"
for s in vakant-api vakant-bot; do systemctl is-active --quiet "$s" || PROBLEMS="$PROBLEMS $s"; done
USED=$(df --output=pcent / | tail -1 | tr -dc 0-9); [ "$USED" -ge 92 ] && PROBLEMS="$PROBLEMS disk_${USED}%"
DBP=$(db_problems)
[ -n "$DBP" ] && PROBLEMS="$PROBLEMS $DBP"
PREV=$(cat "$STATE" 2>/dev/null || echo ok)
if [ -n "$PROBLEMS" ]; then
  if [ "$PREV" = "ok" ]; then
    for id in $ADMINS; do curl -s -m 8 -o /dev/null "https://api.telegram.org/bot$TOKEN/sendMessage" --data-urlencode "chat_id=$id" --data-urlencode "text=⚠️ vakant3 muammo: $PROBLEMS ($(date +%H:%M))"; done
  fi
  echo "bad" > "$STATE"
else
  if [ "$PREV" != "ok" ]; then
    for id in $ADMINS; do curl -s -m 8 -o /dev/null "https://api.telegram.org/bot$TOKEN/sendMessage" --data-urlencode "chat_id=$id" --data-urlencode "text=✅ vakant3 tiklandi ($(date +%H:%M))"; done
  fi
  echo "ok" > "$STATE"
fi
