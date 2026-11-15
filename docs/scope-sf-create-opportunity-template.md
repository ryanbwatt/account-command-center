# Scope: unattended placeholder opportunity creation

**Status:** proposed, not implemented. Branch name when built: `sf-create-opportunity-template`.

Custom field API names below are written as keys of the `sf_fields` map in `config.local.json`
(e.g. `sf_fields.journey`); the real API names live only in that local file.

## Problem

`sf_create_opportunity` can write 7 fields. This org rejects a create without 15.

The allowlist (`_SF_WRITABLE_FIELDS`) was designed for *forecast updates* on existing
opportunities — `NextStep, Description, StageName, CloseDate, ForecastCategory, Amount,
Probability`. Create was layered onto the same validator, so every other field is **silently
dropped** by `_sf_validate_write()` (`if k not in _SF_WRITABLE_FIELDS: continue`).

The failure mode is bad: the dry run renders a perfect-looking record, then the real create fails
on fields the tool never sent. Creating a single placeholder took four round trips, each
surfacing a different validation error, and still ended in the Salesforce UI.

Fields the org requires that the tool cannot set:

| Field | Required by | Notes |
|---|---|---|
| `sf_fields.journey` | validation rule | picklist: Customer / Employee / Learner / Audience |
| `sf_fields.usecases` | validation rule | long picklist, ~25 values |
| `sf_fields.primary_business_contact_o` | validation rule | Contact lookup |
| `sf_fields.sub_type` | validation rule (prob >= 25%) | Strategic / Organic Growth |
| `sf_fields.what_type_of_deal_is_this` | validation rule (prob >= 25%) | Normal / Pilot. Label is "Deal Type"; this is the field to write, not `sf_fields.deal_type` |
| `sf_fields.buyers` | validation rule | multipicklist |
| `sf_fields.incumbents` | validation rule | multipicklist, **restricted** |
| `RecordTypeId` | picklist filtering | defaults to Standard, but must be explicit or restricted picklists reject valid values |
| `Type` | correctness | defaults to "New Business", wrong for an upsell |
| `sf_fields.contract_length` | correctness | months |
| `sf_fields.start_date` | correctness | term start |
| `ForecastCategoryName` | correctness | the writable field; `ForecastCategory` is read-only in this org |

## Evidence for defaulting

Sampled the user's `Upsell` opps from the last 400 days, on the Standard record
type (excluding Overages and Pilots, which are a different shape):

- `sf_fields.what_type_of_deal_is_this` = **Normal** — every one, no exceptions
- `sf_fields.sub_type` = **Organic Growth** — the large majority
- `sf_fields.buyers` = **Executive** — the large majority
- `sf_fields.incumbents` = **None** — all but one
- `RecordTypeId` = **Standard**

These are boilerplate, not judgment calls. Safe to default.

`sf_fields.journey` / `sf_fields.usecases` are **not** safe to default globally — they vary by
account and describe what the customer actually does (employee training, customer-facing video,
learner content, or audience events). But they are **stable per account**, so inherit them from
the account's most recent opportunity that has them set, and require an explicit argument when
the account has none.

## Design

Add `sf_create_placeholder_opportunity()` alongside the existing tool rather than replacing it —
the current one stays valid for a hand-specified create.

```
sf_create_placeholder_opportunity(
    account_id, name, mrr, term_start,       # required
    term_end=None,                          # default: account's renewal date (sf_fields.closest_renewal_date)
    stage="Qualification", probability=10,
    journey=None, usecases=None,             # default: inherit from account's last opp
    description="", dry_run=True,
)
```

Derivations, so the caller supplies four values instead of fifteen:

1. **Term length** — months between `term_start` and `term_end`, inclusive of the start month.
   `term_end` defaults to the account's renewal date (`sf_fields.closest_renewal_date`) so add-ons
   co-terminate with the contract, which is the established pattern on these accounts.
2. **Amount** — `mrr * contract_length`. Verified against the user's opps carrying both
   `sf_fields.rr` and `sf_fields.contract_length`: every one matched exactly. `Amount` is total
   contract value; `sf_fields.rr` is a rollup from line items and cannot be written.
3. **Close date** — last day of the month before `term_start`, clamped to >= today.
4. **Primary business contact** — the account's most recent opportunity's
   `sf_fields.primary_business_contact_o`, else the account's primary contact.
5. **Journey / Usecases** — inherited per above.
6. **Boilerplate** — Type `Upsell`, Sub Type `Organic Growth`, Buyers `Executive`,
   Incumbents `None`, Deal Type `Normal`, RecordType `Standard`,
   ForecastCategoryName `Pipeline`.

## Implementation notes

- **Separate the create allowlist from the update allowlist.** Add `_SF_CREATE_FIELDS` rather than
  widening `_SF_WRITABLE_FIELDS` — the update path's narrowness is a deliberate forecast guardrail
  and must not loosen as a side effect.
- **Validate all fields up front and raise once**, listing every problem. The round-trip-per-error
  experience is the main thing being fixed.
- **Fetch picklist values from `sf sobject describe` and cache per process.** Hardcoding restricted
  picklist values is what broke on `sf_fields.incumbents` — "None" is active and in the
  global describe, but rejected until `RecordTypeId` is set, because record types filter
  picklists. The validator must describe against the *record type being used*.
- Keep `dry_run=True` default, keep `OwnerId` forced to `_SF_OWNER_ID`, keep the `_sf_audit` call
  and the `create-unverified` path.
- Return the derivations in the dry-run payload so the arithmetic is reviewable before it is
  written. Example (fictional numbers): `{"derived": {"contract_length": 12, "amount": 12000,
  "term_end": "2027-12-31", "close_date": "2026-12-31"}}`.

## Test plan

- Dry run reproduces a known example record exactly. Example (fictional): Acme Corp, MRR $1,000,
  12 months, $12,000, close 2026-12-31, term 2027-01-01 -> 2027-12-31, contact Jordan Lee,
  Journey Customer.
- A create with a deliberately bad picklist value fails on the first call and names every invalid
  field at once.
- An account with no prior Journey/Usecases raises asking for them rather than guessing.
- `term_start` after `term_end` raises.
- One real create end to end, then verify every field landed by reading the record back.

## Out of scope

- Opportunity line items (`OpportunityLineItem`). `sf_fields.rr` stays 0 until someone adds the
  product SKU in the UI, and the hand-entered `Amount` may then disagree with the rollup. Worth a
  follow-up: adding the SKU line with quantity and unit price would make `sf_fields.rr`
  authoritative.
- Renewal opportunities — different record type, different required fields, owned by the renewals
  desk.
- Account ownership changes. Out of scope by design; that is a Sales Ops action.
