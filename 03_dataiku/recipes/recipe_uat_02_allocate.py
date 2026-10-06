# Application: Singular / PM Automation
# Phase 11 — Priority 2b: UAT Sample Allocation (internal + blind outputs)
# Dataiku Python recipe — thin wrapper over scripts/uat_02_sample_allocation.py
#
# Required DSS project variables:
#   PM_FRAMEWORK_ROOT : absolute path to the PM_GLOBAL_SOLUTION repo on the DSS node
#   UAT_COUNTRIES     : space-separated ISO codes (default: "AR AU BR FR")
#
# Required Managed Folders (all must exist before running):
#   uat_staging  : staged scored parquets from recipe_uat_01_score
#   uat_internal : output with score columns for internal review
#   uat_blind    : output stripped of model metadata for stewards
#
# Governance: RULE-006 traceability columns added by uat_02 internally.
# Run recipe_uat_01_score before this recipe.

import os
import subprocess
import sys
from pathlib import Path

import dataiku

# ---------------------------------------------------------------------------
# Resolve framework root
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Locate framework root from DSS project library (added to sys.path by DSS)
# ---------------------------------------------------------------------------
FRAMEWORK_ROOT = None
for _p in sys.path:
    if _p and (Path(_p) / "scripts" / "uat_02_sample_allocation.py").exists():
        FRAMEWORK_ROOT = _p
        break
if not FRAMEWORK_ROOT:
    raise EnvironmentError(
        "Framework not found in sys.path. "
        "Ensure the project library is configured from the PM_GLOBAL_SOLUTION Git repo."
    )
script = str(Path(FRAMEWORK_ROOT) / "scripts" / "uat_02_sample_allocation.py")

# ---------------------------------------------------------------------------
# Managed folder paths (all flags already exist in uat_02 argparse)
# ---------------------------------------------------------------------------
staging_dir = dataiku.Folder("uat_staging").get_path()
internal_dir = dataiku.Folder("uat_internal").get_path()
blind_dir = dataiku.Folder("uat_blind").get_path()

# ---------------------------------------------------------------------------
# Runtime parameters
# ---------------------------------------------------------------------------
variables = dataiku.get_custom_variables()
countries = variables.get("UAT_COUNTRIES", "AR AU BR FR").split()

# ---------------------------------------------------------------------------
# Build command
# ---------------------------------------------------------------------------
cmd = [
    sys.executable,
    script,
    "--staging-dir",
    staging_dir,
    "--internal-dir",
    internal_dir,
    "--blind-dir",
    blind_dir,
    "--countries",
    *countries,
]

env = {**os.environ, "PYTHONPATH": FRAMEWORK_ROOT}
subprocess.run(cmd, check=True, env=env, text=True)
