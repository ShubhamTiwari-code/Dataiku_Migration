# Application: Singular / PM Automation
# Phase 11b+ — UAT status chain step 1: Process returned pm_report decisions
# Dataiku Python recipe — thin wrapper over scripts/uat_09_process_pm_report_decisions.py
#
# Sequence: run BEFORE recipe_uat_06_pool.py (its output feeds uat_06's pooling step).
#
# Required Managed Folders:
#   uat_non_uat_decisions : input pm_report chunks returned by stewards
#                           (mirrors uat/non_uat_decisions/)
#   uat_results           : input, blind_uat anti-join source (mirrors uat/results/)
#   uat_results_non_uat   : output, processed non-UAT decisions (mirrors uat/results_non_uat/)
#   models                : input (read-only), routing JSON + PKLs for model-drift check
#
# Governance: RULE-026 (source eligibility) enforced inside uat_09 (process_market()).
# KNOWN-DEVIATION-003: Pair Registry anti-join reads CSV directly (Phase 12 resolution pending).

import os
import subprocess
import sys
from pathlib import Path

import dataiku

FRAMEWORK_ROOT = None
for _p in sys.path:
    if _p and (Path(_p) / "scripts" / "uat_09_process_pm_report_decisions.py").exists():
        FRAMEWORK_ROOT = _p
        break
if not FRAMEWORK_ROOT:
    raise EnvironmentError(
        "Framework not found in sys.path. "
        "Ensure the project library is configured from the PM_GLOBAL_SOLUTION Git repo."
    )
script = str(Path(FRAMEWORK_ROOT) / "scripts" / "uat_09_process_pm_report_decisions.py")

non_uat_decisions_dir = dataiku.Folder("uat_non_uat_decisions").get_path()
results_dir = dataiku.Folder("uat_results").get_path()
results_non_uat_dir = dataiku.Folder("uat_results_non_uat").get_path()
models_dir = dataiku.Folder("models").get_path()

cmd = [
    sys.executable,
    script,
    "--input-dir",
    non_uat_decisions_dir,
    "--results-dir",
    results_dir,
    "--results-non-uat-dir",
    results_non_uat_dir,
    "--models-dir",
    models_dir,
]

subprocess.run(cmd, check=True, env={**os.environ, "PYTHONPATH": FRAMEWORK_ROOT}, text=True)
