#!/usr/bin/env bash
# Proves the newest DB backup can actually be restored: gunzips the newest
# data/backups/*.sqlite3.gz into a temp dir, runs PRAGMA integrity_check and counts
# users / schema_migrations, prints one OK/FAIL line and removes the temp copy.
# Never opens or touches the live DB. Exit code: 0 OK, 1 FAIL.
#
# Overrides (tests / manual runs): VAKANT_BACKUP_DIR, VAKANT_PY, TMPDIR.
set -u
BACKUP_DIR=${VAKANT_BACKUP_DIR:-/home/vakant/data/backups}
PY=${VAKANT_PY:-/home/vakant/.venv/bin/python}

NEWEST=$(ls -1t "$BACKUP_DIR"/*.sqlite3.gz 2>/dev/null | head -n 1)
if [ -z "$NEWEST" ]; then
  echo "FAIL restore_check: no *.sqlite3.gz in $BACKUP_DIR ($(date '+%F %T'))"
  exit 1
fi

WORK=$(mktemp -d "${TMPDIR:-/tmp}/vakant-restore.XXXXXX") || { echo "FAIL restore_check: mktemp"; exit 1; }
trap 'rm -rf "$WORK"' EXIT
COPY="$WORK/restore.sqlite3"

if ! gunzip -c "$NEWEST" > "$COPY" 2>/dev/null; then
  echo "FAIL restore_check: $NEWEST does not gunzip ($(date '+%F %T'))"
  exit 1
fi

"$PY" - "$COPY" "$NEWEST" <<'PY'
import sqlite3, sys, time
copy, name = sys.argv[1], sys.argv[2]
stamp = time.strftime("%Y-%m-%d %H:%M:%S")
try:
    conn = sqlite3.connect(copy)
    integrity = [r[0] for r in conn.execute("PRAGMA integrity_check")]
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    migrations = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    conn.close()
except sqlite3.Error as exc:
    print(f"FAIL restore_check: {name}: {exc} ({stamp})")
    sys.exit(1)
if integrity != ["ok"]:
    print(f"FAIL restore_check: {name}: integrity_check={'; '.join(integrity[:3])} ({stamp})")
    sys.exit(1)
if migrations == 0:
    print(f"FAIL restore_check: {name}: schema_migrations is empty ({stamp})")
    sys.exit(1)
print(f"OK restore_check: {name} integrity=ok users={users} schema_migrations={migrations} ({stamp})")
PY
