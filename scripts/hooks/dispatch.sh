#!/usr/bin/env bash
# Universal hook dispatcher.
# Registered per event in .claude/settings.json.
# Runs every executable *.sh in scripts/hooks/<event>/ in lexicographic order.
# Add an automation: drop a script in the directory, chmod +x. No restart needed.
# Handler failures are logged, never fatal.

set -uo pipefail

CC_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
source "$CC_DIR/scripts/lib/log.sh"

EVENT="${1:-}"
[ -n "$EVENT" ] || { log_json warn "hook_dispatch_no_event"; exit 0; }

HOOK_DIR="$CC_DIR/scripts/hooks/$EVENT"
[ -d "$HOOK_DIR" ] || exit 0

shopt -s nullglob
handlers=( "$HOOK_DIR"/*.sh )
shopt -u nullglob
[ ${#handlers[@]} -gt 0 ] || exit 0

PAYLOAD="$(cat 2>/dev/null || true)"

for script in "${handlers[@]}"; do
  [ -x "$script" ] || continue
  if ! printf '%s' "$PAYLOAD" | "$script" "$EVENT"; then
    log_json warn "hook_handler_failed" "event=$EVENT" "script=$(basename "$script")"
  fi
done
