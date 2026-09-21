#!/usr/bin/env bash
# Every 5 min: if the API health or a service is down, alert admins via the bot once per incident.
set -u
ENV=/home/vakant/.env
TOKEN=$(grep "^TOKEN=" "$ENV" | cut -d= -f2-)
ADMINS=$(grep "^ADMIN_IDS=" "$ENV" | cut -d= -f2- | tr "," " ")
STATE=/home/vakant/data/.health_state
PROBLEMS=""
curl -fs -m 8 http://localhost:8001/api/health >/dev/null || PROBLEMS="$PROBLEMS api_health"
for s in vakant-api vakant-bot; do systemctl is-active --quiet "$s" || PROBLEMS="$PROBLEMS $s"; done
USED=$(df --output=pcent / | tail -1 | tr -dc 0-9); [ "$USED" -ge 92 ] && PROBLEMS="$PROBLEMS disk_${USED}%"
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
