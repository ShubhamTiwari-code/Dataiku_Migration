# Application: Singular / PM Automation
# Phase 11b — UAT status chain step 4d: Automated MARKET_STATUS / EXECUTIVE_SUMMARY generation
# Dataiku Python recipe — thin wrapper over
# scripts/uat_13_generate_market_status_and_exec_summary.py
#
# Sequence: run AFTER recipe_uat_11_manifest.py (consumes its manifest for traceability).
# Parallel-safe with recipe_uat_07_report.py, recipe_uat_10_evidence.py,
# recipe_uat_12_attainability.py.
#
# Required Managed Folders:
#   uat_reports_decile : input (mirrors uat/reports_decile/)
#   uat_manifest       : input (phase11b_run_manifest_{date}.json, from uat_11)
#   reports            : output, MARKET_STATUS_PHASE11b_*.md + EXECUTIVE_SUMMARY_PHASE11b_*.md
#                        (mirrors top-level reports/; also where phase11b_context_notes.md,
#                        a human-edited narrative input, is read from — not overridable, by
#                        design, since it is repo-tracked content, not a runtime artifact)
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
    if _p and (Path(_p) / "scripts" / "uat_13_generate_market_status_and_exec_summary.py").exists():
        FRAMEWORK_ROOT = _p
        break
if not FRAMEWORK_ROOT:
    raise EnvironmentError(
        "Framework not found in sys.path. "
        "Ensure the project library is configured from the PM_GLOBAL_SOLUTION Git repo."
    )
script = str(Path(FRAMEWORK_ROOT) / "scripts" / "uat_13_generate_market_status_and_exec_summary.py")

reports_decile_dir = dataiku.Folder("uat_reports_decile").get_path()
manifest_dir = dataiku.Folder("uat_manifest").get_path()
output_dir = dataiku.Folder("reports").get_path()

cmd = [
    sys.executable,
    script,
    "--reports-decile-dir",
    reports_decile_dir,
    "--manifest-dir",
    manifest_dir,
    "--output-dir",
    output_dir,
]

subprocess.run(cmd, check=True, env={**os.environ, "PYTHONPATH": FRAMEWORK_ROOT}, text=True)
