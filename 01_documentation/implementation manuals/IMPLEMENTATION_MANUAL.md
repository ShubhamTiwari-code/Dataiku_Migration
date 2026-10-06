# Operational PM Reports Slice — Implementation Manual

Status: **IMPLEMENTED IN THE LOCAL FRAMEWORK, PASSED GOVERNANCE RE-AUDIT** (updated 2026-09-24).
Everything described below as "future"/"NEW" has been written, tested against real repo data, and
reviewed twice by the Governance Auditor (`governance/PRE_IMPLEMENTATION_AUDIT_DATAIKU_SLICE.md` →
PASS_WITH_WARNINGS, then `governance/IMPLEMENTATION_REVIEW.md` → FAIL on one real bug found, fixed,
re-verified → **PASS**). What remains is **Dataiku-side deployment** (Managed Folders, project
variables, Code Environment, model upload) — that part has NOT been done and requires DSS
administrator access this session did not have. See "Where to start" at the end of this file.

## 1. Purpose
Provide a governed, agile path to close the remaining gaps in Dataiku's "Operational PM Reports Slice"
(refresh candidates, blind reports, predict reports, ingest steward decisions) without duplicating the
already-mature logic in `uat_08`, `uat_09`, and `PairRegistry`.

## 2. Scope
In scope: 4 processes, 5 data contracts (`PM_CANDIDATES_CURRENT`, `RESOLVED_PAIR_REGISTRY` view,
`AUTOMATION_POLICY`, `INGESTED_FILE_REGISTRY`, `RUN_MANIFEST`/`RECONCILIATION_WATERFALL`), a `PairRegistry`
extension, and a test-scenario mapping.
Out of scope: model training, threshold optimization, new UAT approvals, PII in tests, changes to
blind-review/decision-source/model-drift controls.

## 3. Architecture
```
Snowflake (CSV upload today / native dataset future)
   -> [Process #1: Refresh PM Candidates]           (NEW script+recipe, design/recipe_refresh_pm_candidates.design.md)
   -> PM_CANDIDATES_CURRENT                          (NEW contract)
        |
        +--> anti-join RESOLVED_PAIR_REGISTRY -->  [Process #2: Blind PM Reports]   (EXISTS: recipe_blind_pm_reports.py + uat_08)
        +--> anti-join + AUTOMATION_POLICY gate --> [Process #3: Predict PM Reports] (EXISTS: recipe_predict_pm_reports.py + uat_08; needs BACKLOG-007 flag)
                    |
              SharePoint outbound -> Data Steward -> SharePoint inbound
                    |
                    v
        [Process #4: Ingest Steward Decisions]       (EXISTS: recipe_uat_09_process.py + uat_09; needs INGESTED_FILE_REGISTRY hook)
                    |
                    v
        RESOLVED_PAIR_REGISTRY (updated)  --> anti-join of next cycle
```

