#!/usr/bin/env bash
# Save an HTML draft to the work Exchange Drafts folder via Mail.app (syncs to Outlook).
# Config (config.local.json): mail_account_name = the Mail.app account name;
# email_signature_html = optional HTML signature appended to every draft.
# Never sends. Usage:
#   stage_draft.sh reply <mail_id> <body.html> [--no-sig]              # reply-all in thread, original quoted below
#   stage_draft.sh new "<to,to>" "<subject>" <body.html> [--no-sig]    # new thread
# <mail_id> is the `id` returned by the apple-mail MCP search/get tools.
# body.html is the message body only; the font wrapper and signature are added here.
set -euo pipefail

mode="${1:-}"; shift || true
case "$mode" in
  reply) id="${1:?mail_id}"; body="${2:?body.html}"; sig="${3:-}"; to=""; subject="" ;;
  new)   to="${1:?to}"; subject="${2:?subject}"; body="${3:?body.html}"; sig="${4:-}"; id="" ;;
  *) echo "usage: stage_draft.sh reply <mail_id> <body.html> | new <to> <subject> <body.html> [--no-sig]" >&2; exit 2 ;;
esac
[[ -s "$body" ]] || { echo "ERROR: body file missing or empty: $body" >&2; exit 2; }

font='font-family: Aptos, Arial, Helvetica, sans-serif; font-size: 12pt; color: rgb(0, 0, 0);'
CC_DIR="${CC_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
_cfg() { python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2],''))" "$CC_DIR/config.local.json" "$1" 2>/dev/null; }
acct_name="$(_cfg mail_account_name)"
[[ -n "$acct_name" ]] || { echo "ERROR: mail_account_name missing in config.local.json" >&2; exit 2; }
signature="$(_cfg email_signature_html)"
[[ "$sig" == "--no-sig" ]] && signature=""

html="$(mktemp -t stage_draft)"
trap 'rm -f "$html"' EXIT
{ printf '<div style="%s">' "$font"; cat "$body"; printf '</div>%s' "$signature"; } > "$html"

# Setting html content replaces the whole reply body, quoted original included,
# so rebuild the Outlook-style quoted block from the parent's source and append it.
# ponytail: inline cid: images in the parent won't render in the quote; attach-forward if that matters.
if [[ "$mode" == "reply" ]]; then
  src="$(mktemp -t stage_draft_src)"
  trap 'rm -f "$html" "$src"' EXIT
  /usr/bin/osascript - "$id" "$src" "$acct_name" <<'APPLESCRIPT'
on run argv
	set {theId, srcPath, acctName} to argv
	tell application "Mail"
		set acct to account acctName
		repeat with mb in (every mailbox of acct)
			try
				set theSource to source of (first message of mb whose id is (theId as integer))
				set f to open for access (POSIX file srcPath) with write permission
				write theSource to f as «class utf8»
				close access f
				return
			end try
		end repeat
		error "No message with id " & theId & " in any " & acctName & " mailbox"
	end tell
end run
APPLESCRIPT
  /usr/bin/python3 -I - "$src" >> "$html" <<'PY'
import email, email.policy, html, re, sys
m = email.message_from_bytes(open(sys.argv[1], "rb").read(), policy=email.policy.default)
part = m.get_body(("html", "plain"))
body = part.get_content() if part else ""
if part is None or part.get_content_type() == "text/plain":
    body = html.escape(body).replace("\n", "<br>")
else:
    inner = re.search(r"<body[^>]*>(.*)</body>", body, re.S | re.I)
    body = inner.group(1) if inner else body
row = lambda k, v: f"<b>{k}:</b> {html.escape(str(v))}<br>" if v else ""
print('<div><br></div><hr style="display:inline-block;width:98%" tabindex="-1">'
      '<div id="divRplyFwdMsg" dir="ltr"><font face="Calibri, sans-serif" style="font-size:11pt" color="#000000">'
      + row("From", m["From"]) + row("Sent", m["Date"]) + row("To", m["To"]) + row("Cc", m["Cc"])
      + row("Subject", m["Subject"]) + '</font><div>&nbsp;</div></div>' + body)
PY
fi

/usr/bin/osascript - "$mode" "$id" "$to" "$subject" "$html" "$acct_name" <<'APPLESCRIPT'
on run argv
	set {theMode, theId, theTo, theSubject, theHtmlPath, acctName} to argv
	set theHTML to read (POSIX file theHtmlPath) as «class utf8»
	tell application "Mail"
		set acct to account acctName
		if theMode is "reply" then
			set parentMsg to missing value
			repeat with mb in (every mailbox of acct)
				try
					set parentMsg to first message of mb whose id is (theId as integer)
					exit repeat
				end try
			end repeat
			if parentMsg is missing value then error "No message with id " & theId & " in any " & acctName & " mailbox"
			set d to reply parentMsg with reply to all without opening window
		else
			-- Without an explicit sender, Mail saves new drafts under its default account (iCloud).
			set acctAddrs to email addresses of acct
			set d to make new outgoing message with properties {subject:theSubject, sender:(item 1 of acctAddrs), visible:false}
			set AppleScript's text item delimiters to ","
			repeat with addr in text items of theTo
				tell d to make new to recipient at end of to recipients with properties {address:addr}
			end repeat
			set AppleScript's text item delimiters to ""
		end if
		set html content of d to theHTML
		save d
		return "DRAFT SAVED: " & (subject of d)
	end tell
end run
APPLESCRIPT
