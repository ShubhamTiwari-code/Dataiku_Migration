# Dataiku Argentina Pilot: Beginner Deployment Guide

**Purpose:** deploy the existing Argentina PM workflow in Dataiku DSS using CSV upload and a GitHub-hosted project library. This guide assumes you do not have a local coding environment.

**Important status:** this repository checkout is not deployable yet. The Dataiku recipe wrappers exist under `03_dataiku/recipes/`, but the scripts and Python package they launch are absent from `04_framework/scripts/` and `04_framework/src/`. The sample-input and managed-folder placeholder directories are also empty. Ask the repository owner to restore the implementation before attempting a run. This guide describes the intended setup and identifies checks needed because some documentation and wrappers disagree.

## 1. The simple picture

Think of the pieces this way:

- **GitHub project library:** the recipe instructions and reusable Python framework code. It is not the place for Argentina’s input data.
- **DSS Code Environment:** the Python runtime and packages that execute recipes. You do not need to install Python on your own computer, but a DSS administrator must provide this runtime.
- **Managed Folders:** file storage attached to the DSS project. They hold the incoming CSV, model files, reports, and decision files.
- **Recipes:** buttons in the Dataiku Flow that run code in order.
- **Project variables:** small settings telling recipes which market and folder to use.

Intended high-level flow:

```text
GitHub source code ──> DSS project library ──> Python recipes
                                               │
Argentina CSV ──> snowflake_extracts ──> refresh candidates
                                               │
                                               ├──> blind report ──> steward review
                                               │                         │
                                               │                         v
                                               └──> (predict only after approval)  decision ingestion
                                                                          │
                                                                          v
                                                        registry / next-cycle exclusion
```

The repository describes a `PM_CANDIDATES_CURRENT` snapshot between refresh and report generation. However, the visible blind and predict recipe wrappers pass `snowflake_extracts` directly to their scripts, not `pm_candidates_current`. The framework scripts are missing, so we cannot check whether they also read the snapshot internally. Have the code owner confirm and correct the Flow before relying on the snapshot as a report input.

## 2. Argentina readiness

Argentina is represented in the model artifacts:

- Country slug: `argentina`
- ISO country code: `AR`
- Model file: `model_custom_argentina.pkl`
- Routing entry: `CUSTOM` in `05_models/paso_6_model_strategy_decision.json`

`CUSTOM` means the routing artifact selects a country-specific model. It does **not** mean Argentina is approved for automatic decision reveal. The governance audit lists six automation-approved markets and does not include Argentina. The model artifacts also report different Argentina evaluation results, so begin with blind reports and human decisions. Do not enable automated reveal unless governance explicitly approves it and the required decile-policy artifact is current.

There is another blocking check: both visible report wrappers pass `--exclude-latam`. Argentina is in Latin America. Until the owner checks how the missing framework script applies this flag, do not run these wrappers for Argentina. It could exclude Argentina even when `PM_COUNTRIES=AR`.

## 3. What must be supplied before setup

Ask the project/code owner and DSS administrator for these items:

1. A complete GitHub branch or release containing `04_framework/scripts/`, `04_framework/src/`, and tests. At minimum, the wrappers refer to:
   - `scripts/dataiku_refresh_pm_candidates.py`
   - `scripts/uat_08_generate_pm_reports.py`
   - `scripts/uat_09_process_pm_report_decisions.py`
2. The supported Python version and pinned package list/lock file for the framework. None is present in this checkout.
3. The Argentina source CSV and an authoritative column map. The candidate contract requires market identity plus the two entity/profile URIs used to form `pair_id`; exact source header names are not available here.
4. Confirmation of extract filename/discovery conventions and expected report filenames.
5. A decision on the two wiring differences: report recipes appear to read raw extracts instead of the refreshed candidate snapshot; `--exclude-latam` appears in both blind and predict wrappers.
6. A DSS administrator to provide Git access, a Python Code Environment, and Managed Folders.

Do not guess the missing CSV headers, Python dependencies, or market eligibility rules.

## 4. Step A: connect GitHub to the Dataiku project library

This is configured inside Dataiku; no local IDE is required.

