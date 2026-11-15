#!/usr/bin/env bash
# send_self_brief.sh — send the morning account brief to the user, and ONLY to the user.
#
# SECURITY / GUARDRAIL (approved by the user, scoped exception to the CLAUDE.md
# "never send email without approval" rule):
#   * The recipient is HARD-LOCKED to `user_email` in config.local.json (the
#     user's own address). There is no argument, env var, or flag that changes
#     who this emails. This script is a
#     self-send only — it physically cannot deliver to anyone else.
#   * It is meant to be called only by the weekday morning-brief automation.
#   * Everything else in the hub stays draft-and-approve.
#
# Usage:
#   send_self_brief.sh "<subject>" <path-to-html-body-file>            # sends
#   send_self_brief.sh "<subject>" <path-to-html-body-file> --draft    # opens a
#       draft in Outlook without sending (used for testing / dry runs)
#
# The HTML body is read from a file (not passed inline) so large emails don't
# hit shell-escaping issues.

set -euo pipefail

# The only address, ever: read from the gitignored config, never from args/env.
_cc_dir="$(cd "$(dirname "$0")/.." && pwd)"
LOCKED_RECIPIENT="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('user_email',''))" "$_cc_dir/config.local.json" 2>/dev/null || true)"
readonly LOCKED_RECIPIENT
if [[ ! "$LOCKED_RECIPIENT" =~ ^[^@[:space:],\;]+@[^@[:space:],\;]+$ ]]; then
  echo "ERROR: user_email missing or not a single address in config.local.json" >&2; exit 2
fi

subject="${1:-}"
body_path="${2:-}"
mode="${3:-send}"

if [[ -z "$subject" ]]; then
  echo "ERROR: subject (arg 1) is required" >&2; exit 2
fi
if [[ -z "$body_path" || ! -f "$body_path" ]]; then
  echo "ERROR: body HTML file (arg 2) missing or not a file: '$body_path'" >&2; exit 2
fi
if [[ ! -s "$body_path" ]]; then
  echo "ERROR: body HTML file is empty: '$body_path'" >&2; exit 2
fi

do_send="true"
if [[ "$mode" == "--draft" ]]; then
  do_send="false"
fi

abs_body="$(cd "$(dirname "$body_path")" && pwd)/$(basename "$body_path")"

/usr/bin/osascript - "$subject" "$abs_body" "$do_send" "$LOCKED_RECIPIENT" <<'APPLESCRIPT'
on run argv
	set theSubject to item 1 of argv
	set theBodyPath to item 2 of argv
	set doSend to (item 3 of argv is "true")
	set theRecipient to item 4 of argv
	set theHTML to (read (POSIX file theBodyPath) as «class utf8»)
	tell application "Microsoft Outlook"
		set msg to make new outgoing message with properties {subject:theSubject, content:theHTML}
		make new to recipient at msg with properties {email address:{address:theRecipient}}
		if doSend then
			send msg
		else
			open msg
		end if
	end tell
end run
APPLESCRIPT

if [[ "$do_send" == "true" ]]; then
  echo "SENT: \"$subject\" -> $LOCKED_RECIPIENT"
else
  echo "DRAFT opened in Outlook (not sent): \"$subject\" -> $LOCKED_RECIPIENT"
fi
