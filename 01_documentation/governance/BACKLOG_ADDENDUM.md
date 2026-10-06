# BACKLOG addendum (proposed — NOT applied to docs/governance/BACKLOG.md)

These items are proposed additions for governance review before being copied into the real
`docs/governance/BACKLOG.md`. This file does not modify that document.

| ID (proposed) | Title | Category | Priority | Status |
|---|---|---|---|---|
| BACKLOG-DM-001 | Implement `recipe_refresh_pm_candidates.py` + script (Process #1 currently missing) | Dataiku | MEDIUM | OPEN |
| BACKLOG-DM-002 | Materialize `AUTOMATION_POLICY` as a `PairRegistry`-backed, read-only derived table | Dataiku / Pair Registry | MEDIUM | OPEN |
| BACKLOG-DM-003 | Materialize `INGESTED_FILE_REGISTRY` in `PairRegistry` (subsumes ad-hoc hash logic in uat_09) | Pair Registry / Lineage | MEDIUM | OPEN |
| BACKLOG-DM-004 | Dynamic blind/predict exclude-list driven by `AUTOMATION_POLICY` instead of hand-maintained `PM_EXCLUDE_COUNTRIES` | Dataiku / Operational drift | LOW | OPEN — improvement, not a defect |
| BACKLOG-DM-005 | Add the 22 test scenarios from `test_strategy/TEST_STRATEGY_DATAIKU_SLICE.md` | Testing | MEDIUM | OPEN |
| BACKLOG-DM-006 | (Existing) BACKLOG-007 — add `--reports-decile-dir` to `uat_08_generate_pm_reports.py` | Dataiku | already tracked | OPEN (cross-reference only) |

Cross-references: `docs/governance/BACKLOG.md` BACKLOG-007, `docs/governance/KNOWN_FAILURES.md`
KNOWN-DEVIATION-001/003/004, FAILURE-018.
