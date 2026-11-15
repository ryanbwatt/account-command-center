# Pulse + one tip: prompt for a data warehouse assistant (Databricks)

Paste the block below as the scheduled task (weekly, Monday 8:00 ET). Replace the three
account names, the field placeholders (from `sf_fields` in `config.local.json`), the KB site
(`kb_base_url`), and your name. It mirrors `.claude/skills/pulse-tip/SKILL.md`, so the two
outputs can be compared side by side. It asks for text output rather than drafts, since the
assistant may not be able to write to Outlook.

---

```
You are my account-management analyst. Every Monday, for each of these accounts:
<ACCOUNT 1>, <ACCOUNT 2>, <ACCOUNT 3>, find ONE specific, helpful thing to tell the customer
this week, and write it as a short email I can send. Do not send anything and do not change
any record.

For each account:

1. Usage vs. contract. From Salesforce, get the active contract's bandwidth and storage
   allowances and the monthly usage per Partner ID (<sf_fields.pid_monthly_usage>:
   <sf_fields.bandwidth_combined_gb>, <sf_fields.average_storage_gb>). Ignore the current
   partial month. For the current contract year, compute year-to-date usage, the 3-month run
   rate, projected year-end usage, projected utilization (projected ÷ allowance), and the trend
   vs. the same 3 months last year. Use only bandwidth and storage numbers from Salesforce; do
   not trust its allowance fields, take allowances from the contract.
2. What they told us. From the last 60 days of call notes and Gong summaries, list pains,
   requests or complaints in the customer's words.
3. Pick ONE signal, in this order:
   a. a pain they told us about that a platform feature or setting addresses;
   b. projected utilization between 90% and 120% (tip: how to trim whichever pool drives it);
   c. something paid for but unused (for example captioning credits remaining);
   d. low adoption of something they already own.
   If projected utilization is over 120%, or under 50%, or usage is down more than 25%, or
   there is an open escalation: do NOT write a tip. Flag it for me with the numbers.
   If nothing specific applies, skip the account. A generic tip is worse than none.
4. Find one article on <KB SITE> that explains the fix. Use a real URL you found; never
   invent one. No good article means skip.
5. Choose the recipient: the customer's day-to-day platform owner from the Salesforce
   contacts, on the customer's own email domain.
6. Write the email: subject "Quick tip: <what they get>"; "Hi <first name>,"; 3–4 short
   sentences stating the one concrete fact I noticed, the one thing to try, the article link,
   and an offer of 15 minutes to walk through it. No pricing, no selling, no "just checking in".
   Sign off "Thanks!" then "<YOUR NAME>".

Output, in this order:
- A table: Account | Signal | Key numbers | Article | Recipient
- Each email in full
- "Needs me": accounts flagged in step 3, with the numbers and why
- "Skipped": accounts skipped, with one-line reasons
- "Data I couldn't get": any source or field you couldn't reach
```

---

**What to compare against Claude's run:** same signal picked? same numbers (projected
utilization should match to within a few percent)? a real, relevant KB link? an email you'd
send unedited? how long it took, and whether it said plainly what it couldn't access.
