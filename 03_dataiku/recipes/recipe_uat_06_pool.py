# Application: Singular / PM Automation
# Phase 11b — UAT status chain step 2: Pool all sources and analyze by decile
# Dataiku Python recipe — thin wrapper over scripts/uat_06_pool_and_analyze.py
#
# Sequence: run AFTER recipe_uat_09_process.py, BEFORE recipe_uat_11_manifest.py.
#
# Required Managed Folders:
#   uat_internal          : input (mirrors uat/internal/)
#   uat_results           : input (mirrors uat/results/)
#   uat_results_non_uat   : input (mirrors uat/results_non_uat/, written by uat_09)
#   uat_internal_11b      : input, Track 3 supplement (mirrors uat/internal_11b/)
#   uat_results_11b       : input, Track 3 supplement (mirrors uat/results_11b/)
#   uat_reports_decile    : output, updated decile analyses (mirrors uat/reports_decile/)
#   uat_manifest          : input, per-country run manifests for model-drift check
#   models                : input (read-only), routing JSON + PKLs
#   reports               : input (read-only), Design-C sample-size CSV (top-level reports/)
#
# Governance: RULE-024/RULE-025 (automation gating, model-drift fail-closed) enforced inside
# uat_06 (_compute_metrics(), _action_specific_fields()).

import os
import subprocess
import sys
from pathlib import Path

import dataiku

FRAMEWORK_ROOT = None
for _p in sys.path:
    if _p and (Path(_p) / "scripts" / "uat_06_pool_and_analyze.py").exists():
        FRAMEWORK_ROOT = _p
        break
if not FRAMEWORK_ROOT:
    raise EnvironmentError(
        "Framework not found in sys.path. "
        "Ensure the project library is configured from the PM_GLOBAL_SOLUTION Git repo."
    )
script = str(Path(FRAMEWORK_ROOT) / "scripts" / "uat_06_pool_and_analyze.py")

internal_dir = dataiku.Folder("uat_internal").get_path()
results_dir = dataiku.Folder("uat_results").get_path()
results_non_uat_dir = dataiku.Folder("uat_results_non_uat").get_path()
internal_11b_dir = dataiku.Folder("uat_internal_11b").get_path()
results_11b_dir = dataiku.Folder("uat_results_11b").get_path()
reports_decile_dir = dataiku.Folder("uat_reports_decile").get_path()
manifest_dir = dataiku.Folder("uat_manifest").get_path()
models_dir = dataiku.Folder("models").get_path()
simplified_sizes_csv = str(
    Path(dataiku.Folder("reports").get_path()) / "uat_simplified_table1_sample_sizes.csv"
)

cmd = [
    sys.executable,
    script,
    "--include-track3",
    "--internal-dir",
    internal_dir,
    "--results-dir",
    results_dir,
    "--results-non-uat-dir",
    results_non_uat_dir,
    "--internal-11b-dir",
    internal_11b_dir,
    "--results-11b-dir",
    results_11b_dir,
    "--reports-decile-dir",
    reports_decile_dir,
    "--manifest-dir",
    manifest_dir,
    "--models-dir",
    models_dir,
    "--simplified-sizes-csv",
    simplified_sizes_csv,
]

subprocess.run(cmd, check=True, env={**os.environ, "PYTHONPATH": FRAMEWORK_ROOT}, text=True)
