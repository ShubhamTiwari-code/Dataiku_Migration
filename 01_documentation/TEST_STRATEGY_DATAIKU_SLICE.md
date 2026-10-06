# Test Strategy — Operational PM Reports Slice
Spec only — no test code in this pass. Maps every required scenario (prompt section I) to the exact
function/fixture it should exercise once implemented, so a future Agent-mode pass can write
`tests/test_pair_registry_slice.py`, `tests/test_uat_08_pm_reports.py`, `tests/test_uat_09_ingest.py`
directly from this table without re-deriving the mapping.

| # | Scenario | Target function(s) | Notes / existing fixture to reuse |
|---|---|---|---|
| 1 | `pair_id` symmetric: A\|B == B\|A | `uat_08._build_pair_id` | Synthetic 2-row DataFrame with swapped URI order |
| 2 | anti-join excludes resolved pairs | `uat_08._load_resolved` + `uat_08._dedup` | Fake `PairRegistry.get_resolved_pairs()` returning a known set |
| 3 | same input → same pending set (determinism) | `uat_08.run_pipeline` (single market) | Run twice on identical fixture, assert `df_pending` equal |
| 4 | same file not ingested twice | `uat_09._discover_pm_report_files` + new `PairRegistry.get_file_registry_entry` | Same bytes, same filename |
| 5 | renamed file, same hash, not re-ingested | same as #4 | Same bytes, different filename (simulate SharePoint suffix) |
| 6 | `DECISION_SOURCE=AUTOMATED` excluded | `uat_09.process_market` (AUTOMATED-exclusion branch) | Fixture row with `DECISION_SOURCE="AUTOMATED"` + a filled decision |
| 7 | human decision takes priority | `uat_09._normalize_decision` / `process_market` | Row with both `MERGE / NO MERGE / SUSPECT` and `DSR_DECISION` set to different values |
| 8 | legacy fallback works | `process_market` | Fixture with only `DSR_DECISION`, no `MERGE / NO MERGE / SUSPECT` column |
| 9 | unknown decision rejected | `uat_09._normalize_decision` (via `normalize_target`) | Value like `"Maybe"` — assert raise/reject, not silently coerced |
| 10 | in-file duplicates removed | `uat_09.process_market` dedup step | Two identical `pair_id` rows in one chunk |
| 11 | cross-chunk duplicates removed | `process_market` aggregation step | Same `pair_id` split across `set01`/`set02` |
| 12 | conflicting decisions logged | new `PairRegistry.record_conflict` | Same `pair_id`, different `normalized_decision` across two ingestion runs |
| 13 | market without policy → blind | `uat_08._load_decile_automation` returning `{}` | Missing/empty decile CSV fixture |
| 14 | wrong model hash → blind | `uat_08._check_model_drift` | Fixture model file with mismatched SHA-256 vs. fake manifest |
| 15 | unapproved bucket stays blind | `uat_08._maybe_reveal_predict` | Row whose `score_bucket` maps to `MANUAL` in the decile CSV |
| 16 | approved bucket reveals predict | `_maybe_reveal_predict` | Row whose `score_bucket` maps to `AUTO_MERGE`/`AUTO_NO_MERGE` |
| 17 | `n_auto_revealed + n_manual == n_records` | `_maybe_reveal_predict` reveal_info dict | Assert arithmetic on the returned `reveal_info` |
| 18 | no resolved pairs in report output | `uat_08.run_pipeline` end-to-end | Assert `set(df_output.pair_id) & resolved_ids == set()` |
| 19 | waterfall closes mathematically | `uat_09._append_waterfall_record` | Assert the closure_invariant documented in [RECONCILIATION_WATERFALL.schema.yaml](../contracts/RECONCILIATION_WATERFALL.schema.yaml) |
| 20 | dry-run modifies nothing | `run_pipeline(dry_run=True)` / `process_market(dry_run=True)` | Assert no files written under a tmp output dir |
| 21 | failure mid-registry-update ≠ SUCCESS | new `PairRegistry.record_ingested_file_start/_result` | Monkeypatch the registry-write call to raise between start and result |
| 22 | schema migration idempotent | `PairRegistry.schema_migrate` | Call twice on the same fixture parquet, assert identical resulting schema/row count |

## Fixture reuse policy
No real HCP data. Reuse the synthetic-data generation patterns already present in
`tests/fixtures/` and in `test_inference.py` / `test_encoder.py` (synthetic profile pairs with
fabricated URIs, names, and scores) rather than sampling any file under `uat/` or `data/`.

## Blocking dependency
Scenarios 4, 5, 12, 21, 22 require the new `PairRegistry` methods from
[pair_registry_extension.design.md](../design/pair_registry_extension.design.md) to exist first —
they cannot be written against the current class.
