# Value map for /value-story

Frameworks: Forrester TEI (benefits / flexibility / risk-adjusted), Bain B2B Elements of
Value (table stakes → individual value), Gainsight verified outcomes, TSIA value management (lock a baseline),
realized value over utilization.

## Pillars

| Pillar | Means | Bain tier | $ kind |
|---|---|---|---|
| **Stabilize** | risk down: compliance (CPE, ADA/WCAG, 508, HIPAA), security, continuity, uptime of big events, fewer vendors | table stakes, reduced risk/anxiety | saved / avoided |
| **Compete** | faster, better, wider: time to publish, languages, quality, employee/learner experience, AI-native workflows | functional, ease of doing business | saved (time, tools) |
| **Grow** | more revenue and reach: pipeline, audience, new markets, monetization, workforce capability | functional growth, inspirational | made |

Include one **persona line**: what this outcome does for the reader personally (CFO $, CLO completion, CMO pipeline,
CIO risk/uptime, comms reach). Bain: individual value drives B2B loyalty.

## Profile → levers

Pick the rows that match the profile and ignore the rest. Customer-reported numbers beat every rate below.

| Profile | Lever | Pillar | Metric we need | Rate (cited) |
|---|---|---|---|---|
| Internal + live | Town halls / all-hands at scale, no outage | Stabilize | events, live viewers, incidents | ITIC downtime (qualitative unless they give a $) |
| Internal + live/VOD | Travel avoided for meetings & training | Grow (saved) | **customer**: attendees who'd otherwise travel | GBTA trip parts below |
| Internal + VOD (L&D) | Training delivered without classroom | Compete | learning hours (value-id `RATES` ATD $/hr) | ATD via value-id |
| Internal | Knowledge findable (search, chapters, AI) | Compete | searches, AI Q&A sessions | qualitative; MGI "~20% of workweek" only as context |
| External + live (marketing) | Webinar/event pipeline | Grow (made) | **customer**: pipeline/leads sourced or influenced | ON24 benchmarks as context only |
| External + VOD (customer ed / support) | Tickets deflected by video | Stabilize (saved) | **customer**: deflected contacts | customer cost per contact only |
| External (media / publishing) | Monetized views, new-language audiences | Grow (made) | revenue or views by language | customer revenue only |
| Any + captions | Accessibility compliance | Stabilize (saved) | caption minutes | Rev human captions $1.99/min |
| Any + translation | Global reach | Compete (saved) / Grow | minutes × languages | Rev subtitles $6.49 ES · $10.49 FR/DE · $15.99 JA/KO per min |
| Any + dubbing / avatars | Localized and scaled production | Compete | minutes produced | qualitative (no neutral rate) |
| Any + agents (learning / revenue) | Next value step | "next" slide (TEI flexibility) | — | never counted in totals |
| Any | Vendors / tools consolidated | Stabilize (saved) | **customer**: retired tool cost | customer only |

AI off → drop the AI rows, keep `featured` empty or make it the strongest non-AI outcome, and put one AI play in `next`.

## Industry priorities (what their execs value)

- **Financial / professional services**: audit-proof CPE (NASBA: ≥3 polls per credit for group-internet programs), client-content
  security, thought-leadership webinars for pipeline, less advisor travel.
- **Healthcare / life sciences**: HIPAA/GxP-safe hosting, clinician and rep training completion, captioned patient education, compliant HCP engagement.
- **Higher ed**: ADA Title II WCAG 2.1 AA by **Apr 26 2027** (pop. ≥50K; Apr 26 2028 smaller; DOJ IFR 2026-04-20). Also lecture capture + LMS, enrollment reach.
- **Government / federal**: FedRAMP, Section 508, continuity of operations, public-meeting transparency, cost avoidance.
- **Media / publishing**: monetization, time to publish, new-language reach, peak-event uptime.
- **Tech / SaaS**: webinar pipeline, product education that deflects tickets, partner and customer enablement.
- **Manufacturing / automotive**: frontline skills (1.9M US jobs could go unfilled by 2033, Deloitte/MI 2024), multilingual safety content, dealer comms.
- **Legal / information services**: content security and entitlements, CLE delivery (verify per state), expert video as AI-ready knowledge products.

## Rates (verified; cite on the slide notes)

| Rate | Value | Source |
|---|---|---|
| Business-event cost per attendee/day | $162 (2024), $169 (2025f) | GBTA + CWT Global Business Travel Forecast 2024 |
| NA airfare per ticket | $804 (2024) | same |
| Hotel per night (global) | $162 (2024) | same |
| Training spend per learner/yr | $774 | Training Magazine Industry Report 2024 |
| Cost per learning hour | see value-id `RATES` | ATD 2024 SOIR |
| Human captions | $1.99/min | Rev price list 2026 |
| Human subtitles | $6.49–$15.99/min by language | Rev price list 2026 |
| IT downtime | >$300K/hr for 90%+ of mid/large orgs | ITIC 2024 |
| Website-accessibility suits | 3,117 federal filings in 2025 (+27%) | Seyfarth ADA Title III, 2026 |
| Employee engagement | 20% engaged; ~$10T lost productivity | Gallup State of the Global Workplace 2026 |

Travel avoided = customer's virtual attendees who would have traveled × (airfare + hotel nights + $169/day). The attendee count must come from the customer.

**Do not use** (unverified): virtual events "75–85% cheaper", "1.8 hrs/day searching", Brandon Hall "40–60% less time",
vendor-blog ADA settlement and dubbing price ranges, 3Play public list price. Check whether a vendor TEI exists before citing one. Comparable studies (context only): Zoom TEI 2022 (261%), Teams Premium TEI 2023 (caption labor
$29–116K), WeVideo TEI 2025 (208%). Most of their benefit dollars are labor time + tool consolidation + travel; revenue is conservative.

## Slide craft

1. Lead with their goal, not our product. No product names in titles.
2. Tag every $: customer / measured / benchmark. Money saved and money made stay separate.
3. Low end of ranges, attributable only, count once. Hard-to-prove value is stated qualitatively, never inflated.
4. Upsell is framed as an option on the "next" slide.
5. Lock a baseline (first run: `baseline` in the spec JSON) and reuse the same formulas each quarter so the trend is credible.
6. Have the champion validate the numbers before the meeting (Gainsight's verified outcome). Put that ask in the companion.
