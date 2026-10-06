# Application: Singular / PM Automation
# Phase 11c — Priority 2: PM Reports WITH Predict (decile-aware reveal)
# Dataiku Python recipe — thin wrapper over scripts/uat_08_generate_pm_reports.py
#
# Required DSS project variables:
#   PM_COUNTRIES        : comma-separated ISO codes, or "all" (default: "all")
#   PM_EXCLUDE_COUNTRIES: comma-separated ISO codes to skip (default: "" — see note below)
#
# Required Managed Folders:
#   snowflake_extracts  : input CSVs from Snowflake (mirrors uat/snowflake_extracts/)
#   pm_reports          : output Excel reports (mirrors uat/pm_reports/)
#   models              : input (read-only), routing JSON + PKLs for the predict gate
#   uat_reports_decile  : input (read-only), decile-aware reveal source (BACKLOG-007 fix;
#                          mirrors uat/reports_decile/ — without this override the recipe
#                          previously fell back to a path that does not exist inside the
#                          DSS Project Library checkout, degrading every market to blind)
#
# Predict is always requested (--predict). uat_08's own internal gating (routing JSON +
# model-SHA256-drift check vs the approval-time manifest — "Decile-Aware Predict Reveal",
# ARCHITECTURE.md) decides, per row, whether predict columns are actually revealed; markets
# without an approved decile bucket are unaffected (silently stay fully blind). This recipe
# does not need its own reveal/no-reveal toggle.
#
# Governance: RULE-006 satisfied inside uat_08 via Report_Info sheet.
# KNOWN-DEVIATION-001 (resolved 2026-09-15): Pair Registry anti-join now queries
# PairRegistry.get_resolved_pairs() first, direct CSV read kept as a union for pre-migration pairs.

import os
import subprocess
import sys
from pathlib import Path

import dataiku

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

extracts_dir = dataiku.Folder("snowflake_extracts").get_path()
output_dir = dataiku.Folder("pm_reports").get_path()
models_dir = dataiku.Folder("models").get_path()
reports_decile_dir = dataiku.Folder("uat_reports_decile").get_path()

variables = dataiku.get_custom_variables()
countries = variables.get("PM_COUNTRIES", "all")
exclude_countries = variables.get("PM_EXCLUDE_COUNTRIES", "")

cmd = [
    sys.executable,
    script,
    "--mode",
    "non_uat",
    "--predict",
    "--extracts-dir",
    extracts_dir,
    "--output-dir",
    output_dir,
    "--models-dir",
    models_dir,
    "--reports-decile-dir",
    reports_decile_dir,
    "--countries",
    countries,
    "--exclude-countries",
    exclude_countries,
    "--exclude-latam",
]

subprocess.run(cmd, check=True, env={**os.environ, "PYTHONPATH": FRAMEWORK_ROOT}, text=True)
