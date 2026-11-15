#!/usr/bin/env bash
set -euo pipefail

CC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ERRORS=0

check() {
  if ! command -v "$1" &>/dev/null; then
    echo "MISSING: $1 — $2"
    return 1
  fi
  return 0
}

if ! command -v uv &>/dev/null; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

check git "install via: brew install git"                   || ((ERRORS++))
check gh  "install via: brew install gh && gh auth login"   || ((ERRORS++))
check op  "install via: brew install 1password-cli"         || ((ERRORS++))
check uv  "install failed — see https://docs.astral.sh/uv/" || ((ERRORS++))

if [ "$ERRORS" -gt 0 ]; then
  echo ""
  echo "$ERRORS missing prerequisite(s). Install them and re-run."
  exit 1
fi

MCP_PORT=19234
LOGS_DIR="$CC_DIR/logs"
mkdir -p "$LOGS_DIR"

if curl -so /dev/null "http://localhost:$MCP_PORT/" 2>/dev/null; then
  echo "MCP server already running on port $MCP_PORT"
else
  if [ -f "$CC_DIR/mcp-server/server.py" ]; then
    echo "Starting MCP server..."
    date +%Y-%m-%dT%H-%M-%S > "$LOGS_DIR/.session-id"
    cd "$CC_DIR/mcp-server"
    nohup uv run python server.py 2>"$LOGS_DIR/mcp-server.log" >/dev/null &
    echo $! > "$CC_DIR/.mcp-server.pid"
    cd "$CC_DIR"
    for i in 1 2 3 4 5 6 7 8 9 10; do
      curl -so /dev/null "http://localhost:$MCP_PORT/" 2>/dev/null && break
      sleep 1
    done
    curl -so /dev/null "http://localhost:$MCP_PORT/" 2>/dev/null \
      || echo "WARN: MCP server failed to start — check logs/mcp-server.log"
  else
    echo "WARN: MCP server not yet configured — run setup to wire credentials"
  fi
fi

[ -f "$CC_DIR/config.local.json" ] \
  || echo "CONFIG_MISSING: config.local.json not found. Create it with: {\"sf_instance\": \"your-instance.my.salesforce.com\", \"sf_username\": \"your@email.com\", \"sf_user_id\": \"005XXXXXXXXXXXXXXX\"}"

# ── Salesforce auth check ──────────────────────────────────────────────────────
# Identity comes from config.local.json (gitignored) — never hardcoded, so this
# script is portable across users.
_cfg() { python3 -c "import json,sys; print(json.load(open('$CC_DIR/config.local.json')).get('$1',''))" 2>/dev/null; }
SF_USERNAME="$(_cfg sf_username)"
SF_INSTANCE="$(_cfg sf_instance)"
if ! command -v sf &>/dev/null; then
  echo "SF_AUTH: MISSING — install SF CLI: brew install sf"
elif [ -z "$SF_USERNAME" ]; then
  echo "SF_AUTH: SKIPPED — set sf_username in config.local.json"
else
  if sf data query --query "SELECT Id FROM Account LIMIT 1" \
       --target-org "$SF_USERNAME" --json &>/dev/null; then
    echo "SF_AUTH: OK ($SF_USERNAME)"
  else
    echo "SF_AUTH: session expired — re-authenticating..."
    sf org login web --instance-url "https://${SF_INSTANCE:-login.salesforce.com}"
    echo "SF_AUTH: OK"
  fi
fi

echo ""
echo "=== Account Command Center — Session Ready ==="
echo "  Skills: /business-review  /account-forecast  /sf-forecast-update"
echo ""
echo "MODEL: prefer an Opus or Sonnet model (/model) for these skills"