1. Open the DSS project and its **Libraries** or **Project libraries** editor. The precise menu label varies by DSS version.
2. Choose **Git > Import from Git**.
3. Enter the repository URL. Select a reviewed branch, tag, or commit. For production, prefer a release tag or commit over a branch that changes unexpectedly.
4. Set the repository subpath to `04_framework` if that is where the owner restores the framework. Set the target library path so the imported library root contains `scripts/` and `src/` directly.
5. Click **Save and Retrieve** and verify that the library contains the required scripts.
6. Ask the DSS administrator to allow the Git remote. Use the organization-approved HTTPS or SSH authentication process; never paste credentials into recipe code or project variables.
7. Do not edit/push production code from Dataiku unless your team’s review process explicitly allows it. For updates, retrieve a reviewed commit and test it before promotion.

The recipe wrappers search `sys.path` for a library root containing `scripts/<expected_script>.py`. If the library import puts the repository root (rather than `04_framework`) on the path, the wrapper will not find the script. Verify this layout before running.

## 5. Step B: select the Python Code Environment

1. Ask the DSS administrator to create or select a Python Code Environment compatible with the framework’s pinned dependencies.
2. The administrator installs the supplied package list and builds the environment.
3. In project settings, select that environment for the Python recipes.
4. Test a trivial Python recipe or the platform’s environment check. Do not install arbitrary latest package versions: model serialization libraries such as scikit-learn can be version-sensitive.

A Python recipe still needs a server-side Python environment even though you personally have no coding environment. The Code Environment is managed in DSS.

## 6. Step C: create the project variables

In the project’s variables settings, add these values for an Argentina-only pilot:

| Variable | Pilot value | Meaning |
|---|---|---|
| `PM_COUNTRIES` | `AR` | Run only Argentina in the PM report recipes. |
| `PM_EXCLUDE_COUNTRIES` | empty | Do not add an additional country exclusion. |
| `PM_CANDIDATES_INPUT` | `snowflake_extracts` | Input Managed Folder name for the refresh recipe. |
| `UAT_COUNTRIES` | `AR` | Used by the separate UAT score recipe; its format is space-separated. |
| `FORCE_RESCORE` | `false` | UAT score setting; leave default unless a controlled rescore is required. |

Do not set `PM_COUNTRIES=all` for the first pilot. The wrappers have different defaults for `PM_EXCLUDE_COUNTRIES`; set it explicitly so a previous project value does not surprise you.

## 7. Step D: create Managed Folders and load files

Create these DSS Managed Folders using the exact names because recipes refer to them by name:

| Managed Folder | Direction | What belongs there |
|---|---|---|
| `snowflake_extracts` | Input | The approved Argentina CSV extract. CSV/manual upload is the supported source mode in this repository. |
| `models` | Input, read-only for these recipes | `model_custom_argentina.pkl`, `paso_6_model_strategy_decision.json`, and `models_manifest.json` from the same approved release. Other UAT steps may require additional model artifacts. |
| `pm_candidates_current` | Output | Refreshed candidate snapshots and manifest/pointer artifacts according to the framework implementation. |
| `pm_reports` | Output | Generated Excel reports for human review. |
| `uat_reports_decile` | Input, read-only | Decile analysis/policy CSVs used by the predict reveal gate. Do not use this to grant Argentina approval. |
| `uat_non_uat_decisions` | Input for decision ingestion | Steward-returned report chunks, if this UAT decision-ingestion path is in scope. |
| `uat_results` | Input for decision ingestion | Existing blind-UAT anti-join source required by the visible `recipe_uat_09_process.py` wrapper. |
| `uat_results_non_uat` | Output for decision ingestion | Processed decisions from that wrapper. |

Upload the Argentina CSV into `snowflake_extracts` through the DSS folder interface. Validate that it is the intended period and contains the owner-confirmed required columns before executing a recipe. Keep model files separate from extract files.

The manual describes manifests in a separate `run_manifests` folder in one place, but also says the implemented scripts currently write manifest JSON beside output and that a separate folder is not needed. Confirm the actual implementation and use one agreed location; do not create a second, competing manifest process.

## 8. Step E: understand and run the recipes in order

A Dataiku recipe is a saved program node in the Flow. Open the recipe, select the Code Environment, verify its inputs/outputs, then use **Run**. Review the job log and output before continuing.

### E1. Refresh candidate snapshot

Recipe: `03_dataiku/recipes/recipe_refresh_pm_candidates.py`.

In plain words: it gets the folder paths and market settings from DSS, finds `dataiku_refresh_pm_candidates.py` in the imported Git library, and launches it with the Argentina input and candidate output locations. It does not itself contain the candidate-building logic.

Run this first after the missing script has been restored. Expected result per the contract:

