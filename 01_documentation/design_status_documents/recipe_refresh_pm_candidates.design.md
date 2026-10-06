# Design: Process #1 — Refresh PM Candidates

**As-is today**: no recipe/script exists. Snowflake extracts are manually uploaded as CSVs into the
`snowflake_extracts` Managed Folder; `uat_08._find_extract()` reads the most recent file per market
directly at report-generation time — there is no separate, auditable "snapshot" step.

**Target (per user decision — design for a future native connector, CSV upload as today's fallback)**

## Script (future): `scripts/dataiku_refresh_pm_candidates.py`
Thin orchestration script (reused logic, not duplicated):
1. Reuse `uat_08._find_extract()` / `EXTRACT_SELECTION_POLICY` for per-market file discovery when
   `--source-type csv_manual_upload` (default today).
2. When `--source-type snowflake_native --snowflake-dataset <name>` is passed (future, once an
   administrator provisions a Dataiku-Snowflake connection — see IMPLEMENTATION_MANUAL.md
   "Administrator Dependencies"), read via `dataiku.Dataset(name).get_dataframe()` instead. The rest
   of the pipeline (validation, pair_id, dedup, manifest) is identical regardless of source.
3. Reuse `uat_08._build_pair_id()` verbatim (import, do not copy) for canonical `pair_id` construction.
4. Validate: reject rows missing the two profile-URI columns needed for `pair_id` (D1 requirement:
   "Debe fallar si faltan las columnas indispensables para pair_id") — count as `row_status=invalid`.
5. Deduplicate by `(market_iso, pair_id)` using the same tie-break as `_find_extract` (mtime desc,
   size desc) when the same pair appears in more than one source file.
6. Write `PM_CANDIDATES_CURRENT` per [contracts/PM_CANDIDATES_CURRENT.schema.yaml](../contracts/PM_CANDIDATES_CURRENT.schema.yaml)
   via staged write + atomic publish (new snapshot dir per run + "latest" pointer update last).
7. Write a `RUN_MANIFEST` entry per [contracts/RUN_MANIFEST.schema.yaml](../contracts/RUN_MANIFEST.schema.yaml).

## CLI flags (P0.3 pattern, consistent with existing uat_* scripts)
```
--source-type {csv_manual_upload|snowflake_native}   default: csv_manual_upload
--extracts-dir PATH        # csv_manual_upload mode; mirrors uat_08's --extracts-dir
--snowflake-dataset NAME   # snowflake_native mode; Dataiku dataset name (admin-provisioned)
--countries / --exclude-countries   # same semantics as uat_08
--output-dir PATH          # pm_candidates_current Managed Folder mount
--run-id / --dry-run       # same semantics as other uat_* scripts
```

## Recipe (future): `dataiku/recipes/recipe_refresh_pm_candidates.py`
Thin wrapper, same pattern as existing recipes (framework-root discovery, `dataiku.Folder()` /
`dataiku.Dataset()` resolution, build argv, `subprocess.run(check=True)`).

New Managed Folder required: `pm_candidates_current` (output). New project variable:
`PM_CANDIDATES_INPUT` = `snowflake_extracts` (folder name) or a Dataiku dataset name, resolved by the
recipe based on `source_type`.

## What this explicitly does NOT do (restriction L)
- Does not call `predict()`, does not touch `models/`.
- Does not decide automation approvals (that is `AUTOMATION_POLICY`, a separate read-only derivation).
- Does not read/write `RESOLVED_PAIR_REGISTRY` (anti-join happens in Process #2/#3, which read
  `PM_CANDIDATES_CURRENT.latest` + `RESOLVED_PAIR_REGISTRY` independently).

## Administrator dependency
The `snowflake_native` mode requires: a Dataiku-Snowflake connection object, and either a shared
dataset or a project-level SQL query definition — both are DBA/Dataiku-admin actions and are **not**
assumed to exist. Until provisioned, `csv_manual_upload` remains the only supported mode, and the
manifest's `source_type` field makes this explicit and auditable per run.
