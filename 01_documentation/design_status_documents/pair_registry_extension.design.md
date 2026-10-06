# Design: PairRegistry extension for the Operational PM Reports Slice

**Target file (future implementation, NOT modified in this pass)**: [`src/lineage/pair_registry.py`](../../src/lineage/pair_registry.py)

## Why extend PairRegistry directly (per decision)
Rather than a parallel adapter module, the three missing contracts become new Parquet-backed tables
inside the same class, reusing its existing idempotency primitives:
- `_load(path, columns)` — safe read with schema defaulting
- `_append(path, new_rows)` — append-only event logs
- `_upsert_registry(new_rows)` pattern — upsert-by-key with `drop_duplicates(keep=...)`
- `schema_migrate()` — idempotent "add missing columns" migration

This keeps a single lineage subsystem instead of two, and reuses the already-audited
(KNOWN-DEVIATION-001/003) resolved-pairs query path.

## New storage files (under `data/lineage/`, matching existing convention)
| File | Contract | Notes |
|---|---|---|
| `automation_policy.parquet` | [AUTOMATION_POLICY](../contracts/AUTOMATION_POLICY.schema.yaml) | Full-replace per derivation run |
| `ingested_file_registry.parquet` | [INGESTED_FILE_REGISTRY](../contracts/INGESTED_FILE_REGISTRY.schema.yaml) | Append + in-place status update by `file_hash` |
| (no new file) | [RESOLVED_PAIR_REGISTRY](../contracts/RESOLVED_PAIR_REGISTRY.schema.yaml) view | Computed on read from existing `steward_events.parquet` + `pair_registry.parquet` |

## New methods (signatures only — design, not implementation)

```python
class PairRegistry:
    # --- AUTOMATION_POLICY -------------------------------------------------
    def upsert_automation_policy(self, df: pd.DataFrame, policy_version: str) -> None:
        """Full-replace automation_policy.parquet with a new derivation run's output.
        MUST be called only by the read-only derivation described in
        design/automation_policy_derivation.design.md — never invents new approvals here.
        Staged write + atomic replace (see IMPLEMENTATION_MANUAL.md)."""

    def get_automation_policy(
        self, market_iso: Optional[str] = None, approved_only: bool = False
    ) -> pd.DataFrame:
        """Read automation_policy.parquet, optionally filtered. approved_only=True returns only
        rows with approval_status == 'APPROVED', used by the predict-reveal gate and by the
        blind/predict routing improvement (see recipe_generate_blind_pm_reports.design.md)."""

    def get_markets_with_any_approval(self) -> FrozenSet[str]:
        """Convenience wrapper: market_iso values with >=1 APPROVED row. This is the proposed
        replacement for the hand-maintained PM_EXCLUDE_COUNTRIES variable."""

    # --- INGESTED_FILE_REGISTRY ---------------------------------------------
    def get_file_registry_entry(self, file_hash: str) -> Optional[dict]:
        """Lookup by content hash — used to short-circuit already-ingested files, including renames."""

    def record_ingested_file_start(self, file_hash: str, file_name: str, file_path: str, market_iso: str) -> None:
        """Insert/refresh a row with status=RUNNING-equivalent (processed_at=None). Must be called
        BEFORE any registry/waterfall mutation for this file (test scenario #21)."""

    def record_ingested_file_result(self, file_hash: str, result: dict) -> None:
        """Set counts + status (SUCCESS/FAILED) + processed_at. Only called AFTER
        RESOLVED_PAIR_REGISTRY has been durably updated for this file's rows."""

    # --- RESOLVED_PAIR_REGISTRY (Dataiku view) ------------------------------
    def record_steward_review(
        self, df_results: pd.DataFrame, uat_run_id: str, decision_source: Optional[pd.Series] = None
    ) -> None:
        """(existing method, ADDITIVE parameter) — decision_source defaults to None so every
        existing call site keeps working unchanged; new callers (future uat_09) pass the
        HUMAN/AUTOMATED/LEGACY_DSR_FALLBACK value they already compute in-memory today but
        currently discard before calling this method. Persisted as a new nullable column in
        _STEWARD_COLS via schema_migrate() (RULE-026: decision_source is what lets the
        RESOLVED_PAIR_REGISTRY view enforce that AUTOMATED rows are never counted as evidence)."""

    def get_resolved_pairs_dataiku_view(self, market_iso: Optional[str] = None) -> pd.DataFrame:
        """Flattened projection matching contracts/RESOLVED_PAIR_REGISTRY.schema.yaml, built by
        joining steward_events.parquet with pair_registry.parquet. Superset of the existing
        get_resolved_pairs() -> FrozenSet[str] (that method keeps working unchanged for uat_08/uat_09;
        this is an additive read path for the new ingestion recipe/manifests). Rows where
        decision_source is missing (pre-migration data, written before this column existed) are
        classified as LEGACY_DSR_FALLBACK, never AUTOMATED, per the RESOLVED_PAIR_REGISTRY
        conflict_policy fail-safe."""

    def record_conflict(self, market_iso: str, pair_id: str, existing_decision: str, incoming_decision: str, ingestion_run_id: str) -> None:
        """Write a record_status='conflict' row per contracts/RESOLVED_PAIR_REGISTRY.schema.yaml
        conflict_policy. Never overwrites the existing active decision."""

    def schema_migrate(self) -> None:
        """(existing method) — extend to also ensure automation_policy.parquet and
        ingested_file_registry.parquet exist with the current schema_version, additive-only."""
```

## Backward compatibility
- **Correction (PRE_IMPLEMENTATION_AUDIT finding F1)**: `record_steward_review()` gains one new
  OPTIONAL keyword parameter (`decision_source=None`) — this is a signature change, but every
  EXISTING call site keeps working unchanged because the default preserves current behavior.
  `get_resolved_pairs()`, `register_pairs()`, `record_training()`, `record_prediction()`,
  `record_uat()` are genuinely unchanged (no new parameters).
- `uat_08` requires ZERO changes to keep working. `uat_09` requires ONE additive change (future,
  not part of this design pass): pass its already-computed `decision_source` value into the new
  `decision_source=` parameter instead of discarding it, so `RESOLVED_PAIR_REGISTRY.decision_source`
  becomes populated going forward (RULE-026 traceability). Historical rows without it fall back to
  `LEGACY_DSR_FALLBACK` classification, never silently treated as `HUMAN` or `AUTOMATED`.
- `uat_08` reveal gate could later call `get_automation_policy()` instead of reading
  `uat/reports_decile/*.csv` directly, closing the KNOWN-DEVIATION-004 read pattern — that remains an
  optional follow-up, not a requirement of this design.

## Governance rule citations
- **RULE-004** (architecture changes require approval + `ARCHITECTURE.md` version bump): every new
  table/method here is a canonical-path/module-interface change and must be reflected in
  `ARCHITECTURE.md`'s "Dataiku DSS Integration Layer" section with a version bump before merge.
- **RULE-026** (source eligibility — `DECISION_SOURCE == AUTOMATED` is never valid human evidence):
  the `decision_source` field added here exists specifically so `RESOLVED_PAIR_REGISTRY` can enforce
  RULE-026 at the contract level, not just inside `uat_09`'s in-process logic.

## Idempotency
- `upsert_automation_policy` and the file-registry writes both follow: write to `*.tmp.parquet` →
  validate row counts/schema → `os.replace()` to the final path (atomic on the same filesystem).
- `record_ingested_file_start` / `record_ingested_file_result` are two separate calls specifically so
  that a crash between them leaves `status` at its pre-run value (never `SUCCESS`) — satisfies test
  scenario #21.