- A new snapshot under `pm_candidates_current/<run_id>/`.
- A candidate Parquet file, with a `latest` pointer updated only after the snapshot is complete.
- A run manifest recording status, source type, row counts, invalid rows, duplicate count, and market list.
- For valid rows, the required identity columns include `market_iso=AR`, `market_slug=argentina`, and canonical `pair_id`.

The contract says `pair_id` is symmetric: the URI pair is sorted consistently, so swapping the two source URIs does not create a new pair. Invalid URI rows should be counted/rejected, not silently treated as valid.

### E2. Generate a blind report

Recipe: `03_dataiku/recipes/recipe_blind.py`.

In plain words: it launches `uat_08_generate_pm_reports.py` in non-UAT mode without the `--predict` switch. The intended output is an Excel report with predictions hidden from the steward, plus a `Report_Info` sheet for traceability.

Before running, the owner must resolve the `--exclude-latam` issue and confirm which input it consumes (raw CSV or candidate snapshot). Run only with `PM_COUNTRIES=AR` and inspect the job log to ensure Argentina was actually processed. A successful job that generated zero Argentina rows is not a successful pilot.

### E3. Human review

1. Review the generated report with the authorized Argentina steward.
2. The steward marks decisions using the organization’s approved template and does not alter identifiers or hidden/model-only fields.
3. Transfer the returned file into the agreed inbound location. Confirm the exact folder handoff with the owner; the generic SharePoint integration is not configured in this repository.
4. Keep the original report and returned file associated with the run for audit.

### E4. Process returned decisions, if this path is in scope

Recipe: `03_dataiku/recipes/recipe_uat_09_process.py`.

This visible recipe expects `uat_non_uat_decisions`, `uat_results`, `uat_results_non_uat`, and `models`. It calls the missing `uat_09_process_pm_report_decisions.py` script. This recipe belongs to the UAT/status chain; confirm with the system owner before using it as the operational SharePoint ingestion process. The implementation manual describes separate future/operational ingestion wiring, so do not assume they are interchangeable.

Only run ingestion once the returned file is validated. Check its manifest, processed-file registry, resolved-pair changes, and error log before the next report cycle. Human/steward decisions are not the same as automated model decisions.

### E5. Predict report (not part of the initial Argentina pilot)

Recipe: `03_dataiku/recipes/recipe_predict_pm_reports.py`.

This wrapper always passes `--predict` and uses model and decile Managed Folders. The underlying framework is intended to fail safe to blind when routing, model-hash, or approved-decile gates fail. That fail-safe is not an Argentina approval. Do not run this for production Argentina until there is explicit governance approval, a current decile policy, verified matching model hashes, and the `--exclude-latam` behavior is fixed and tested.

## 9. What the recipe wrapper code does

All wrappers follow the same pattern. Here is the shape of the existing refresh wrapper, simplified only by omitting comments:

```python
import os
import subprocess
import sys
from pathlib import Path
import dataiku

framework_root = None
for path in sys.path:
    if path and (Path(path) / "scripts" / "dataiku_refresh_pm_candidates.py").exists():
        framework_root = path
        break
if not framework_root:
    raise EnvironmentError("Framework scripts were not found in the DSS project library")

variables = dataiku.get_custom_variables()
input_dir = dataiku.Folder(
    variables.get("PM_CANDIDATES_INPUT", "snowflake_extracts")
).get_path()
output_dir = dataiku.Folder("pm_candidates_current").get_path()

command = [
    sys.executable,
    str(Path(framework_root) / "scripts" / "dataiku_refresh_pm_candidates.py"),
    "--source-type", "csv_manual_upload",
    "--extracts-dir", input_dir,
    "--output-dir", output_dir,
    "--countries", variables.get("PM_COUNTRIES", "all"),
    "--exclude-countries", variables.get("PM_EXCLUDE_COUNTRIES", ""),
]
subprocess.run(
    command,
    check=True,
    env={**os.environ, "PYTHONPATH": framework_root},
    text=True,
)
```

What those lines mean:

- `dataiku.Folder(...).get_path()` asks DSS where the Managed Folder is mounted for this job. You should not hard-code a laptop or server filesystem path.
- `dataiku.get_custom_variables()` reads the project-level settings.
- `sys.executable` runs the child script with the selected recipe Python environment.
- `subprocess.run(..., check=True)` makes the recipe fail if the framework script exits with an error.
- `PYTHONPATH` lets the script import the framework package from the project library.

