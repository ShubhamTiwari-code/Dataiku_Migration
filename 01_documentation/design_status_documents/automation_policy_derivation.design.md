# Design: AUTOMATION_POLICY derivation (read-only)

**Rule (prompt D3 / restriction L)**: "No derives nuevas aprobaciones en este proceso." This derivation
NEVER computes a new approval — it only republishes, in one queryable table, decisions that are already
governed elsewhere.

## Sources (both already exist and are already the actual sources of truth)
1. `models/paso_6_model_strategy_decision.json` — per-market `model_strategy`, model filename
   convention (`model_custom_{slug}.pkl` vs `model_global.pkl`), and (via the manifest referenced by
   `uat_08._check_model_drift`) the approved-time SHA-256.
2. `uat/reports_decile/{slug}_decile_combined_analysis.csv` — per score-bucket `AUTO_MERGE` /
   `AUTO_NO_MERGE` / manual designation, read today by `uat_08._load_decile_automation()`.

## Derivation algorithm (future script, e.g. `scripts/dataiku_derive_automation_policy.py`)
```
for each market in paso_6_model_strategy_decision.json:
    read decile CSV for market (if missing -> all buckets NOT_APPROVED, no row emitted per bucket
        beyond a single NOT_APPROVED marker row, per AUTOMATION_POLICY.schema.yaml conflict_policy)
    for each score_bucket row in the decile CSV:
        automation_action = AUTO_MERGE | AUTO_NO_MERGE | MANUAL
            (verbatim from the CSV's `automation_recommendation` column — NOT the CSV's own
            `automation_action` column, which is a different candidate-level field; see
            AUTOMATION_POLICY.schema.yaml derivation_note)
        approval_status   = APPROVED if automation_action != MANUAL else NOT_APPROVED
        model_sha256      = from the approval-time manifest (uat/manifest/{slug}_uat_run_manifest.json)
        if routing JSON and manifest disagree about which model file is active -> AMBIGUOUS (fail-safe)
    write one row per (market_iso, score_bucket)
emit RUN_MANIFEST with policy_version = "{YYYYMMDD}-{HHMMSS}"
call PairRegistry.upsert_automation_policy(df, policy_version)
```

## Governance rule citations
- **RULE-024** (automation gating must use the metric matching the row's own predicted class —
  false-merge rate for `AUTO_MERGE` candidates, missed-merge rate for `AUTO_NO_MERGE` candidates):
  `AUTOMATION_POLICY.automation_action` republishes exactly the values RULE-024 already governs in
  `uat/reports_decile/*.csv`; this derivation performs no recomputation of that gate.
- **RULE-025** (automation must be blocked, not silently allowed, when model-version verification is
  unavailable): the `AMBIGUOUS` fail-safe status (routing JSON vs. manifest disagreement) is this
  contract's implementation of RULE-025's "cannot verify = treat as blocked" requirement.

## Consumption
- `uat_08`'s existing reveal gate (`_load_decile_automation` + `_check_model_drift` +
  `_check_routing_json`) is NOT required to change — it can keep reading the CSVs directly (current
  production behavior, KNOWN-DEVIATION-004, already accepted). `AUTOMATION_POLICY` is an **additive**
  queryable cache for Dataiku-side tooling (e.g. the blind/predict routing improvement below), not a
  replacement dependency uat_08 must adopt in this pass.
- **Blind/predict routing improvement** (addresses the user's KR question): instead of the
  hand-maintained `PM_EXCLUDE_COUNTRIES` variable, `recipe_generate_blind_pm_reports.py` could compute
  `exclude_countries = ",".join(PairRegistry.get_markets_with_any_approval())` at runtime, so newly
  approved markets (e.g. Colombia, approved 2026-09-23) are automatically excluded from the blind
  recipe the next time it runs, without an operator remembering to edit the variable. This is a
  **design opportunity**, not a defect fix — the current KR-only default is intentional and correct
  today; it just doesn't scale as more markets get approved. See
  [recipe_generate_blind_pm_reports.design.md](recipe_generate_blind_pm_reports.design.md).
