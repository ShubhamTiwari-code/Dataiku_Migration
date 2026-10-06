# Application: Singular / PM Automation
# Phase 11 — Priority 2a: UAT Score and Stratify
# Dataiku Python recipe — thin wrapper over scripts/uat_01_score_and_stratify.py
#
# Required DSS project variables:
#   PM_FRAMEWORK_ROOT : absolute path to the PM_GLOBAL_SOLUTION repo on the DSS node
#   UAT_COUNTRIES     : space-separated ISO codes (default: "AR AU BR FR")
#   FORCE_RESCORE     : "true" to bypass staging cache (default: "false")
#
# Required Managed Folders:
#   snowflake_extracts : input CSVs from Snowflake
#   uat_staging        : output scored parquets (mirrors uat/staging/)
#   uat_manifest       : RULE-001 run manifests (mirrors uat/manifest/)
#   models             : frozen PKLs, routing JSON, models_manifest.json
#
# Governance: RULE-001 manifest written to uat_manifest Managed Folder.
# Pilot markets: AR, AU, BR, FR (validated locally 2026-07-17).
# Excluded: KR (AUTO_MERGE approval suspended, SYSTEM_STATE 2026-08-18).

import os
import subprocess
import sys
from pathlib import Path

import dataiku

# ---------------------------------------------------------------------------
# Locate framework root from DSS project library (added to sys.path by DSS)
# ---------------------------------------------------------------------------
FRAMEWORK_ROOT = None
for _p in sys.path:
    if _p and (Path(_p) / "scripts" / "uat_01_score_and_stratify.py").exists():
        FRAMEWORK_ROOT = _p
        break
if not FRAMEWORK_ROOT:
    raise EnvironmentError(
        "Framework not found in sys.path. "
        "Ensure the project library is configured from the PM_GLOBAL_SOLUTION Git repo."
    )
script = str(Path(FRAMEWORK_ROOT) / "scripts" / "uat_01_score_and_stratify.py")

# ---------------------------------------------------------------------------
# Managed folder paths
# ---------------------------------------------------------------------------
extracts_dir = dataiku.Folder("snowflake_extracts").get_path()
staging_dir = dataiku.Folder("uat_staging").get_path()
manifest_dir = dataiku.Folder("uat_manifest").get_path()
models_dir = dataiku.Folder("models").get_path()

# ---------------------------------------------------------------------------
# Runtime parameters
# ---------------------------------------------------------------------------
variables = dataiku.get_custom_variables()
countries = variables.get("UAT_COUNTRIES", "AR AU BR FR").split()
force_rescore = variables.get("FORCE_RESCORE", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Build command
# ---------------------------------------------------------------------------
cmd = [
    sys.executable,
    script,
    "--extracts-dir",
    extracts_dir,
    "--staging-dir",
    staging_dir,
    "--manifest-dir",
    manifest_dir,
    "--models-dir",
    models_dir,
    "--countries",
    *countries,
]
if force_rescore:
    cmd.append("--force-rescore")

env = {**os.environ, "PYTHONPATH": FRAMEWORK_ROOT}
subprocess.run(cmd, check=True, env=env, text=True)