The actual wrappers are the source of truth for their current arguments: [refresh](../03_dataiku/recipes/recipe_refresh_pm_candidates.py), [blind report](../03_dataiku/recipes/recipe_blind.py), [predict report](../03_dataiku/recipes/recipe_predict_pm_reports.py), and [decision processing](../03_dataiku/recipes/recipe_uat_09_process.py). The simplified snippet is explanatory; do not replace a production wrapper with it without code review.

## 10. Expected final output and acceptance checks

The first pilot is complete only when all these checks pass:

1. The refresh job status is `SUCCESS`, not merely “finished.” Its manifest identifies the run and says it processed `AR`/`argentina`.
2. The latest candidate snapshot exists, has a nonzero row count if the source was expected to contain candidates, and has no null/blank `market_iso`, `market_slug`, or `pair_id` on valid rows.
3. Invalid and duplicate rows are counted in the manifest. Explain any unexpectedly high count before continuing.
4. The blind report output exists in `pm_reports`, is for Argentina, and includes the traceability/`Report_Info` information. The report should not expose predict scores to the steward in this first pilot.
5. The run log confirms Argentina was not silently excluded by `--exclude-latam` and that the intended input snapshot/source was consumed.
6. A steward-reviewed file can be ingested only through the agreed, validated process; its manifest and registry changes are auditable.
7. There are no unexplained model/hash warnings, failed gates, missing files, or unexpected zero-row outputs.

The exact report filename and workbook columns must be confirmed from the restored framework and the business owner; they are not specified by the code present in this checkout.

## 11. Troubleshooting in plain language

| Message or symptom | Likely reason | Action |
|---|---|---|
| “Framework not found in sys.path” | Git library is missing, wrong branch/subpath, or wrong target/source path. | Verify the imported root contains `scripts/` and retrieve the reviewed Git reference. |
| “No such file” for a script | The framework source was not restored or the wrong Git commit was imported. | Ask the code owner for the complete implementation; do not create a fake replacement script. |
| “No module named …” | The selected DSS Code Environment lacks a required package. | Ask the administrator to install the pinned dependency set. |
| Folder not found | Managed Folder name differs from recipe code or the project lacks permission. | Compare names exactly and ask the project admin to grant access. |
| Successful run, but no Argentina output | Wrong country setting, filename/columns not recognized, or `--exclude-latam` excluded the market. | Check job logs, variables, source mapping, and exclusion handling. |
| Predict recipe reports blind/degraded | Routing, model hash, or decile-policy gate is absent or mismatched. | Keep manual review; have model governance investigate. Do not bypass the gate. |
| Candidate snapshot created but report seems to use another source | Visible wrappers pass `snowflake_extracts` to the report script. | Confirm and fix candidate-snapshot wiring before claiming the report uses `PM_CANDIDATES_CURRENT`. |

## 12. Production promotion checklist

- [ ] Complete framework restored to the selected, reviewed Git release.
- [ ] `--exclude-latam` behavior tested and Argentina is included when requested.
- [ ] Report recipe input is confirmed to be the intended source/snapshot.
- [ ] DSS Code Environment and package versions are documented and reproducible.
- [ ] Argentina input column mapping, period, and row counts approved by data owner.
- [ ] Model artifact hashes agree with the model manifest and governance-approved release.
- [ ] Blind Argentina pilot reviewed and signed off by the authorized steward.
- [ ] Decision-ingestion route and registry/manifest ownership confirmed.
- [ ] Explicit governance approval recorded before any automated reveal is enabled.
- [ ] Scheduling, permissions, monitoring, rollback, and release gate approved.

## 13. Repository references

- [Implementation manual](implementation%20manuals/IMPLEMENTATION_MANUAL.md)
- [Post-implementation governance review](governance/IMPLEMENTATION_REVIEW.md)
- [Governance continuity](governance/GOVERNANCE_CONTINUITY.md)
- [Candidate data contract](../06_config/contracts/PM_CANDIDATES_CURRENT.schema.yaml)
- [Run manifest contract](../06_config/contracts/RUN_MANIFEST.schema.yaml)
- [Argentina model decision](../05_models/MODEL_DECISION.md)
- [Argentina routing and model metadata](../05_models/paso_6_model_strategy_decision.json)
- [Dataiku Git project-library instructions](https://doc.dataiku.com/dss/latest/collaboration/import-code-from-git.html)
- [Dataiku Python recipes](https://doc.dataiku.com/dss/latest/code_recipes/python.html)
- [Dataiku Code Environments](https://doc.dataiku.com/dss/latest/code-envs/index.html)