## 4. Components (as-is vs target) — target column now DONE for all rows
| Component | As-is (before) | Target | Status | Design doc |
|---|---|---|---|---|
| Refresh candidates | Manual CSV upload, no snapshot/manifest | `recipe_refresh_pm_candidates.py` + script | ✅ DONE — [dataiku/recipes/recipe_refresh_pm_candidates.py](../dataiku/recipes/recipe_refresh_pm_candidates.py), [scripts/dataiku_refresh_pm_candidates.py](../scripts/dataiku_refresh_pm_candidates.py) | [design/recipe_refresh_pm_candidates.design.md](design/recipe_refresh_pm_candidates.design.md) |
| Blind reports | Production, compliant | Optional dynamic exclude-list | ⏸ DEFERRED (BACKLOG-DM-001, optional improvement, not required) | [design/recipe_generate_blind_pm_reports.design.md](design/recipe_generate_blind_pm_reports.design.md) |
| Predict reports | Production, compliant | Add `--reports-decile-dir` (BACKLOG-007) | ✅ DONE — flag added to [scripts/uat_08_generate_pm_reports.py](../scripts/uat_08_generate_pm_reports.py), wired into [recipe_predict_pm_reports.py](../dataiku/recipes/recipe_predict_pm_reports.py) | [design/recipe_generate_predict_pm_reports.design.md](design/recipe_generate_predict_pm_reports.design.md) |
| Ingest decisions | Production, compliant | Add `INGESTED_FILE_REGISTRY` hook + conflict recording | ✅ DONE — [scripts/uat_09_process_pm_report_decisions.py](../scripts/uat_09_process_pm_report_decisions.py) (bug found + fixed post-audit, see IMPLEMENTATION_REVIEW.md) | [design/recipe_ingest_steward_decisions.design.md](design/recipe_ingest_steward_decisions.design.md) |
| AUTOMATION_POLICY | Scattered (routing JSON + decile CSVs) | Derived, queryable, read-only | ✅ DONE — `PairRegistry.upsert_automation_policy()`/`get_automation_policy()` | [design/automation_policy_derivation.design.md](design/automation_policy_derivation.design.md) |
| PairRegistry | Covers training/predict/UAT/steward events | + automation_policy, ingested_file_registry, resolved-view, conflict recording | ✅ DONE — [src/lineage/pair_registry.py](../src/lineage/pair_registry.py) | [design/pair_registry_extension.design.md](design/pair_registry_extension.design.md) |

## 5. Data contracts
See [contracts/](contracts/) — one YAML per contract with columns, types, nullability, keys, upsert
and conflict policy, and migration notes.

## 6. Managed Folders / variables (Dataiku-side provisioning — STILL an admin dependency, not done)
New Managed Folders needed: `pm_candidates_current` (new), `uat_reports_decile` (already existed for
the UAT chain, now ALSO required by `recipe_predict_pm_reports`). New variables:
`PM_CANDIDATES_INPUT` (implemented, defaults to `snowflake_extracts`). `run_manifests` as a separate
Managed Folder, `PM_AUTOMATION_POLICY_VERSION`, `PM_SHAREPOINT_INBOUND`/`PM_SHAREPOINT_OUTBOUND`,
`PM_CONFLICT_POLICY` remain design-only (not needed by anything implemented so far — `RUN_MANIFEST`
is currently written as a local JSON file next to each script's output, not a separate Dataiku
dataset/folder). No Code Environment, connection, or plugin creation is assumed available; all
Managed Folders/variables above are the only DSS-admin actions required.

