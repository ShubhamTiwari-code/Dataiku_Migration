# Application: Singular / PM Automation
# Phase 11b — UAT status chain step 4c: Automation Attainability & Futility Analysis
# Dataiku Python recipe — thin wrapper over scripts/uat_12_attainability_analysis.py
#
# Sequence: run AFTER recipe_uat_06_pool.py. Parallel-safe (RULE-027: read-only on
# reports_decile's automation columns; only writes its own advisory columns/files).
#
# Required Managed Folders:
#   uat_reports_decile : input + output (mirrors uat/reports_decile/; writes
#                        {slug}_attainability_analysis.csv into the same folder)

import os
import subprocess
import sys
from pathlib import Path

import dataiku

FRAMEWORK_ROOT = None
for _p in sys.path:
    if _p and (Path(_p) / "scripts" / "uat_12_attainability_analysis.py").exists():
        FRAMEWORK_ROOT = _p
        break
if not FRAMEWORK_ROOT:
    raise EnvironmentError(
        "Framework not found in sys.path. "
        "Ensure the project library is configured from the PM_GLOBAL_SOLUTION Git repo."
    )
script = str(Path(FRAMEWORK_ROOT) / "scripts" / "uat_12_attainability_analysis.py")

reports_decile_dir = dataiku.Folder("uat_reports_decile").get_path()

cmd = [
    sys.executable,
    script,
    "--reports-decile-dir",
    reports_decile_dir,
]

subprocess.run(cmd, check=True, env={**os.environ, "PYTHONPATH": FRAMEWORK_ROOT}, text=True)
