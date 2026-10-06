# Application: Singular / PM Automation
# Phase 11b — UAT status chain step 4b: Automation Evidence Report
# Dataiku Python recipe — thin wrapper over scripts/uat_10_generate_automation_evidence.py
#
# Sequence: run AFTER recipe_uat_06_pool.py. Parallel-safe with recipe_uat_07_report.py,
# recipe_uat_11_manifest.py, recipe_uat_12_attainability.py, recipe_uat_13_status.py (read-only
# on reports_decile, no shared write target).
#
# Required Managed Folders:
#   uat_internal          : input (mirrors uat/internal/)
#   uat_results           : input (mirrors uat/results/)
#   uat_results_non_uat   : input (mirrors uat/results_non_uat/)
#   uat_non_uat_decisions : input (mirrors uat/non_uat_decisions/)
#   uat_reports_decile    : input (mirrors uat/reports_decile/)
#   uat_reports_evidence  : output (mirrors uat/reports_evidence/)
#
# KNOWN-DEVIATION-006: reads uat/reports_decile and uat/non_uat_decisions directly (no
# PairRegistry query) — same accepted pattern as KNOWN-DEVIATION-001/003/004.

import os
import subprocess
import sys
from pathlib import Path

import dataiku

FRAMEWORK_ROOT = None
for _p in sys.path:
    if _p and (Path(_p) / "scripts" / "uat_10_generate_automation_evidence.py").exists():
        FRAMEWORK_ROOT = _p
        break
if not FRAMEWORK_ROOT:
    raise EnvironmentError(
        "Framework not found in sys.path. "
        "Ensure the project library is configured from the PM_GLOBAL_SOLUTION Git repo."
    )
script = str(Path(FRAMEWORK_ROOT) / "scripts" / "uat_10_generate_automation_evidence.py")

internal_dir = dataiku.Folder("uat_internal").get_path()
results_dir = dataiku.Folder("uat_results").get_path()
results_non_uat_dir = dataiku.Folder("uat_results_non_uat").get_path()
non_uat_decisions_dir = dataiku.Folder("uat_non_uat_decisions").get_path()
reports_decile_dir = dataiku.Folder("uat_reports_decile").get_path()
output_dir = dataiku.Folder("uat_reports_evidence").get_path()

cmd = [
    sys.executable,
    script,
    "--internal-dir",
    internal_dir,
    "--results-dir",
    results_dir,
    "--results-non-uat-dir",
    results_non_uat_dir,
    "--non-uat-decisions-dir",
    non_uat_decisions_dir,
    "--reports-decile-dir",
    reports_decile_dir,
    "--output-dir",
    output_dir,
]

subprocess.run(cmd, check=True, env={**os.environ, "PYTHONPATH": FRAMEWORK_ROOT}, text=True)
