#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER="root@194.163.136.239"
REMOTE_ROOT="/home/vakant"

echo "[1/5] Build frontend"
cd "$SCRIPT_DIR/webapp/frontend"
npm run build

echo "[2/5] Sync frontend dist"
rsync -az --delete dist/ "$SERVER:$REMOTE_ROOT/webapp/frontend/dist/"

echo "[3/5] Sync project code (DB excluded)"
cd "$SCRIPT_DIR"
rsync -azc \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'webapp/frontend/node_modules' \
  --exclude 'webapp/frontend/dist' \
  --exclude 'src/database/database.sqlite3' \
  ./ "$SERVER:$REMOTE_ROOT/"

echo "[4/5] Ensure persistent DB path"
ssh "$SERVER" "mkdir -p $REMOTE_ROOT/data && [ -f $REMOTE_ROOT/data/database.sqlite3 ] || cp $REMOTE_ROOT/src/database/database.sqlite3 $REMOTE_ROOT/data/database.sqlite3"
ssh "$SERVER" "grep -q '^DB_PATH=' $REMOTE_ROOT/.env && sed -i 's|^DB_PATH=.*|DB_PATH=$REMOTE_ROOT/data/database.sqlite3|' $REMOTE_ROOT/.env || echo 'DB_PATH=$REMOTE_ROOT/data/database.sqlite3' >> $REMOTE_ROOT/.env"

echo "[4b] Ensure WEBAPP_SECRET exists on server (API refuses to start without it)"
ssh "$SERVER" "grep -q '^WEBAPP_SECRET=' $REMOTE_ROOT/.env || echo \"WEBAPP_SECRET=\$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')\" >> $REMOTE_ROOT/.env"

echo "[4c] Install Python deps (requirements.txt may have changed)"
ssh "$SERVER" "cd $REMOTE_ROOT && .venv/bin/python -m pip install -q -r requirements.txt"

echo "[5/5] Restart services & health check"
ssh "$SERVER" "systemctl restart vakant-api vakant-bot && sleep 3 && systemctl is-active vakant-api && systemctl is-active vakant-bot && curl -s http://localhost:8001/api/health"

echo "Done."
