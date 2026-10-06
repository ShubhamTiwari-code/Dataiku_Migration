# Governance continuity: keeping control when maintenance moves to Dataiku

Addresses the concern: *"es altamente probable perder la gobernanza de esta tarea"* once part of the
Operational PM Reports Slice's state (resolved pairs, automation policy) is maintained from Dataiku
instead of the local framework.

## Why the risk is real
Today, every governance guarantee (RULE-002/006/024/025/026, FAILURE-018/019 fixes, the reconciliation
waterfall) is enforced by code that lives in `scripts/` and is reviewed the same way as the rest of the
repository — one Git history, one test suite, one `SYSTEM_STATE.md`. Once `RESOLVED_PAIR_REGISTRY` /
`AUTOMATION_POLICY` are *maintained* (not just read) from Dataiku, a second, less-reviewable place
starts mutating state that governance rules depend on. Two failure modes to guard against:
1. **Drift**: Dataiku-side data diverges from what the repository's own artifacts (`paso_6_...json`,
   `uat/reports_decile/*.csv`, `data/lineage/steward_events.parquet`) would say, with no one noticing.
2. **Silent control bypass**: someone edits a Dataiku dataset/Managed Folder directly (outside any
   recipe), and the rule the recipe enforced (e.g., RULE-026 exclusion) is bypassed without a trace.

## Mitigations (design decisions, apply from the first bootstrap onward)
1. **One-way data flow, not shared ownership.** The local framework's artifacts
   (`paso_6_model_strategy_decision.json`, `uat/reports_decile/*.csv`, `data/lineage/*.parquet`) remain
   the sole systems of record for *approvals* and *training/prediction lineage*. Dataiku's copies are
   explicitly downstream derivatives (see `AUTOMATION_POLICY.schema.yaml`: "read-only... never derives
   new approvals"). Only `RESOLVED_PAIR_REGISTRY` (steward decisions collected via Dataiku-hosted
   SharePoint ingestion) becomes genuinely Dataiku-authoritative going forward, because that is the one
   piece of state that must be captured wherever the ingestion actually runs.
2. **Every write carries a `RUN_MANIFEST`.** No Dataiku recipe may mutate `RESOLVED_PAIR_REGISTRY` or
   `INGESTED_FILE_REGISTRY` without emitting a manifest (`run_id`, `process_name`, counts, `status`).
   This is the Dataiku-side equivalent of a commit message — it is what gives a later audit something
   to check even though there is no Git history for the data itself.
3. **Periodic export back into the repository.** A read-only "mirror" script (future work, not part of
   this pass) should periodically pull the current `RESOLVED_PAIR_REGISTRY` from Dataiku and write a
   dated snapshot under `data/lineage/dataiku_mirror/` in the repo (or as a scheduled artifact), so
   `git log` on that folder becomes an audit trail even though the live system of record is Dataiku.
   Without this, `git blame` stops being able to answer "who resolved this pair and when."
4. **Rule citations travel with the code, not just the docs.** Every new Dataiku-side script/recipe
   must cite the `RULE-0xx` / `FAILURE-0xx` IDs it enforces in its own header comment (as already done
   in `dataiku/recipes/recipe_blind_pm_reports.py`), so a governance audit of the *Dataiku* codebase
   doesn't require re-deriving which rules apply — this is already the project's convention, this
   package just needs to keep applying it as pieces move to Dataiku.
5. **The bootstrap snapshot itself is the checkpoint, not a one-off.** Re-running
   [`bootstrap/snapshot_uat_and_pair_registry.py`](../bootstrap/snapshot_uat_and_pair_registry.py)
   periodically (even after Dataiku becomes the primary maintainer) gives governance a way to compare
   "what the local framework's artifacts would say today" against "what Dataiku currently has,"
   surfacing drift instead of assuming none occurred.
6. **RELEASE_GATE.md stays the single gate.** Nothing described in this package changes
   `docs/governance/RELEASE_GATE.md`; any change originating in Dataiku that affects production
   behavior (e.g., a market crossing into automation approval) must still be reflected in
   `SYSTEM_STATE.md`/`ARCHITECTURE.md` through the same review process as any other change — Dataiku
   is explicitly not exempted from the gate by being a different platform.

## What this does NOT solve
- It does not give the repository real-time visibility into Dataiku — mitigation #3 is periodic, not
  live. If real-time governance visibility is required, that is a genuine platform gap under the
  current permission constraints (no admin access to wire a live sync), and should be tracked as an
  explicit accepted risk in `docs/governance/KNOWN_FAILURES.md` once this package moves to
  implementation, not silently assumed away.
- It does not prevent a Dataiku admin from manually editing a Managed Folder's contents outside any
  recipe — that is a platform/process control (who has write access to Managed Folders), not something
  a script can enforce.
