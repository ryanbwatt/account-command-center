# VBF template

## Grid and per-cell prompts

| Cell | Question it answers | Deal mode | Win-study mode |
|---|---|---|---|
| Before Scenario (As-Is) | What does the customer do today? | Current tools, workflows, documented behavior (e.g. an outdated chatbot), disconnected portals, constraints | Vendor X/Y state before the switch |
| Negative Business Impact | What does the as-is cost them? | **Quantified or benchmarked cost of inaction**: engineering headcount drag ($/yr to build bespoke pipeline), velocity delays (days/weeks vs minutes), support escalation volume, training abandonment, churn risk | Observed financial and operational pain that drove the decision |
| After Scenario (To-Be) | What changes with the video platform? | Proposed capability (e.g. AI video answers, avatars, cited video clips inside host product); roadmap Options 1 to 3 | Delivered capability |
| Positive Business Outcome | What do they gain, and downstream? | Projected financial & operational outcomes: in-workflow real estate stickiness, higher daily active usage/retention, faster verification, support offload | Realized outcomes |

### Dual Experience Breakdown (Mandatory)
Every cell must break down into:
- `operations`: Buyer, engineering, product, admin, CS/enablement perspective (e.g., custom pipeline maintenance cost, dev sprint drag, inability to measure in-product engagement).
- `end_user`: Frontline employee, learner, viewer perspective (e.g., leaving workflow to scrub hour-long recordings, friction, unverified answers).

### Quantifying Negative Business Impact
Never stop at passive qualitative statements (e.g., "the customer builds its own packaging and clip rendering"). Answer: **What does that cost them?**
- **Engineering / Infrastructure Drag**: e.g. "N FTEs (example: 3 FTEs, ~$450K/yr loaded) to build and babysit bespoke video ingestion, packaging, and clip-rendering pipelines on raw sources."
- **Velocity / Time-to-Answer**: e.g. "Takes days/weeks of engineering time when it should take minutes via API/MCP; end users spend 10-15 minutes scrubbing recordings for a 30-second explanation."
- **Enablement & Support Burden**: e.g. "Untargeted, out-of-workflow training leads to low feature adoption, repeated support escalations, and renewal churn vulnerability."
- When exact customer numbers are not yet verified, model the impact with reasonable operational hypotheses or industry research benchmarks (e.g., "example: ~$300K/yr dev overhead", "example: ~30% content abandonment") and document the modeling logic in the companion file.

Proof Points: `capabilities` (critical capabilities needed), `evidence` (reference customer, trial, pilot, or "none yet"), `use_cases` (applicable use cases).

Header: `account_profile` ("Fortune N Enterprise, <FTEs>, <revenue>" in win-study; account name in deal mode) + `headline` (the goal or displacement in one sentence).

## Roadmap Options (Slide 4 / Solution Overview)
When mapping out deployment options:
- **Option 1: RAG-only** (Lowest lift, available today): the vendor provides sources/captions/timestamps via API; customer LLM composes text.
  - *Risk / Watch-out*: **Cannibalization risk**. If the customer builds custom packaging, clip rendering, and UI around raw timestamps, they sink engineering effort and will resist adopting higher-value MCP / AI answer solutions.
- **Option 2: Packaged clips** (Agent-to-agent / MCP): the vendor returns packaged, permissioned clips with captions and timestamps; customer embeds clips beside the answer.
- **Option 3: Full AI video answers (Goal)** (Highest lift): the vendor embeds AI answers, interactive clips, summaries, and in-video follow-ups.
  - *Explicit Business Case for Cited Video Clips*:
    - **In-Workflow Real Estate & Stickiness**: Keeps professionals inside the high-value host application ("flow of work") rather than abandoning to side portals.
    - **Platform Affinity & Daily Active Usage**: Direct lift to core platform retention, feature discovery, and renewal value.
    - **Verification & Decision Velocity**: Instant authoritative proof (exact spoken audio, slides, expert commentary) with cited timestamps, eliminating scrubbing and ambiguity.

## Strategic Reframing & Tiered Monetization
- **Reposition the video platform**: Shift from merely a "video vendor" to the enterprise digital content repository and single source of truth for digital learning and verified video intelligence.
- **Tiered Packaging Model**:
  - *Base Tier*: Standard text and document retrieval.
  - *Video-Augmented Tier*: Cited playable video clips, timestamped excerpts, and in-video AI follow-ups.
  - *Premium Assistant Tier*: conversational AI agent or AI avatar that remembers earlier questions and project history, grounded in verified internal content.
- **Domain Rigor**: In regulated industries, emphasize human expert provenance and non-hallucinatory grounding.

## JSON spec (Core VBF)

Illustrative example: "Acme Corp" and every figure below are fictional.

```json
{
  "account": "Acme Corp",
  "account_profile": "Acme Corp (illustrative example)",
  "headline": "Goal in one sentence",
  "before": {
    "summary": "optional one-liner",
    "operations": ["fact bullet"],
    "end_user": ["fact bullet"]
  },
  "negative_impact": {
    "operations": ["Quantified cost (example): 3 FTEs (~$450K/yr) to build and maintain bespoke video packaging"],
    "end_user": ["Lost productivity (example): professionals spend ~15 min scrubbing videos; low adoption of out-of-workflow training"]
  },
  "after": {
    "operations": ["Single API/MCP integration delivers permissioned clips and AI answers in minutes"],
    "end_user": ["Ask in-product; get cited video clips and summaries with in-video follow-ups"]
  },
  "positive_outcome": {
    "operations": ["Save ~$400K/yr (example) in custom pipeline dev; track CS feature adoption and time-to-first-productive-action"],
    "end_user": ["Keeps users in core workflow real estate; closes gap between available and used features, driving retention"]
  },
  "proof_points": {
    "capabilities": "Search/RAG API; agent-to-agent/MCP; embeddable AI Q&A widget; cited clips; permission-aware results",
    "evidence": "Customer demo (date); 100,000 licensed users (example); 1M annual streams (example)",
    "use_cases": "In-product training search; contextual video answers; expert knowledge retrieval"
  },
  "validate": ["Confirm custom video pipeline dev costs with <stakeholder>"],
  "gaps": ["Discovery question on support ticket escalation volume"],
  "sources": ["[G1] Gong YYYY-MM-DD 'call title'", "[N1] Notes/file.md"],
  "source_status": ["Gong via SF: reachable", "Granola export: 4 notes read"]
}
```

## Extended 5-Slide Solution Overview Deck
For broader stakeholder alignment, the skill produces an extended 5-slide deck:
- **Slide 1**: Value Based Framework (2x2 grid + Proof Points).
- **Slide 2**: Solution Overview (Workflow steps with highlighted video-platform injection points, where video is missing today, core opportunity, vendor contribution, design principles).
- **Slide 3**: What the User Sees (Illustrative UI mock-up: sourced answer + related clips + in-video AI follow-up).
- **Slide 4**: How We Get There (Options 1/2/3 breakdown with explicit business case for Option 3, pilot work plan, pilot measures).
- **Slide 5**: Commercial Upside & Monetization (Value pool modeling, monetization levers, vendor upside).


A worked, fully fictional example of slides 2-5 lives in `scripts/build_overview_pptx.py` (Acme Corp / Site Assist, a made-up construction-software product, invented round numbers).
