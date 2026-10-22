#!/usr/bin/env bash
# Pull-based auto-deploy (cron, every 2 min, root). CI force-pushes one commit per green master push to the `deploy`
# branch: the source tree + built webapp/frontend/dist + RELEASE (the source sha). This script ships a new release:
#   snapshot current code -> DB backup -> rsync -> pip install (only if requirements.txt changed) -> restart -> health.
# A failed health check restores the snapshot, restarts, marks the release failed (not retried) and alerts ADMIN_IDS.
#
#   ops/auto_deploy.sh            normal run (cron)
#   ops/auto_deploy.sh --force    redeploy the current release even if it is already live or marked failed
#   touch /home/vakant/.deploy/auto-deploy.disabled    kill switch (cron runs become no-ops)
#
# Never touches data/ (DB, uploads, backups), .env or .venv. Like deploy_safe.sh it does not delete server files.
set -euo pipefail

# Overridable only for the local sandbox test; production uses the defaults.
ROOT=${VAKANT_ROOT:-/home/vakant}
STATE=$ROOT/.deploy
REPO=$STATE/release
PREV=$STATE/prev
REMOTE=${VAKANT_DEPLOY_REMOTE:-https://github.com/khusinboev/vakant3.git}
BRANCH=deploy
PY=${VAKANT_PY:-$ROOT/.venv/bin/python}
FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

log() { echo "$(date '+%F %T') $*"; }

notify() {
  local token admins id
  token=$(grep '^TOKEN=' "$ROOT/.env" | cut -d= -f2- || true)
  admins=$(grep '^ADMIN_IDS=' "$ROOT/.env" | cut -d= -f2- | tr ',' ' ' || true)
  [ -n "$token" ] || return 0
  for id in $admins; do
    curl -s -m 8 -o /dev/null "https://api.telegram.org/bot$token/sendMessage" \
      --data-urlencode "chat_id=$id" --data-urlencode "text=$1" || true
  done
}

healthy() {
  local i
  for i in $(seq 1 30); do
    if curl -fs -m 3 http://localhost:8001/api/health >/dev/null; then
      sleep 3  # the bot must survive its startup (migrations, polling)
      systemctl is-active --quiet vakant-api && systemctl is-active --quiet vakant-bot && return 0
      return 1
    fi
    sleep 1
  done
  return 1
}

# Inside `if` conditions `set -e` is off, so every step returns its own failure.
sync_code() {  # $1 = source dir (release checkout or snapshot)
  rsync -rlptc \
    --exclude '.git' --exclude '.github' --exclude '.env' --exclude '.env.*' --exclude '.venv' --exclude '.deploy' \
    --exclude 'data' --exclude '__pycache__' --exclude 'node_modules' --exclude 'webapp/frontend/dist' \
    --exclude 'src/database/database.sqlite3' \
    "$1/" "$ROOT/" || return 1
  rsync -rlptc --delete "$1/webapp/frontend/dist/" "$ROOT/webapp/frontend/dist/" || return 1
}

pip_if_changed() {
  local want have
  want=$(sha256sum "$ROOT/requirements.txt" | cut -d' ' -f1)
  have=$(cat "$STATE/requirements.sha256" 2>/dev/null || true)
  if [ "$want" != "$have" ]; then
    log "requirements.txt changed: pip install"
    "$PY" -m pip install -q -r "$ROOT/requirements.txt" || return 1
    echo "$want" > "$STATE/requirements.sha256"
  fi
}

mkdir -p "$STATE"
exec 9>"$STATE/lock"
flock -n 9 || exit 0
if [ -e "$STATE/auto-deploy.disabled" ] && [ "$FORCE" = 0 ]; then exit 0; fi

remote_head=$(git ls-remote "$REMOTE" "refs/heads/$BRANCH" | cut -f1)
[ -n "$remote_head" ] || { log "no $BRANCH branch on origin"; exit 0; }
if [ ! -d "$REPO/.git" ]; then
  git clone -q --depth 1 --branch "$BRANCH" "$REMOTE" "$REPO"
elif [ "$(git -C "$REPO" rev-parse HEAD)" != "$remote_head" ]; then
  git -C "$REPO" fetch -q --depth 1 origin "$BRANCH"
  git -C "$REPO" reset -q --hard FETCH_HEAD
fi

new=$(cat "$REPO/RELEASE")
cur=$(cat "$STATE/current" 2>/dev/null || echo none)
failed=$(cat "$STATE/failed" 2>/dev/null || echo none)
if [ "$FORCE" = 0 ] && { [ "$new" = "$cur" ] || [ "$new" = "$failed" ]; }; then exit 0; fi
test -f "$REPO/webapp/frontend/dist/index.html" || { log "release $new has no dist"; exit 1; }

log "deploying ${new:0:7} (live: ${cur:0:7})"

# 1. Snapshot the live code (incl. dist) for rollback.
rsync -a --delete --exclude 'data' --exclude '.venv' --exclude '.deploy' --exclude '.git' --exclude '.env' --exclude '.env.*' \
  --exclude '__pycache__' "$ROOT/" "$PREV/"

# 2. DB backup (sqlite backup API, safe under WAL); keep the newest 10.
ts=$(date +%Y%m%d%H%M%S)
bak="$ROOT/data/backups/predeploy_${ts}_${cur:0:7}_to_${new:0:7}.sqlite3"
mkdir -p "$ROOT/data/backups"
"$PY" - "$ROOT/data/database.sqlite3" "$bak" <<'PY'
import sqlite3, sys
s = sqlite3.connect(sys.argv[1]); d = sqlite3.connect(sys.argv[2])
with d:
    s.backup(d)
s.close(); d.close()
PY
gzip -f "$bak"
ls -1t "$ROOT"/data/backups/predeploy_*.sqlite3.gz 2>/dev/null | tail -n +11 | xargs -r rm -f

# 3–5. Ship, restart, verify.
if sync_code "$REPO" && pip_if_changed && systemctl restart vakant-api vakant-bot && healthy; then
  echo "$new" > "$STATE/current"
  rm -f "$STATE/failed"
  log "ok ${new:0:7}"
  notify "✅ vakant3 deploy ${new:0:7}"
  exit 0
fi

log "FAILED ${new:0:7}: rolling back to ${cur:0:7}"
echo "$new" > "$STATE/failed"
sync_code "$PREV"
pip_if_changed || true
systemctl restart vakant-api vakant-bot || true
if healthy; then
  notify "❌ vakant3 deploy ${new:0:7} yiqildi, ${cur:0:7} ga qaytarildi. Log: /var/log/vakant-deploy.log"
else
  notify "🔥 vakant3 deploy ${new:0:7} yiqildi va qaytarish ham ishlamadi. Darhol tekshiring: /var/log/vakant-deploy.log"
fi
exit 1
