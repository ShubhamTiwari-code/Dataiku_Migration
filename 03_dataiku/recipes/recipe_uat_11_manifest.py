# Application: Singular / PM Automation
# Phase 11b — UAT status chain step 3: Build the unified Phase 11b run manifest
# Dataiku Python recipe — thin wrapper over scripts/uat_11_build_run_manifest.py
#
# Sequence: run AFTER recipe_uat_06_pool.py, BEFORE recipe_uat_07_report.py and
# recipe_uat_13_status.py (both consume the manifest this produces for RULE-006
# Run_ID/Dataset_Version/Model_Version traceability fields — see KNOWN-DEVIATION-007).
#
# Required Managed Folders:
#   uat_manifest        : output (phase11b_run_manifest_{date}.json), also read (per-country
#                         manifests + reconciliation waterfall live here)
#   uat_reports_decile  : input (mirrors uat/reports_decile/)
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
    if _p and (Path(_p) / "scripts" / "uat_11_build_run_manifest.py").exists():
        FRAMEWORK_ROOT = _p
        break
if not FRAMEWORK_ROOT:
    raise EnvironmentError(
        "Framework not found in sys.path. "
        "Ensure the project library is configured from the PM_GLOBAL_SOLUTION Git repo."
    )
script = str(Path(FRAMEWORK_ROOT) / "scripts" / "uat_11_build_run_manifest.py")

manifest_dir = dataiku.Folder("uat_manifest").get_path()
reports_decile_dir = dataiku.Folder("uat_reports_decile").get_path()

cmd = [
    sys.executable,
    script,
    "--manifest-dir",
    manifest_dir,
    "--reports-decile-dir",
    reports_decile_dir,
]

subprocess.run(cmd, check=True, env={**os.environ, "PYTHONPATH": FRAMEWORK_ROOT}, text=True)
