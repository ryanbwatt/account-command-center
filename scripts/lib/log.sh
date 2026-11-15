#!/usr/bin/env bash
# Shared structured logging. Source it: source "$CC_DIR/scripts/lib/log.sh"
# Usage: log_json <level> <event> [key=value ...]

_LOG_DIR="${CC_DIR:?CC_DIR must be set}/logs"
_LOG_FILE="$_LOG_DIR/scripts.log"
_SESSION_FILE="$_LOG_DIR/.session-id"
_LOG_SCRIPT="$(basename "${BASH_SOURCE[1]}" .sh)"

mkdir -p "$_LOG_DIR"

LOG_SESSION="unknown"
[ -f "$_SESSION_FILE" ] && LOG_SESSION="$(cat "$_SESSION_FILE")"

log_json() {
  local level="$1" event="$2"; shift 2
  local extras=""
  for pair in "$@"; do
    local key="${pair%%=*}" val="${pair#*=}"
    extras="$extras, \"$key\": \"$val\""
  done
  local ts; ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '{"ts":"%s","level":"%s","event":"%s","session":"%s","script":"%s"%s}\n' \
    "$ts" "$level" "$event" "$LOG_SESSION" "$_LOG_SCRIPT" "$extras" >> "$_LOG_FILE"
}
