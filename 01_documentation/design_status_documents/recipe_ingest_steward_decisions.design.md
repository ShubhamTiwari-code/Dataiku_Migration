# Design: Process #4 — Ingest Steward Decisions

**As-is today**: [`dataiku/recipes/recipe_uat_09_process.py`](../../dataiku/recipes/recipe_uat_09_process.py)
already wraps [`scripts/uat_09_process_pm_report_decisions.py`](../../scripts/uat_09_process_pm_report_decisions.py),
which already implements almost everything required by prompt section D4:
- file discovery tolerant of legacy names, `reviewed_` prefix, and SharePoint suffixes (`_discover_pm_report_files`)
- blindness validation with the `DECISION_SOURCE`-present exception (`_check_blindness`, FAILURE-018 fix)
- decision normalization with `MERGE / NO MERGE / SUSPECT` prioritized over legacy `DSR_DECISION` (`_normalize_decision`)
- unconditional `DECISION_SOURCE == AUTOMATED` exclusion (FAILURE-019 fix)
- in-file and cross-file dedup by `pair_id`
- anti-join against already-resolved pairs (`_load_resolved_pair_ids`)
- an append-only reconciliation waterfall (`_append_waterfall_record`)
- recording to `PairRegistry.record_steward_review()`

**What is genuinely missing**: hash-based file-level idempotency is not a queryable, standalone
contract — a file's "already processed" status lives implicitly in whether its rows already appear
in `results_non_uat` CSVs, not in an explicit `INGESTED_FILE_REGISTRY` keyed by SHA-256.

## Target changes (future implementation — described here, not applied)
1. At the top of `process_market()` (or a new wrapper around `_discover_pm_report_files()`), compute
   `file_hash = sha256(file_bytes)` per discovered chunk and call
   `PairRegistry.get_file_registry_entry(file_hash)`. If found with `status == SUCCESS`, skip the file
   entirely (covers "same file re-ingested" AND "renamed file with identical content" — test
   scenarios #4/#5).
2. Call `record_ingested_file_start()` before writing anything, and `record_ingested_file_result()`
   only after both the `results_non_uat` CSV write and the `PairRegistry.record_steward_review()` call
   have succeeded — matching the atomicity requirement (test scenario #21).
3. Feed the same counts already computed for the existing waterfall
   (`raw_rows`, `rows_with_decision`, `automated_prefill_excluded`, dedup counts, `already_resolved`)
   into the new `record_ingested_file_result()` call so `INGESTED_FILE_REGISTRY` and
   `RECONCILIATION_WATERFALL` never disagree (single source of truth for the numbers).
4. Route conflicting decisions (same `pair_id`, different `normalized_decision` across ingestion runs)
   through the new `PairRegistry.record_conflict()` instead of silently keeping the first-seen value —
   today's implicit behavior (`drop_duplicates(keep="first")`) already avoids double-counting but does
   not surface a conflict signal; this closes that gap per the `RESOLVED_PAIR_REGISTRY.conflict_policy`.

## Recipe changes
None required at the recipe level — `recipe_uat_09_process.py` stays a thin wrapper; all of the above
lives inside `uat_09_process_pm_report_decisions.py` and `pair_registry.py`.

## Explicitly out of scope (restriction L)
- Does not change the `ELIGIBLE_ISO` allow-list mechanism (a separate, already-tracked issue —
  FAILURE-018 recurrence — not part of this design package).
- Does not change decision-normalization semantics or the legacy `DSR_DECISION` fallback rule.

## Governance rule citation
- **RULE-026** (source eligibility — `DECISION_SOURCE == AUTOMATED` is never valid evidence): the new
  `decision_source` parameter on `record_steward_review()` (see
  [pair_registry_extension.design.md](pair_registry_extension.design.md)) makes RULE-026 enforceable
  at the `RESOLVED_PAIR_REGISTRY` contract level, in addition to `uat_09`'s existing in-process check.
