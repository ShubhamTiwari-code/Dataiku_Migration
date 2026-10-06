# Application: Singular / PM Automation
# Phase 11b — UAT status chain step 4a: Generate combined Phase 11b decile report
# Dataiku Python recipe — thin wrapper over scripts/uat_07_generate_11b_report.py
#
# Sequence: run AFTER recipe_uat_11_manifest.py (consumes its phase11b_run_manifest_{date}.json
# for RULE-006 Run_ID/Dataset_Version/Model_Version fields — KNOWN-DEVIATION-007). Parallel-safe
# with recipe_uat_10_evidence.py, recipe_uat_12_attainability.py, recipe_uat_13_status.py.
#
# Required Managed Folders:
#   uat_reports_decile : input (mirrors uat/reports_decile/)
#   uat_manifest       : input (phase11b_run_manifest_{date}.json, from uat_11)
#   uat_reports        : input, Phase 11 legacy analyses for comparison (mirrors uat/reports/)
#   reports            : output, combined UAT_EXTENDED_RESULTS_11b_*.md (mirrors top-level reports/)
#
# Note: this script also reads docs/ARCHITECTURE.md (for the live pipeline version string) via
# a path relative to FRAMEWORK_ROOT — works unmodified since the DSS project library clone
# includes docs/.

import os
import subprocess
import sys
from pathlib import Path

import dataiku

FRAMEWORK_ROOT = None
for _p in sys.path:
    if _p and (Path(_p) / "scripts" / "uat_07_generate_11b_report.py").exists():
        FRAMEWORK_ROOT = _p
        break
if not FRAMEWORK_ROOT:
    raise EnvironmentError(
        "Framework not found in sys.path. "
        "Ensure the project library is configured from the PM_GLOBAL_SOLUTION Git repo."
    )
script = str(Path(FRAMEWORK_ROOT) / "scripts" / "uat_07_generate_11b_report.py")

reports_decile_dir = dataiku.Folder("uat_reports_decile").get_path()
manifest_dir = dataiku.Folder("uat_manifest").get_path()
phase11_reports_dir = dataiku.Folder("uat_reports").get_path()
output_dir = dataiku.Folder("reports").get_path()

cmd = [
    sys.executable,
    script,
    "--reports-decile-dir",
    reports_decile_dir,
    "--manifest-dir",
    manifest_dir,
    "--phase11-reports-dir",
    phase11_reports_dir,
    "--output-dir",
    output_dir,
]

subprocess.run(cmd, check=True, env={**os.environ, "PYTHONPATH": FRAMEWORK_ROOT}, text=True)
