# Application: Singular / PM Automation
# Operational PM Reports Slice — Process #1: Refresh PM Candidates
# Dataiku Python recipe — thin wrapper over scripts/dataiku_refresh_pm_candidates.py
#
# Required DSS project variables:
#   PM_COUNTRIES         : comma-separated ISO codes, or "all" (default: "all")
#   PM_EXCLUDE_COUNTRIES : comma-separated ISO codes to skip (default: "")
#   PM_CANDIDATES_INPUT  : Managed Folder name to read Snowflake extracts from
#                          (default: "snowflake_extracts")
#
# Required Managed Folders:
#   snowflake_extracts    : input CSVs from Snowflake (mirrors uat/snowflake_extracts/)
#   pm_candidates_current : output PM_CANDIDATES_CURRENT snapshot + RUN_MANIFEST.json
#
# Only csv_manual_upload source mode is supported today — see
# dataiku_migration/design/recipe_refresh_pm_candidates.design.md for the
# native-Snowflake-connector design (requires administrator-provisioned connection).
#
# Governance: no predict, no Excel, no steward-decision processing, no model
# changes, no UAT-approval computation (restrictions D1/L).

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
    if _p and (Path(_p) / "scripts" / "dataiku_refresh_pm_candidates.py").exists():
        FRAMEWORK_ROOT = _p
        break
if not FRAMEWORK_ROOT:
    raise EnvironmentError(
        "Framework not found in sys.path. "
        "Ensure the project library is configured from the PM_GLOBAL_SOLUTION Git repo."
    )
script = str(Path(FRAMEWORK_ROOT) / "scripts" / "dataiku_refresh_pm_candidates.py")

# ---------------------------------------------------------------------------
# Managed folder paths
# ---------------------------------------------------------------------------
variables = dataiku.get_custom_variables()
extracts_folder_name = variables.get("PM_CANDIDATES_INPUT", "snowflake_extracts")
extracts_dir = dataiku.Folder(extracts_folder_name).get_path()
output_dir = dataiku.Folder("pm_candidates_current").get_path()

# ---------------------------------------------------------------------------
# Runtime parameters from DSS project variables
# ---------------------------------------------------------------------------
countries = variables.get("PM_COUNTRIES", "all")
exclude_countries = variables.get("PM_EXCLUDE_COUNTRIES", "")

# ---------------------------------------------------------------------------
# Build and execute subprocess command
# ---------------------------------------------------------------------------
cmd = [
    sys.executable,
    script,
    "--source-type",
    "csv_manual_upload",
    "--extracts-dir",
    extracts_dir,
    "--output-dir",
    output_dir,
    "--countries",
    countries,
    "--exclude-countries",
    exclude_countries,
]

subprocess.run(cmd, check=True, env={**os.environ, "PYTHONPATH": FRAMEWORK_ROOT}, text=True)
