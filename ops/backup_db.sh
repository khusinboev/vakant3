#!/usr/bin/env bash
# Daily SQLite backup with 14-day retention (uses the sqlite backup API, safe under WAL).
set -euo pipefail
SRC=/home/vakant/data/database.sqlite3
DST_DIR=/home/vakant/data/backups
mkdir -p "$DST_DIR"
DST="$DST_DIR/database_$(date +%Y%m%d).sqlite3"
/home/vakant/.venv/bin/python - "$SRC" "$DST" <<PY
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
s = sqlite3.connect(src); d = sqlite3.connect(dst)
with d: s.backup(d)
s.close(); d.close()
PY
gzip -f "$DST"
find "$DST_DIR" -name "database_*.sqlite3.gz" -mtime +14 -delete
