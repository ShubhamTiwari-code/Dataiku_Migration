# Application: Singular / PM Automation
# Phase 11c — Priority 1: Blind PM Reports (no predict)
# Dataiku Python recipe — thin wrapper over scripts/uat_08_generate_pm_reports.py
#
# Required DSS project variables:
#   PM_COUNTRIES        : comma-separated ISO codes, or "all" (default: "all")
#   PM_EXCLUDE_COUNTRIES: comma-separated ISO codes to skip (default: "KR")
#
# Required Managed Folders:
#   snowflake_extracts  : input CSVs from Snowflake (mirrors uat/snowflake_extracts/)
#   pm_reports          : output Excel reports (mirrors uat/pm_reports/)
#
# Governance: RULE-006 satisfied inside uat_08 via Report_Info sheet.
# KNOWN-DEVIATION-001: Pair Registry anti-join reads CSV directly (Phase 12 resolution pending).

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
    if _p and (Path(_p) / "scripts" / "uat_08_generate_pm_reports.py").exists():
        FRAMEWORK_ROOT = _p
        break
if not FRAMEWORK_ROOT:
    raise EnvironmentError(
        "Framework not found in sys.path. "
        "Ensure the project library is configured from the PM_GLOBAL_SOLUTION Git repo."
    )
script = str(Path(FRAMEWORK_ROOT) / "scripts" / "uat_08_generate_pm_reports.py")

# ---------------------------------------------------------------------------
# Managed folder paths
# ---------------------------------------------------------------------------
extracts_dir = dataiku.Folder("snowflake_extracts").get_path()
output_dir = dataiku.Folder("pm_reports").get_path()

# ---------------------------------------------------------------------------
# Runtime parameters from DSS project variables
# ---------------------------------------------------------------------------
variables = dataiku.get_custom_variables()
countries = variables.get("PM_COUNTRIES", "all")
exclude_countries = variables.get("PM_EXCLUDE_COUNTRIES", "KR")

# ---------------------------------------------------------------------------
# Build and execute subprocess command
# ---------------------------------------------------------------------------
cmd = [
    sys.executable,
    script,
    "--mode",
    "non_uat",
    "--extracts-dir",
    extracts_dir,
    "--output-dir",
    output_dir,
    "--countries",
    countries,
    "--exclude-countries",
    exclude_countries,
    "--exclude-latam",
]

subprocess.run(cmd, check=True, env={**os.environ, "PYTHONPATH": FRAMEWORK_ROOT}, text=True)
