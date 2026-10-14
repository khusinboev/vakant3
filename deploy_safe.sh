#!/usr/bin/env bash
# Manual deploy (fallback). The normal path is push to master -> CI -> `deploy` branch -> server cron
# (ops/auto_deploy.sh); see .claude/deploy.md. This script ships the LOCAL working tree, so it refuses a dirty one
# (ALLOW_DIRTY=1 overrides).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER="root@193.187.129.197"  # migrated 2026-09-30; host is shared with other projects
REMOTE_ROOT="/home/vakant"

cd "$SCRIPT_DIR"
if [ -n "$(git status --porcelain)" ] && [ "${ALLOW_DIRTY:-0}" != 1 ]; then
  echo "Working tree is not clean; commit first (or ALLOW_DIRTY=1)." >&2
  exit 1
fi

# One SSH connection for every step below.
CTL="$(mktemp -d)/ssh-%r@%h:%p"
SSH_OPTS=(-o ControlMaster=auto -o ControlPath="$CTL" -o ControlPersist=60)
trap 'ssh "${SSH_OPTS[@]}" -O exit "$SERVER" 2>/dev/null || true' EXIT
remote() { ssh "${SSH_OPTS[@]}" "$SERVER" "$@"; }

echo "[1/6] Build frontend"
(cd webapp/frontend && npm run build)

echo "[2/6] Pre-deploy DB backup"
remote "$REMOTE_ROOT/backup_db.sh"

echo "[3/6] Sync frontend dist and project code (DB excluded)"
rsync -az --delete -e "ssh ${SSH_OPTS[*]}" webapp/frontend/dist/ "$SERVER:$REMOTE_ROOT/webapp/frontend/dist/"
rsync -azc -e "ssh ${SSH_OPTS[*]}" \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude '.git' \
  --exclude '.github' \
  --exclude '.claude' \
  --exclude '.deploy' \
  --exclude '.venv' \
  --exclude 'data' \
  --exclude 'webapp/frontend/node_modules' \
  --exclude 'webapp/frontend/dist' \
  --exclude 'src/database/database.sqlite3' \
  ./ "$SERVER:$REMOTE_ROOT/"

echo "[4/6] Ensure persistent DB path and WEBAPP_SECRET (API refuses to start without it)"
remote "mkdir -p $REMOTE_ROOT/data && [ -f $REMOTE_ROOT/data/database.sqlite3 ] || cp $REMOTE_ROOT/src/database/database.sqlite3 $REMOTE_ROOT/data/database.sqlite3"
remote "grep -q '^DB_PATH=' $REMOTE_ROOT/.env && sed -i 's|^DB_PATH=.*|DB_PATH=$REMOTE_ROOT/data/database.sqlite3|' $REMOTE_ROOT/.env || echo 'DB_PATH=$REMOTE_ROOT/data/database.sqlite3' >> $REMOTE_ROOT/.env"
remote "grep -q '^WEBAPP_SECRET=' $REMOTE_ROOT/.env || echo \"WEBAPP_SECRET=\$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')\" >> $REMOTE_ROOT/.env"

echo "[5/6] Install Python deps only if requirements.txt changed (state shared with ops/auto_deploy.sh)"
remote "cd $REMOTE_ROOT && mkdir -p .deploy && want=\$(sha256sum requirements.txt | cut -d' ' -f1) && \
  if [ \"\$want\" != \"\$(cat .deploy/requirements.sha256 2>/dev/null)\" ]; then \
    .venv/bin/python -m pip install -q -r requirements.txt && echo \"\$want\" > .deploy/requirements.sha256; \
  else echo 'unchanged, skipped'; fi"

echo "[6/6] Restart services & health check"
remote "systemctl restart vakant-api vakant-bot && sleep 3 && systemctl is-active vakant-api && systemctl is-active vakant-bot && curl -fs http://localhost:8001/api/health"

echo
echo "Done."
