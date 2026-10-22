#!/usr/bin/env bash
#
# Runs ONE heavy command inside its own cgroup with a memory and time limit, so a runaway
# test run / build cannot take the whole machine (editor, agents, desktop) down.
# The dev machine has 14 GB RAM and also runs other projects' heavy slices (e.g. slaydx-heavy.slice).
#
# Two layers:
#   1. vakant3-heavy.slice — shared ceiling for ALL heavy work in this repo (lead + agents): MemoryMax=4G.
#      On overflow the OOM killer reaps only processes inside the slice.
#   2. Per command scope: MemoryMax (default 3G) and a KILL timeout (default 900 s).
#
# Usage:
#   scripts/heavy.sh pytest
#   scripts/heavy.sh pytest tests/test_e2e_flow.py
#   scripts/heavy.sh -m 2G -t 600 bash -c 'cd webapp/frontend && npm run build'
#
# Rules (see CLAUDE.md "Heavy commands"): the full pytest suite, `npm run build`, `tsc -b` and ops/loadtest.py
# run ONLY through this script; prefer single test files; at most 2 heavy commands at a time (agents count).
set -euo pipefail

MEM="${HEAVY_MEM:-3G}"
T="${HEAVY_TIMEOUT:-900}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m) MEM="$2"; shift 2 ;;
    -t) T="$2"; shift 2 ;;
    --) shift; break ;;
    *) break ;;
  esac
done
if [[ $# -eq 0 ]]; then
  echo "usage: scripts/heavy.sh [-m 3G] [-t 900] <command...>" >&2
  exit 2
fi

SLICE=vakant3-heavy.slice
# Shared ceiling (idempotent).
systemctl --user set-property "$SLICE" MemoryMax=4G MemorySwapMax=512M >/dev/null 2>&1 || true

# Vite/tsc: bound the Node heap so overflow is a clear error, not an OOM kill.
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=1536}"

if command -v systemd-run >/dev/null 2>&1; then
  exec systemd-run --user --scope --quiet --slice="$SLICE" \
    -p MemoryMax="$MEM" -p MemorySwapMax=256M \
    timeout -s KILL "$T" "$@"
else
  # No systemd (CI, container): at least a time limit.
  exec timeout -s KILL "$T" "$@"
fi
