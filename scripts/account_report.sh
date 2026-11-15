#!/bin/zsh
# Runs the account usage report for every partner ID in config.local.json
# (account_report.partner_ids).
# Usage:
#   ./scripts/account_report.sh                    # uses 1Password KS if stored
#   ./scripts/account_report.sh --ks "ks_string"   # use a KS you grabbed from the management console
cd "$(dirname "$0")/.." || exit 1

KS_ARG=()
if [[ "$1" == "--ks" && -n "$2" ]]; then
  KS_ARG=(--ks "$2")
  echo "✓ Using provided KS."
else
  # Try to pull a saved KS from 1Password (secure note titled "Platform KS")
  SAVED_KS=$(op item get "Platform KS" --fields label=credential 2>/dev/null)
  if [[ -n "$SAVED_KS" ]]; then
    KS_ARG=(--ks "$SAVED_KS")
    echo "✓ KS retrieved from 1Password."
  else
    echo "No KS found. Get one from the video platform's management console:"
    echo "  DevTools → Network → any platform API request → Payload → copy ks= value"
    echo "Then run: ./scripts/account_report.sh --ks \"<paste here>\""
    exit 1
  fi
fi

python3 scripts/pull_account_report.py \
  "${KS_ARG[@]}" \
  --all \
  --csv ~/Downloads/account_usage_monthly_$(date +%F).csv
