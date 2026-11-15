#!/usr/bin/env bash
# job_alert.sh — make a scheduled-job failure loud: macOS notification with sound + email to the user.
#
#   job_alert.sh <job> <reason> <log-path>
#
# The email goes through send_self_brief.sh, whose recipient is hard-locked to the user (config user_email).
# Never fails the caller: an alert that can't be emailed still shows the notification.

job="$1"; reason="${2:-unknown error}"; log="${3:-}"
dir="$(cd "$(dirname "$0")" && pwd)"

/usr/bin/osascript -e 'on run argv' \
  -e 'display notification (item 2 of argv) with title ("FAILED: " & item 1 of argv) sound name "Basso"' \
  -e 'end run' "$job" "$reason" 2>/dev/null

body="$(mktemp -t job_alert).html"
{
  echo "<div><b>$job</b> failed at $(date '+%a %b %-d, %-I:%M %p').</div><div><br></div>"
  echo "<div>Reason: $(printf '%s' "$reason" | sed 's/&/\&amp;/g; s/</\&lt;/g')</div><div><br></div>"
  echo "<div>Log: $log</div><div><br></div><div>Last lines:</div><pre>"
  [[ -f "$log" ]] && tail -15 "$log" | sed 's/&/\&amp;/g; s/</\&lt;/g'
  echo "</pre>"
} >"$body"
"$dir/send_self_brief.sh" "Job failed: $job" "$body" >/dev/null 2>&1 || echo "job_alert: email failed (notification shown)" >&2
rm -f "$body"
