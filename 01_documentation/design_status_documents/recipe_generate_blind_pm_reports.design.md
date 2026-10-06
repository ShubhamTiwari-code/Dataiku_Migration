# Design: Process #2 — Generate Blind PM Reports

**As-is today**: [`dataiku/recipes/recipe_blind_pm_reports.py`](../../dataiku/recipes/recipe_blind_pm_reports.py)
is already a compliant thin wrapper over `uat_08_generate_pm_reports.py --mode non_uat` (no `--predict`).
It already: reads `PM_COUNTRIES` / `PM_EXCLUDE_COUNTRIES` variables, resolves the `snowflake_extracts`
and `pm_reports` Managed Folders, and relies on `uat_08` for anti-join, chunking, and `Report_Info`.
**No functional gap here that blocks the proposal's D2 requirements.**

## Clarification on `PM_EXCLUDE_COUNTRIES` default = "KR" (resolved during planning)
Read directly from the recipe source:
```python
exclude_countries = variables.get("PM_EXCLUDE_COUNTRIES", "KR")   # blind recipe
exclude_countries = variables.get("PM_EXCLUDE_COUNTRIES", "")     # predict recipe
```
This is **intentional routing, not a bug**: South Korea has an approved automation bucket, so it must
be generated exclusively via the **predict** recipe (where the decile-aware reveal applies), and is
therefore excluded from the **blind** recipe by default. A market with an approved bucket getting a
blind-only report would be a regression (stewards would lose the automated pre-fill), so excluding it
from blind is correct.

## Prior art
ARCHITECTURE.md's v2.7.14 note already documents this same `PM_EXCLUDE_COUNTRIES="KR"` scaling
concern, and `docs/DATAIKU_PM_REPORTS_WALKTHROUGH.md` already documents the related
`uat_reports_decile` folder-wiring limitation (KNOWN-DEVIATION-004). This design formalizes a fix
for an already-acknowledged gap, not a newly discovered one.

## The actual gap this uncovers
`SYSTEM_STATE.md` records 6 markets with approved automation buckets as of 2026-09-23 (Germany, Italy,
Mexico, South Korea, Turkey, Colombia), but the recipe's hardcoded default only excludes `KR`. Unless an
operator manually edits the `PM_EXCLUDE_COUNTRIES` DSS project variable every time a new market crosses
the approval threshold, the other 5 approved markets get **both** a blind report and a predict report
from the same cycle — not incorrect (predict-reveal rows are still gated correctly per-row), but
redundant and a source of steward confusion (two files to reconcile for the same market).

## Proposed improvement (future implementation, optional / non-blocking)
Compute the exclude-list dynamically instead of trusting a hand-maintained variable:
```python
# recipe_blind_pm_reports.py (future)
approved_markets = PairRegistry(...).get_markets_with_any_approval()   # from AUTOMATION_POLICY
manual_excludes = set(variables.get("PM_EXCLUDE_COUNTRIES", "").split(","))
exclude_countries = ",".join(sorted(approved_markets | manual_excludes))
```
`PM_EXCLUDE_COUNTRIES` keeps working as an additional manual override (e.g. to exclude a market for
unrelated operational reasons), but is no longer the *only* mechanism keeping approved markets out of
the blind recipe. This depends on [AUTOMATION_POLICY](../contracts/AUTOMATION_POLICY.schema.yaml) /
`PairRegistry.get_markets_with_any_approval()` existing first (see
[pair_registry_extension.design.md](pair_registry_extension.design.md)).

## Governance note
Framed here as a **design improvement / drift-risk reduction**, not a release-blocking defect — the
current behavior is safe (no blindness or approval control is weakened), it is only operationally
fragile. See [governance/PRE_IMPLEMENTATION_AUDIT_DATAIKU_SLICE.md](../governance/PRE_IMPLEMENTATION_AUDIT_DATAIKU_SLICE.md).