## 7. Execution order (future)
1. `recipe_refresh_pm_candidates` (independent)
2. `recipe_blind_pm_reports` / `recipe_predict_pm_reports` (both depend on #1's latest snapshot)
3. Manual: SharePoint outbound → steward review → SharePoint inbound
4. `recipe_uat_09_process` (Ingest Steward Decisions) — anti-join consumed by the next cycle's #1/#2/#3

## 8. Manual operation (local framework, without Dataiku) — already working today
Everything described here already runs locally (validated against real repo data — see
`governance/IMPLEMENTATION_REVIEW.md` for exact counts). `docs/DATAIKU_DEPLOYMENT_GUIDE.md` and
`docs/DATAIKU_PM_REPORTS_WALKTHROUGH.md` describe how to also run it from inside Dataiku DSS —
that step (actual DSS provisioning) has not been done yet.

## 9. Validation plan — COMPLETED
1. ✅ All 22 scenarios in [test_strategy/TEST_STRATEGY_DATAIKU_SLICE.md](test_strategy/TEST_STRATEGY_DATAIKU_SLICE.md) implemented as pytest (`tests/test_pair_registry_slice.py`, `tests/test_uat_08_pm_reports.py`, `tests/test_uat_09_ingest.py`) — 26 passed, 1 documented `xfail` (real pre-existing gap, `BACKLOG-DM-002`, not silently patched).
2. ✅ Dry-run validated for `recipe_refresh_pm_candidates`'s script and for `uat_09` — zero writes confirmed.
3. ✅ `PairRegistry.schema_migrate()` run twice — idempotent (scenario #22 passes).
4. ✅ Governance Auditor re-run against the implemented code — first pass FAIL (found a real bug), fixed, re-verified against real data twice, second pass **PASS**. See `governance/IMPLEMENTATION_REVIEW.md`.

## 9a. Governance audit — two rounds, final verdict PASS
See [governance/PRE_IMPLEMENTATION_AUDIT_DATAIKU_SLICE.md](governance/PRE_IMPLEMENTATION_AUDIT_DATAIKU_SLICE.md)
(design-stage: PASS_WITH_WARNINGS) and [governance/IMPLEMENTATION_REVIEW.md](governance/IMPLEMENTATION_REVIEW.md)
(post-implementation: FAIL → fixed → **PASS**, this is the one to read first).

## 10. Rollback plan
All new artifacts are additive (new files/folders/methods); nothing existing is modified or deleted.
Rollback = do not deploy the new recipes/Managed Folders/variables; delete the new Parquet files under
`data/lineage/` if a trial run needs to be reverted; `uat_08`/`uat_09` continue to function unchanged
whether or not the new methods exist (guarded by `hasattr`/try-except when wired in).

## 11. Permissions / administrator dependencies
- Native Snowflake connector for Process #1 (optional, not required today).
- New Managed Folders (`pm_candidates_current`, `run_manifests`, `uat_reports_decile` wiring) — Dataiku
  project admin action.
- SharePoint connector for Process #4 inbound/outbound — not assumed; generic folder interface only.

## 12. Release checklist — code-side items done, Dataiku-side items pending
- [x] All 22 test scenarios pass (26 passed, 1 documented xfail)
- [x] Dry-run validated for each new/changed script
- [ ] `docs/governance/RELEASE_GATE.md` checklist completed (this is a release-to-production gate, run it when actually promoting)
- [x] `ARCHITECTURE.md` version bumped (v2.7.15, "PairRegistry Extension — Operational PM Reports Slice")
- [x] `docs/governance/BACKLOG.md` updated (BACKLOG-007 closed; BACKLOG-DM-001/002/003/007 added)
- [x] Governance Auditor sign-off on the implemented code (`governance/IMPLEMENTATION_REVIEW.md` — PASS)
- [ ] Dataiku Managed Folders + variables actually provisioned in a real DSS project (admin action, not done)
- [ ] Recipes actually run inside DSS at least once (blind, predict, refresh, ingest) — not done, only run locally

## 13. Known limitations
- Snowflake native connector mode is unverified (no connection exists to test against) —
  `--source-type snowflake_native` raises `NotImplementedError` on purpose.
- SharePoint folder mapping is generic; exact behavior depends on whatever connector/folder Dataiku
  admins eventually provision.
- The dynamic blind/predict exclude-list improvement (BACKLOG-DM-001) is optional and deferred.
- `uat_09`'s `ISO_TO_SLUG` is missing 8 markets present in `uat_08`'s copy, including South Korea
  (BACKLOG-DM-003) — pre-existing gap, not introduced by this work, not fixed.

## 14. Where to start (actually deploying this to Dataiku)
1. Read [governance/IMPLEMENTATION_REVIEW.md](governance/IMPLEMENTATION_REVIEW.md) first — confirms
   the code is governance-approved and lists exactly what changed.
2. Read `docs/DATAIKU_DEPLOYMENT_GUIDE.md` §1 and §2 — Managed Folder + variable checklist, now
   including `pm_candidates_current` and the `uat_reports_decile` requirement for the predict recipe.
3. Read `docs/DATAIKU_PM_REPORTS_WALKTHROUGH.md` for the step-by-step blind/predict deployment
   (already updated §5.5 to reflect the BACKLOG-007 fix).
4. Provision the Managed Folders/variables in your actual DSS project (this is the one remaining
   step nobody has done yet — requires DSS project access).
5. Run each recipe once manually in DSS and compare its output against the equivalent local run
   already validated in this repo.
