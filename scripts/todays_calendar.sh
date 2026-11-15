#!/usr/bin/env bash
# todays_calendar.sh — dump today's events from the user's Exchange work calendar
# as clean, parseable records for the morning-brief skill to classify.
#
# Reads only the Exchange work calendar named "Calendar" (override with CAL_NAME)
# via EventKit/icalBuddy. Read-only.
# Strips the Microsoft Teams join boilerplate from notes so the classifier
# gets just title, time, attendees, location, and the human part of the note.
#
# Usage:
#   scripts/todays_calendar.sh            # today
#   scripts/todays_calendar.sh +2         # today through 2 days ahead (testing)
#
# Output: one "===EVENT===" record per event, or "NO_EVENTS" if the day is clear.

set -euo pipefail

ICALBUDDY="${ICALBUDDY:-/opt/homebrew/bin/icalBuddy}"
CAL_NAME="${CAL_NAME:-Calendar}"
RANGE="eventsToday"
if [[ "${1:-}" =~ ^\+[0-9]+$ ]]; then
  RANGE="eventsToday${1}"
fi

if [[ ! -x "$ICALBUDDY" ]]; then
  echo "ERROR: icalBuddy not found at $ICALBUDDY" >&2
  exit 1
fi

# An unreadable calendar (missing Calendars permission for the host app) makes
# icalBuddy print "No calendars" and return nothing, which must not be read as a
# clear day. Fail loudly when the work calendar isn't visible.
if ! "$ICALBUDDY" calendars 2>&1 | grep -qx "• $CAL_NAME"; then
  echo "CALENDAR_ERROR: calendar \"$CAL_NAME\" not visible to icalBuddy — grant Calendars access to the host app (System Settings → Privacy & Security → Calendars)"
  exit 3
fi

echo "DATE: $(date '+%Y-%m-%d (%A)')"
echo "CALENDAR: $CAL_NAME"
echo ""

# Pull title, datetime, attendees, location, notes. Use a per-event marker and
# a distinctive property separator so post-processing is unambiguous.
raw="$("$ICALBUDDY" \
  -ic "$CAL_NAME" \
  -npn -nc \
  -b "===EVENT===" \
  -ps "| :: |" \
  -iep "datetime,title,attendees,location,notes" \
  -po "datetime,title,attendees,location,notes" \
  "$RANGE" 2>/dev/null || true)"

if [[ -z "${raw// /}" ]]; then
  echo "NO_EVENTS"
  exit 0
fi

# Clean up:
#  - Everything from the Teams boilerplate onward is noise. Cut each note at the
#    first long underscore run OR "Microsoft Teams meeting" / "Join:" marker.
#  - Collapse whitespace runs; keep records compact.
printf '%s\n' "$raw" | /usr/bin/awk '
  BEGIN { RS="===EVENT==="; FS="\n" }
  {
    block=$0
    # trim leading/trailing whitespace of the whole block
    gsub(/^[ \t\r\n]+|[ \t\r\n]+$/, "", block)
    if (block=="") next
    # Kill Teams boilerplate: drop from the first separator/join marker onward.
    # Markers: a run of 6+ underscores, "Microsoft Teams meeting", "Join:",
    # "________", "Need help?", "Dial in by phone".
    idx = match(block, /_{6,}|Microsoft Teams meeting|Join: https|Need help\?|Dial in by phone|Phone conference ID/)
    if (idx > 0) block = substr(block, 1, idx-1)
    # collapse 3+ newlines to 2, trailing space
    gsub(/[ \t]+\n/, "\n", block)
    gsub(/\n{3,}/, "\n", block)
    gsub(/[ \t\r\n]+$/, "", block)
    print "===EVENT==="
    print block
  }
'
echo "===END==="
