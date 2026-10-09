# Application: Singular
# Project: PM Automation
# Author: Salvador Soto
"""
scripts/uat_08_generate_pm_reports.py
=====================================
Phase 11c — Operational PM Reports Generator

Generates chunked Excel reports of unresolved potential-match pairs for Data
Stewards. Pulls the latest Snowflake extract per market, filters out already-
resolved pairs (anti-join against uat/results/ or uat/results_non_uat/), and
writes <=chunk-size-record xlsx files with a DSR_DECISION dropdown and a
Report_Info traceability sheet (RULE-006).

The predict step is optional and gated by two checks:
  Gate 1 (FAILURE-011 / RULE-017) — market registered in paso_6_model_strategy_decision.json
  Gate 2 (FAILURE-006 / RULE-001) — input has >= MIN_COLUMNS_FOR_PREDICT raw columns

Source type: operational_pm_report (NOT eligible for UAT CI — ARCHITECTURE v2.6.0).

Pair Registry deviation: KNOWN-DEVIATION-001 RESOLVED 2026-09-15 — anti-join now queries
PairRegistry.get_resolved_pairs() first; uat/results*/*.csv direct read is kept as a
fallback/safety net for pairs resolved before this change was deployed.

Governance
----------
  ARCHITECTURE.md v2.6.0  RULE-004 (canonical path registered before implementation)
  RULE-006  Report_Info sheet: run_id, dataset_version, model_version, generation_date
  RULE-011  Predictor public interface only (when --predict is active)

EXTRACT_SELECTION_POLICY (deterministic, auditable per RULE-002):
  1. Scan uat/snowflake_extracts/{CC}_*.csv  +  uat/non_uat/{CC}_*.xlsx
  2. Sort by os.path.getmtime() DESCENDING (primary)
  3. Tie-break: larger file in bytes (secondary)
  4. Select candidates[0]; if empty advance to next
  5. Log: filename, mtime ISO-8601, n_pairs loaded

Usage
-----
  # Blind reports for all non-LATAM markets (primary operational use case)
  python scripts/uat_08_generate_pm_reports.py

  # Specific markets, curated column set
  python scripts/uat_08_generate_pm_reports.py --countries MT,LS,BE --columns curated

  # Add model predictions for markets already in routing JSON
  python scripts/uat_08_generate_pm_reports.py --mode uat --predict-countries DE,IT

  # Dry run — print plan without writing files
  python scripts/uat_08_generate_pm_reports.py --dry-run

  # Smaller chunks for very large markets
  python scripts/uat_08_generate_pm_reports.py --chunk-size 250 --mode non_uat
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("uat_08_pm_reports")

# ---------------------------------------------------------------------------
# Canonical paths (ARCHITECTURE.md v2.6.0)
# ---------------------------------------------------------------------------
UAT_DIR = ROOT / "uat"
SNOWFLAKE_DIR = UAT_DIR / "snowflake_extracts"
INTERNAL_DIR = UAT_DIR / "internal"
NON_UAT_DIR = UAT_DIR / "non_uat"
RESULTS_DIR = UAT_DIR / "results"
RESULTS_NON_UAT_DIR = UAT_DIR / "results_non_uat"
DEFAULT_OUTPUT_DIR = UAT_DIR / "pm_reports"
PASO_6_PATH = ROOT / "models" / "paso_6_model_strategy_decision.json"

# Decile-aware predict reveal (ARCHITECTURE.md v2.7.3) — source of automation approval + model integrity  # noqa: E501
REPORTS_DECILE_DIR = UAT_DIR / "reports_decile"
MANIFEST_DIR = UAT_DIR / "manifest"
MODELS_DIR = ROOT / "models"

# ---------------------------------------------------------------------------
# LATAM exclusion — excluded when --exclude-latam (default: True)
# ---------------------------------------------------------------------------
LATAM_SLUGS: FrozenSet[str] = frozenset(
    {
        "argentina",
        "brazil",
        "chile",
        "colombia",
        "costa_rica",
        "dominican_republic",
        "el_salvador",
        "guatemala",
        "honduras",
        "mexico",
        "nicaragua",
        "panama",
    }
)

# ---------------------------------------------------------------------------
# ISO <-> slug mapping — UAT markets (from uat_01) + non-UAT markets (Phase 11c)
# ---------------------------------------------------------------------------
ISO_TO_SLUG: Dict[str, str] = {
    # UAT markets
    "AR": "argentina",
    "AU": "australia",
    "BR": "brazil",
    "CA": "canada",
    "CH": "switzerland",
    "CL": "chile",
    "CO": "colombia",
    "CR": "costa_rica",
    "DE": "germany",
    "DO": "dominican_republic",
    "ES": "spain",
    "FI": "finland",
    "FR": "france",
    "GR": "greece",
    "GT": "guatemala",
    "HK": "hong_kong",
    "HN": "honduras",
    "ID": "indonesia",
    "IN": "india",
    "IT": "italy",
    "KR": "south_korea",
    "MX": "mexico",
    "MY": "malaysia",
    "NI": "nicaragua",
    "NL": "netherlands",
    "PA": "panama",
    "PH": "philippines",
    "PK": "pakistan",
    "PL": "poland",
    "RU": "russia",
    "SA": "saudi_arabia",
    "SG": "singapore",
    "SV": "el_salvador",
    "TH": "thailand",
    "TR": "turkey",
    "TW": "taiwan",
    "US": "united_states",
    "VN": "vietnam",
    "ZA": "south_africa",
    # Non-UAT markets (Phase 11c — NOT in routing JSON; --predict blocked until registered)
    "AT": "austria",
    "BE": "belgium",
    "BF": "burkina_faso",
    "CD": "congo_dr",
    "CM": "cameroon",
    "CZ": "czech_republic",
    "DK": "denmark",
    "EE": "estonia",
    "EG": "egypt",
    "HR": "croatia",
    "HU": "hungary",
    "IE": "ireland",
    "JP": "japan",
    "LS": "lesotho",
    "LT": "lithuania",
    "LU": "luxembourg",
    "LV": "latvia",
    "MK": "north_macedonia",
    "MO": "macao",
    "MT": "malta",
    "NO": "norway",
    "NZ": "new_zealand",
    "PT": "portugal",
    "RO": "romania",
    "RS": "serbia",
    "RW": "rwanda",
    "SE": "sweden",
    "SI": "slovenia",
    "SK": "slovakia",
    "SN": "senegal",
    "TZ": "tanzania",
    "UG": "uganda",
    "ZM": "zambia",
    # New markets (2026-09-02) — PE registered GLOBAL in routing JSON; UK slug verified
    # via data/processed/united_kingdom/ (not yet in routing JSON, blind-only until registered)
    "PE": "peru",
    "UK": "united_kingdom",
    # New markets (2026-09-23) — no model/paso_6 entry yet, blind-only until registered;
    # also added to uat_09's ELIGIBLE_ISO in the same change (FAILURE-018 recurrence prevention)
    "EC": "ecuador",
    "UY": "uruguay",
}
SLUG_TO_ISO: Dict[str, str] = {v: k for k, v in ISO_TO_SLUG.items()}

# ---------------------------------------------------------------------------
# Column selection constants
# ---------------------------------------------------------------------------
PRIORITY_COLS_BLIND: List[str] = [
    "pair_id",
    "MERGE / NO MERGE / SUSPECT",
    "RULE",
    "PROFILE1_NAME",
    "PROFILE2_NAME",
    "MATCHRESULT_NAME",
    "PROFILE1_FIRSTNAME",
    "PROFILE1_LASTNAME",
    "PROFILE2_FIRSTNAME",
    "PROFILE2_LASTNAME",
    "PROFILE1_GENDER",
    "PROFILE2_GENDER",
    "MATCHRESULT_GENDER",
    "PROFILE1_SPECIALTY",
    "PROFILE2_SPECIALTY",
    "MATCHRESULT_SPECIALTY",
    "PROFILE1_CITY",
    "PROFILE2_CITY",
    "PROFILE1_ZIP5",
    "PROFILE2_ZIP5",
    "PROFILE1_EMAIL",
    "PROFILE2_EMAIL",
    "PROFILE1_PFIZERGLOBALCUSTOMERID",
    "PROFILE2_PFIZERGLOBALCUSTOMERID",
    "PROFILE1_ONEKEY_ID",
    "PROFILE2_ONEKEY_ID",
]

# Native column names from uat/internal/ (no renaming — F-11 fix)
PREDICT_COLS_UAT: List[str] = [
    "probability_merge",
    "predicted_class",
    "score_bucket_interval",
    "automation_candidate_flag",
]

# Native column names from Predictor output (no renaming — F-11 fix)
PREDICT_COLS_NON_UAT: List[str] = [
    "PROB_MERGE",
    "PREDICTION",
    "CONFIDENCE_LEVEL",
]

# Always-visible columns added by the decile-aware reveal mechanism (ARCHITECTURE.md v2.7.3)
REVEAL_COLS: List[str] = ["SCORE_BUCKET", "AUTOMATION_STATUS", "DECISION_SOURCE"]

# Model metadata columns stripped from internal CSV for blind output
_BLIND_STRIP: FrozenSet[str] = frozenset(
    {
        "probability_merge",
        "predicted_class",
        "score_bucket_decile",
        "score_bucket_interval",
        "stratum_type",
        "automation_candidate_flag",
        "confidence_score",
        "model_file",
        "data_date",
        # uat_run_id and source_file are retained for traceability
    }
)

# FAILURE-006 proxy: minimum raw columns to attempt --predict
MIN_COLUMNS_FOR_PREDICT = 50

# ---------------------------------------------------------------------------
# Excel formatting constants (colours from PMReportConfig)
# ---------------------------------------------------------------------------
_CLR_HEADER = "34495E"  # dark slate — header fill
_CLR_ALT_ROW = "EBF5FB"  # light blue — alternating rows
_CLR_INFO_KEY = "2C3E50"  # near-black — Report_Info key cells


# ---------------------------------------------------------------------------
# Stage 1: INGEST
# ---------------------------------------------------------------------------


def _find_extract(cc: str, mode: str) -> Tuple[Optional[Path], Optional[pd.DataFrame]]:
    """Return (path, df) for the market's most recent extract (EXTRACT_SELECTION_POLICY)."""
    slug = ISO_TO_SLUG.get(cc.upper(), cc.lower())

    if mode == "uat":
        path = INTERNAL_DIR / f"{slug}_uat_internal.csv"
        if not path.exists():
            logger.warning("[%s] UAT internal file not found: %s", cc, path.name)
            return None, None
        df = pd.read_csv(path, low_memory=False)
        mtime = _fmt_mtime(path)
        logger.info("[%s] UAT source: %s | mtime: %s | n_pairs: %d", cc, path.name, mtime, len(df))
        return path, df

    # non-UAT: collect and rank candidates by EXTRACT_SELECTION_POLICY
    candidates = sorted(SNOWFLAKE_DIR.glob(f"{cc}_PM_MDM_Potential_queries_*.csv")) + sorted(
        NON_UAT_DIR.glob(f"{cc}_PM_MDM_Potential_queries_*.xlsx")
    )
    if not candidates:
        logger.warning("[%s] No extract found in snowflake_extracts/ or non_uat/", cc)
        return None, None

    candidates.sort(key=lambda p: (p.stat().st_mtime, p.stat().st_size), reverse=True)

    for candidate in candidates:
        mtime = _fmt_mtime(candidate)
        df = (
            pd.read_csv(candidate, low_memory=False)
            if candidate.suffix == ".csv"
            else pd.read_excel(candidate)
        )
        if df.empty:
            logger.warning("[%s] Skipping empty: %s", cc, candidate.name)
            continue
        logger.info(
            "[%s] Selected: %s | mtime: %s | n_pairs: %d", cc, candidate.name, mtime, len(df)
        )
        return candidate, df

    logger.error("[%s] All extract candidates are empty", cc)
    return None, None


def _fmt_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


# ---------------------------------------------------------------------------
# Stage 2: DEDUP
# ---------------------------------------------------------------------------


def _load_resolved(cc: str, mode: str) -> FrozenSet[str]:
    """Load resolved pair_ids for a market.

    KNOWN-DEVIATION-001 RESOLVED: queries PairRegistry.get_resolved_pairs() first
    (populated by uat_00 for blind_uat and uat_09 for blind_non_uat). The direct
    CSV read (uat/results/ or uat/results_non_uat/) is kept as a union, not a
    replacement, because pairs resolved before this change was deployed are not
    retroactively present in the registry.
    """
    slug = ISO_TO_SLUG.get(cc.upper(), cc.lower())
    resolved: set = set()
    try:
        from src.lineage.pair_registry import PairRegistry

        registry = PairRegistry(ROOT / "data" / "lineage")
        resolved |= set(registry.get_resolved_pairs(slug))
        logger.info("[%s] Resolved pairs from PairRegistry: %d", cc, len(resolved))
    except Exception as exc:
        logger.warning("[%s] PairRegistry.get_resolved_pairs lookup skipped: %s", cc, exc)

    path = (
        RESULTS_DIR / f"{slug}_steward_results.csv"
        if mode == "uat"
        else RESULTS_NON_UAT_DIR / f"{slug}_non_uat_results.csv"
    )
    if not path.exists():
        logger.info("[%s] No results file — CSV fallback contributes 0 pairs", cc)
        return frozenset(resolved)
    df = pd.read_csv(path)
    if "pair_id" not in df.columns:
        logger.warning("[%s] Results file missing 'pair_id' column: %s", cc, path.name)
        return frozenset(resolved)
    resolved |= set(df["pair_id"].dropna().astype(str))
    logger.info("[%s] Resolved pairs total (registry + %s): %d", cc, path.name, len(resolved))
    return frozenset(resolved)


def _build_pair_id(df: pd.DataFrame, cc: str) -> pd.DataFrame:
    """Build canonical pair_id = min(uri1, uri2)|max(uri1, uri2) — consistent with uat_01/uat_05."""
    if "pair_id" in df.columns:
        return df
    uri1 = next((c for c in df.columns if "PROFILE1" in c.upper() and "URI" in c.upper()), None)
    uri2 = next((c for c in df.columns if "PROFILE2" in c.upper() and "URI" in c.upper()), None)
    if not uri1 or not uri2:
        raise ValueError(
            f"[{cc}] Cannot build pair_id: PROFILE_URI columns not found. "
            f"Available: {list(df.columns[:10])}"
        )
    p1 = df[uri1].fillna("").astype(str).str.strip()
    p2 = df[uri2].fillna("").astype(str).str.strip()
    df = df.copy()
    df["pair_id"] = [f"{min(a, b)}|{max(a, b)}" for a, b in zip(p1, p2)]
    n_before = len(df)
    df = df.drop_duplicates(subset=["pair_id"], keep="first")
    if len(df) < n_before:
        logger.warning("[%s] Dropped %d duplicate pair_ids", cc, n_before - len(df))
    return df


def _dedup(
    df: pd.DataFrame, resolved_ids: FrozenSet[str], cc: str
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    n_total = len(df)
    n_resolved = int(df["pair_id"].isin(resolved_ids).sum())
    df_pending = df[~df["pair_id"].isin(resolved_ids)].copy()
    stats = {"n_total": n_total, "n_resolved": n_resolved, "n_pending": len(df_pending)}
    logger.info(
        "[%s] Dedup: %d total | %d resolved | %d pending", cc, n_total, n_resolved, len(df_pending)
    )
    return df_pending, stats


# ---------------------------------------------------------------------------
# Stage 3: PREDICT (optional, gated)
# ---------------------------------------------------------------------------


def _check_routing_json(slug: str) -> str:
    """Return routing decision for market; raise RuntimeError if absent (FAILURE-011 gate)."""
    if not PASO_6_PATH.exists():
        raise FileNotFoundError(f"Routing JSON not found: {PASO_6_PATH}")
    with open(PASO_6_PATH, encoding="utf-8") as fh:
        by_country = json.load(fh).get("decision", {}).get("by_country", {})
    if slug not in by_country:
        raise RuntimeError(
            f"[PREDICT-GATE] '{slug}' absent from paso_6_model_strategy_decision.json.\n"
            f"  Action: add entry with decision=GLOBAL before using --predict for this market.\n"
            f"  Registered markets: {sorted(by_country.keys())}"
        )
    decision = by_country[slug]["decision"]
    logger.info("[%s] Routing decision: %s", slug, decision)
    return decision


def _run_predict(df_pending: pd.DataFrame, cc: str, mode: str) -> Tuple[pd.DataFrame, str]:
    """Run predictions. For UAT: reuse internal CSV columns. For non-UAT: invoke Predictor."""
    from src.inference.predictor import Predictor  # deferred import — only when --predict

    slug = ISO_TO_SLUG.get(cc.upper(), cc.lower())

    # Gate 1: routing JSON check (FAILURE-011 / RULE-017)
    _check_routing_json(slug)

    # Gate 2: feature coverage proxy (FAILURE-006 / RULE-001)
    if len(df_pending.columns) < MIN_COLUMNS_FOR_PREDICT:
        raise RuntimeError(
            f"[COVERAGE-GATE] {cc}: {len(df_pending.columns)} raw columns < {MIN_COLUMNS_FOR_PREDICT}.\n"  # noqa: E501
            f"  Likely malformed extract. Aborting --predict (FAILURE-006 prevention)."
        )

    if mode == "uat":
        # UAT internal CSV already has model columns — reuse; no Predictor call needed
        available = [c for c in PREDICT_COLS_UAT if c in df_pending.columns]
        if not available:
            logger.warning("[%s] --predict requested but no UAT model columns found", cc)
        model_ver = (
            str(df_pending["model_file"].iloc[0])
            if "model_file" in df_pending.columns
            else "uat_internal"
        )
        return df_pending, model_ver

    # non-UAT: invoke Predictor via public interface (RULE-011)
    df_input = df_pending.drop(columns=["DSR_DECISION"], errors="ignore")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / f"{cc}_predict_input.xlsx"
        df_input.to_excel(tmp_path, index=False, engine="openpyxl")
        logger.info("[%s] Predictor input: %s (%d rows)", cc, tmp_path.name, len(df_input))
        predictor = Predictor(base_dir=ROOT)
        df_out, result = predictor.predict(tmp_path, country=slug)

    logger.info(
        "[%s] Predictor: %d MERGE | %d NO_MERGE", cc, result.merge_count, result.no_merge_count
    )
    return df_out, Path(result.model_path).name


# ---------------------------------------------------------------------------
# Stage 3b: DECILE-AWARE PREDICT REVEAL (ARCHITECTURE.md v2.7.3)
# ---------------------------------------------------------------------------


def _assign_score_bucket(prob: float) -> str:
    """Bin a probability into a 10-decile bucket — must match uat_09/uat_01 format exactly."""
    b = min(int(math.floor(prob * 10)), 9)
    return f"{b / 10:.1f}\u2013{(b + 1) / 10:.1f}"


def _load_decile_automation(slug: str) -> Dict[str, str]:
    """Read approved automation buckets for a market. Empty dict = nothing approved (fail-safe)."""
    path = REPORTS_DECILE_DIR / f"{slug}_decile_combined_analysis.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    if "score_bucket" not in df.columns or "automation_recommendation" not in df.columns:
        return {}
    result: Dict[str, str] = {}
    for bucket, group in df.groupby("score_bucket"):
        recs = set(group["automation_recommendation"])
        if "AUTO_MERGE" in recs:
            result[bucket] = "AUTO_MERGE"
        elif "AUTO_NO_MERGE" in recs:
            result[bucket] = "AUTO_NO_MERGE"
    return result


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _check_model_drift(slug: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Compare current model file SHA256 vs the one recorded when automation was approved.

    Returns (drift_detected, current_sha256, manifest_sha256). No manifest/model on disk
    is treated as "cannot verify" (drift=False) rather than a hard failure.
    """
    manifest_path = MANIFEST_DIR / f"{slug}_uat_run_manifest.json"
    if not manifest_path.exists():
        return False, None, None
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    manifest_sha = manifest.get("model_file_sha256")
    model_file = manifest.get("model_file")
    if not manifest_sha or not model_file:
        return False, None, None
    model_path = MODELS_DIR / model_file
    if not model_path.exists():
        return True, None, manifest_sha
    current_sha = _sha256_file(model_path)
    return current_sha != manifest_sha, current_sha, manifest_sha


def _maybe_reveal_predict(
    df_pending: pd.DataFrame, cc: str, mode: str
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Score + partially reveal predict columns for markets with decile-approved automation.

    Fail-safe by design: any gate failure (routing, drift, scoring error) degrades to the
    original blind df_pending rather than raising — this path runs unconditionally for every
    market, so it must never block blind report generation.
    """
    slug = ISO_TO_SLUG.get(cc.upper(), cc.lower())
    reveal_info: Dict[str, Any] = {
        "eligible": False,
        "automation_source": "N/A (no decile file)",
        "n_auto_revealed": 0,
        "n_manual": len(df_pending),
        "model_file_sha256_current": None,
        "model_file_sha256_manifest": None,
        "model_drift_detected": False,
    }

    automation = _load_decile_automation(slug)
    if not automation:
        return df_pending, reveal_info

    reveal_info["automation_source"] = f"uat/reports_decile/{slug}_decile_combined_analysis.csv"

    try:
        # Gate 1 (reused): market must be registered in routing JSON (FAILURE-011 / RULE-017)
        _check_routing_json(slug)

        # Gate 2: model-drift guard — never trust a stale automation approval
        drift, current_sha, manifest_sha = _check_model_drift(slug)
        reveal_info["model_file_sha256_current"] = current_sha
        reveal_info["model_file_sha256_manifest"] = manifest_sha
        reveal_info["model_drift_detected"] = drift
        if drift:
            logger.warning(
                "[%s] Model drift detected (current=%s manifest=%s) — degrading to blind",
                cc,
                current_sha,
                manifest_sha,
            )
            return df_pending, reveal_info

        from src.inference.predictor import Predictor  # deferred import

        df_input = df_pending.drop(columns=["DSR_DECISION"], errors="ignore")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / f"{cc}_reveal_input.xlsx"
            df_input.to_excel(tmp_path, index=False, engine="openpyxl")
            # Rules/tree-explainability disabled — reveal only needs PROB_MERGE/PREDICTION at scale
            predictor = Predictor(
                base_dir=ROOT, enable_rules=False, enable_tree_explainability_metrics=False
            )
            df_scored, _ = predictor.predict(tmp_path, country=slug)

        if "PROB_MERGE" not in df_scored.columns:
            raise RuntimeError("PROB_MERGE column missing from Predictor output")

        # Drop stale legacy uat-internal model columns — reveal always shows fresh Predictor schema
        df_scored = df_scored.drop(columns=[c for c in _BLIND_STRIP if c in df_scored.columns])

        df_scored["SCORE_BUCKET"] = (
            df_scored["PROB_MERGE"].clip(0.0, 1.0).apply(_assign_score_bucket)
        )
        df_scored["AUTOMATION_STATUS"] = df_scored["SCORE_BUCKET"].map(automation).fillna("MANUAL")
        df_scored["DECISION_SOURCE"] = ""
        df_scored["DSR_DECISION"] = ""

        auto_merge = df_scored["AUTOMATION_STATUS"] == "AUTO_MERGE"
        auto_no_merge = df_scored["AUTOMATION_STATUS"] == "AUTO_NO_MERGE"
        auto_mask = auto_merge | auto_no_merge

        df_scored.loc[auto_merge, "DSR_DECISION"] = "Y"
        df_scored.loc[auto_no_merge, "DSR_DECISION"] = "N"
        df_scored.loc[auto_mask, "DECISION_SOURCE"] = "AUTOMATED"

        # Mask predict-step columns in non-approved rows — never contaminate steward judgment
        # Cast to object dtype first: CONFIDENCE_LEVEL is Categorical and rejects "" otherwise
        mask_cols = [
            c
            for c in PREDICT_COLS_NON_UAT + ["DECISION_RULE", "APPLIED_THRESHOLD", "MODEL_VERSION"]
            if c in df_scored.columns
        ]
        for col in mask_cols:
            df_scored[col] = df_scored[col].astype(object)
            df_scored.loc[~auto_mask, col] = ""

        reveal_info["eligible"] = True
        reveal_info["n_auto_revealed"] = int(auto_mask.sum())
        reveal_info["n_manual"] = int((~auto_mask).sum())
        return df_scored, reveal_info

    except RuntimeError as exc:
        logger.warning("[%s] Decile-reveal gate blocked (%s) — falling back to blind", cc, exc)
        return df_pending, reveal_info


# ---------------------------------------------------------------------------
# Stage 4: SELECT
# ---------------------------------------------------------------------------


def _select_columns(
    df: pd.DataFrame,
    columns_mode: str,
    with_predict: bool,
    mode: str,
    reveal_eligible: bool = False,
) -> pd.DataFrame:
    """Filter and order columns for steward-facing output."""
    if columns_mode == "full":
        if with_predict or mode != "uat" or reveal_eligible:
            return df
        # Blind UAT: drop model metadata; keep uat_run_id, source_file for traceability
        return df.drop(columns=[c for c in _BLIND_STRIP if c in df.columns])

    # curated mode
    predict_cols = (
        PREDICT_COLS_NON_UAT
        if reveal_eligible
        else (PREDICT_COLS_UAT if mode == "uat" else PREDICT_COLS_NON_UAT)
    )
    reveal_cols = REVEAL_COLS if reveal_eligible else []
    wanted = (
        PRIORITY_COLS_BLIND
        + (predict_cols if (with_predict or reveal_eligible) else [])
        + reveal_cols
    )
    ordered = [c for c in wanted if c in df.columns]
    # ensure pair_id is always present
    if "pair_id" in df.columns and "pair_id" not in ordered:
        ordered = ["pair_id"] + ordered
    return df[ordered] if ordered else df


# ---------------------------------------------------------------------------
# Stage 5: SAVE
# ---------------------------------------------------------------------------


def _clean_cell(val: Any) -> Any:
    """Convert pandas/numpy values to Excel-safe Python scalars."""
    if pd.isna(val) if not isinstance(val, (str, list, dict)) else False:
        return ""
    if isinstance(val, pd.Timestamp):
        return val.isoformat()
    return val


def _write_report_chunks(
    df: pd.DataFrame,
    cc: str,
    output_dir: Path,
    run_id: str,
    extract_path: Optional[Path],
    chunk_size: int,
    with_predict: bool,
    model_version: str,
    mode: str,
    timestamp: str,
    n_resolved: int,
    reveal_info: Optional[Dict[str, Any]] = None,
    file_stem: Optional[str] = None,
    extra_info: Optional[List[Tuple[str, Any]]] = None,
) -> List[Path]:
    """Write chunked Excel files with PM_Records + Report_Info sheets (RULE-006).

    file_stem/extra_info are opt-in (uat_14 Medconnect batches); defaults keep the legacy
    PM_HCP_{CC}_{ts}_set{NN}.xlsx naming and Report_Info rows unchanged.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    n_pending = len(df)
    n_sets = max(1, math.ceil(n_pending / chunk_size)) if n_pending > 0 else 0
    if file_stem and n_sets > 1:
        raise ValueError(
            f"file_stem requires a single chunk; got {n_sets} (chunk_size={chunk_size})"
        )

    if n_pending == 0:
        logger.info("[%s] No pending pairs — skipping file generation", cc)
        return []

    reveal_info = reveal_info or {}
    gen_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    dataset_version = (
        f"{extract_path.name} | mtime: {_fmt_mtime(extract_path)}" if extract_path else "unknown"
    )
    model_ver_str = model_version if with_predict else "blind_report (no model predictions)"

    header_fill = PatternFill("solid", fgColor=_CLR_HEADER)
    header_font = Font(bold=True, color="FFFFFF", size=10)
    alt_fill = PatternFill("solid", fgColor=_CLR_ALT_ROW)
    key_fill = PatternFill("solid", fgColor=_CLR_INFO_KEY)
    key_font = Font(bold=True, color="FFFFFF", size=9)

    files_written: List[Path] = []

    for i, start in enumerate(range(0, n_pending, chunk_size), start=1):
        chunk = df.iloc[start : start + chunk_size].reset_index(drop=True)
        out_path = output_dir / (
            f"{file_stem}.xlsx" if file_stem else f"PM_HCP_{cc}_{timestamp}_set{i:02d}.xlsx"
        )

        wb = Workbook()

        # ── Sheet 1: PM_Records ───────────────────────────────────────────
        ws = wb.active
        ws.title = "PM_Records"

        cols = ["DSR_DECISION"] + [c for c in chunk.columns if c != "DSR_DECISION"]
        n_rows = len(chunk)

        # Header
        for col_idx, col_name in enumerate(cols, start=1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Data rows
        for row_idx in range(n_rows):
            excel_row = row_idx + 2
            is_alt = row_idx % 2 == 0
            row_data = chunk.iloc[row_idx]
            for col_idx, col_name in enumerate(cols, start=1):
                # DSR_DECISION may arrive pre-filled Y/N for decile-approved rows — pass through as-is  # noqa: E501
                val = _clean_cell(row_data.get(col_name, ""))
                cell = ws.cell(row=excel_row, column=col_idx, value=val)
                if is_alt:
                    cell.fill = alt_fill

        # DSR_DECISION dropdown (col A, all data rows)
        dv = DataValidation(
            type="list",
            formula1='"Y,N,S"',
            allow_blank=True,
            sqref=f"A2:A{n_rows + 1}",
            showDropDown=False,
        )
        dv.prompt = "Y = Merge  |  N = No Merge  |  S = Suspect / Insufficient"
        dv.error = "Enter Y, N, or S"
        dv.errorTitle = "Invalid value"
        ws.add_data_validation(dv)

        # Column widths: sample first 50 rows, cap at 62
        for col_idx, col_name in enumerate(cols, start=1):
            max_w = max(len(str(col_name)), 8)
            for row_idx in range(2, min(52, n_rows + 2)):
                v = ws.cell(row=row_idx, column=col_idx).value
                if v:
                    max_w = max(max_w, min(len(str(v)), 60))
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_w + 2, 62)

        ws.freeze_panes = "B2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}1"

        # ── Sheet 2: Report_Info (RULE-006) ───────────────────────────────
        ws_info = wb.create_sheet("Report_Info")
        info_rows = [
            ("run_id", run_id),
            ("dataset_version", dataset_version),
            ("model_version", model_ver_str),
            ("generation_date", gen_date),
            ("market_iso", cc),
            ("set_number", f"{i} of {n_sets}"),
            ("n_records_in_set", len(chunk)),
            ("n_total_pending", n_pending),
            ("n_resolved_filtered", n_resolved),
            ("source_type", "operational_pm_report"),
            ("pipeline_mode", mode),
            ("predict_active", str(with_predict)),
            ("automation_source", reveal_info.get("automation_source", "N/A (no decile file)")),
            ("n_auto_revealed", reveal_info.get("n_auto_revealed", 0)),
            ("n_manual", reveal_info.get("n_manual", n_pending)),
            ("model_file_sha256_current", reveal_info.get("model_file_sha256_current") or "N/A"),
            ("model_file_sha256_manifest", reveal_info.get("model_file_sha256_manifest") or "N/A"),
            ("model_drift_detected", str(reveal_info.get("model_drift_detected", False))),
        ] + list(extra_info or [])
        for r, (key, val) in enumerate(info_rows, start=1):
            k_cell = ws_info.cell(row=r, column=1, value=key)
            k_cell.fill = key_fill
            k_cell.font = key_font
            ws_info.cell(row=r, column=2, value=str(val))
        ws_info.column_dimensions["A"].width = 26
        ws_info.column_dimensions["B"].width = 80

        wb.save(out_path)
        files_written.append(out_path)
        logger.info(
            "[%s] Written set %d/%d: %s (%d records)", cc, i, n_sets, out_path.name, len(chunk)
        )

    return files_written


# ---------------------------------------------------------------------------
# Market discovery
# ---------------------------------------------------------------------------


def _discover_markets(mode: str) -> Dict[str, str]:
    """Return {iso_code: pipeline_mode} for all discoverable markets."""
    markets: Dict[str, str] = {}

    if mode in ("uat", "all"):
        for p in sorted(INTERNAL_DIR.glob("*_uat_internal.csv")):
            slug = p.stem.replace("_uat_internal", "")
            iso = SLUG_TO_ISO.get(slug, slug.upper()[:2])
            markets[iso] = "uat"

    if mode in ("non_uat", "all"):
        seen: set = set()
        for p in list(SNOWFLAKE_DIR.glob("*_PM_MDM_Potential_queries_*.csv")) + list(
            NON_UAT_DIR.glob("*_PM_MDM_Potential_queries_*.xlsx")
        ):
            iso = p.stem.split("_")[0].upper()
            if iso not in seen and iso in ISO_TO_SLUG:
                seen.add(iso)
                if iso not in markets:  # UAT takes precedence for overlapping markets
                    markets[iso] = "non_uat"

    return markets


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_pipeline(args: argparse.Namespace) -> List[Dict]:
    run_id = str(uuid.uuid4())
    timestamp = args.run_timestamp or datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = Path(args.output_dir)

    # Apply path overrides before any directory access (P0.3)
    global SNOWFLAKE_DIR, INTERNAL_DIR, NON_UAT_DIR, RESULTS_DIR, RESULTS_NON_UAT_DIR, PASO_6_PATH, REPORTS_DECILE_DIR  # noqa: E501
    if args.extracts_dir:
        SNOWFLAKE_DIR = Path(args.extracts_dir)
    if args.internal_dir:
        INTERNAL_DIR = Path(args.internal_dir)
    if args.non_uat_dir:
        NON_UAT_DIR = Path(args.non_uat_dir)
    if args.results_dir:
        RESULTS_DIR = Path(args.results_dir)
    if args.results_non_uat_dir:
        RESULTS_NON_UAT_DIR = Path(args.results_non_uat_dir)
    if args.models_dir:
        PASO_6_PATH = Path(args.models_dir) / "paso_6_model_strategy_decision.json"
    if args.reports_decile_dir:
        REPORTS_DECILE_DIR = Path(args.reports_decile_dir)

    logger.info("=" * 60)
    logger.info("UAT-08 PM Reports — run_id: %s", run_id)
    logger.info(
        "Mode: %s | Columns: %s | Chunk: %d | Predict: %s",
        args.mode,
        args.columns,
        args.chunk_size,
        args.predict_countries or ("yes" if args.predict else "no"),
    )
    logger.info("=" * 60)

    # Discover and filter markets
    all_markets = _discover_markets(args.mode)

    if args.countries and args.countries.lower() != "all":
        wanted = {c.strip().upper() for c in args.countries.split(",")}
        all_markets = {cc: m for cc, m in all_markets.items() if cc in wanted}

    if args.exclude_latam:
        all_markets = {
            cc: m
            for cc, m in all_markets.items()
            if ISO_TO_SLUG.get(cc, "").lower() not in LATAM_SLUGS
        }

    if args.exclude_countries:
        excluded_cc = {c.strip().upper() for c in args.exclude_countries.split(",")}
        all_markets = {cc: m for cc, m in all_markets.items() if cc not in excluded_cc}
        logger.info("Excluded by --exclude-countries: %s", sorted(excluded_cc))

    if not all_markets:
        logger.warning("No markets found after filtering. Check --mode / --countries.")
        return []

    # Determine which markets get predictions
    predict_set: FrozenSet[str] = frozenset()
    if args.predict_countries:
        predict_set = frozenset(c.strip().upper() for c in args.predict_countries.split(","))
    elif args.predict:
        predict_set = frozenset(all_markets.keys())

    logger.info("Markets to process (%d): %s", len(all_markets), sorted(all_markets))

    results = []

    for cc, mode in sorted(all_markets.items(), key=lambda x: x[0]):
        with_predict = cc in predict_set
        result: Dict = {
            "cc": cc,
            "mode": mode,
            "predict": with_predict,
            "status": "ok",
            "files": [],
            "error": None,
        }
        try:
            # Stage 1: INGEST
            extract_path, df = _find_extract(cc, mode)
            if df is None:
                result["status"] = "skipped_no_extract"
                results.append(result)
                continue

            # Stage 2: DEDUP
            resolved_ids = _load_resolved(cc, mode)
            df = _build_pair_id(df, cc)
            df_pending, stats = _dedup(df, resolved_ids, cc)
            result.update(stats)

            if args.dry_run:
                n_sets = (
                    max(1, math.ceil(stats["n_pending"] / args.chunk_size))
                    if stats["n_pending"] > 0
                    else 0
                )
                result["n_sets"] = n_sets
                result["status"] = "dry_run"
                results.append(result)
                continue

            if stats["n_pending"] == 0:
                result["status"] = "skipped_all_resolved"
                results.append(result)
                continue

            # Stage 3: PREDICT — decile-reveal always takes precedence over legacy --predict
            # for eligible markets (no double-scoring); falls back to legacy path otherwise.
            model_version = "blind_report"
            df_pending, reveal_info = _maybe_reveal_predict(df_pending, cc, mode)
            if reveal_info["eligible"]:
                with_predict = True
                model_version = reveal_info.get("model_file_sha256_current") or "decile_reveal"
            elif with_predict:
                df_pending, model_version = _run_predict(df_pending, cc, mode)
            result["predict"] = with_predict

            # Stage 4: SELECT
            df_out = _select_columns(
                df_pending,
                args.columns,
                with_predict,
                mode,
                reveal_eligible=reveal_info["eligible"],
            )

            # Stage 5: SAVE
            files = _write_report_chunks(
                df_out,
                cc,
                output_dir,
                run_id,
                extract_path,
                args.chunk_size,
                with_predict,
                model_version,
                mode,
                timestamp,
                stats["n_resolved"],
                reveal_info=reveal_info,
            )
            result["files"] = [f.name for f in files]
            result["n_sets"] = len(files)

        except RuntimeError as exc:
            logger.error("[%s] Pipeline gate blocked: %s", cc, exc)
            result["status"] = "blocked"
            result["error"] = str(exc)
        except Exception as exc:
            logger.error("[%s] Unexpected error: %s", cc, exc, exc_info=True)
            result["status"] = "error"
            result["error"] = str(exc)

        results.append(result)

    _print_summary(results, args.dry_run)
    return results


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def _print_summary(results: List[Dict], dry_run: bool) -> None:
    header = f"{'Market':<8} {'Mode':<8} {'n_total':>8} {'n_res':>7} {'n_pend':>7} {'n_sets':>7} {'Predict':<8} {'Status'}"  # noqa: E501
    sep = "-" * 80
    print(f"\n{'DRY RUN — ' if dry_run else ''}PM Reports Summary\n{sep}\n{header}\n{sep}")
    for r in results:
        n_total = r.get("n_total", "-")
        n_res = r.get("n_resolved", "-")
        n_pend = r.get("n_pending", "-")
        n_sets = r.get("n_sets", "-")
        predict_flag = "yes" if r.get("predict") else "blind"
        status = r.get("status", "?")
        if r.get("error"):
            status = f"{status}: {r['error'][:40]}"
        print(
            f"{r['cc']:<8} {r['mode']:<8} {str(n_total):>8} {str(n_res):>7} {str(n_pend):>7} "
            f"{str(n_sets):>7} {predict_flag:<8} {status}"
        )
    print(sep)
    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"].startswith("skipped"))
    blocked = sum(1 for r in results if r["status"] in ("blocked", "error"))
    print(f"Total: {len(results)} | OK: {ok} | Skipped: {skipped} | Blocked/Error: {blocked}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 11c — Operational PM Reports Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/uat_08_generate_pm_reports.py
  python scripts/uat_08_generate_pm_reports.py --mode non_uat --columns curated
  python scripts/uat_08_generate_pm_reports.py --predict-countries DE,IT --mode uat
  python scripts/uat_08_generate_pm_reports.py --countries MT,LS --dry-run
  python scripts/uat_08_generate_pm_reports.py --chunk-size 250 --no-exclude-latam
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["uat", "non_uat", "all"],
        default="all",
        help="Pipeline mode (default: all)",
    )
    parser.add_argument(
        "--countries", default="all", help="Comma-separated ISO codes, or 'all' (default: all)"
    )
    parser.add_argument(
        "--predict",
        action="store_true",
        default=False,
        help="Enable predictions for all processed markets (gated by routing JSON)",
    )
    parser.add_argument(
        "--predict-countries",
        default=None,
        help="Comma-separated ISO codes to enable predictions for (overrides --predict)",
    )
    parser.add_argument(
        "--columns",
        choices=["full", "curated"],
        default="full",
        help="Column selection mode (default: full)",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=500, help="Max records per Excel file (default: 500)"
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    # Path overrides for Dataiku managed folder compatibility (P0.3)
    parser.add_argument(
        "--extracts-dir", default=None, help="Override uat/snowflake_extracts input directory"
    )
    parser.add_argument("--non-uat-dir", default=None, help="Override uat/non_uat input directory")
    parser.add_argument(
        "--results-non-uat-dir", default=None, help="Override uat/results_non_uat anti-join source"
    )
    parser.add_argument(
        "--internal-dir", default=None, help="Override uat/internal directory (mode=uat input)"
    )
    parser.add_argument(
        "--results-dir", default=None, help="Override uat/results anti-join source (mode=uat)"
    )
    parser.add_argument(
        "--models-dir", default=None, help="Override models directory (routing JSON location)"
    )
    parser.add_argument(
        "--reports-decile-dir",
        default=None,
        help="Override uat/reports_decile directory (BACKLOG-007; decile-aware predict reveal source)",  # noqa: E501
    )
    parser.add_argument(
        "--exclude-countries",
        default=None,
        help="Comma-separated ISO codes to skip (e.g. KR for suspended markets)",
    )
    parser.add_argument(
        "--run-timestamp",
        default=None,
        help="Override timestamp YYYYMMDD_HHMM for batch consistency",
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False, help="Show plan without writing files"
    )
    parser.add_argument(
        "--exclude-latam",
        action="store_true",
        default=True,
        help="Exclude LATAM countries (default: True)",
    )
    parser.add_argument(
        "--no-exclude-latam",
        dest="exclude_latam",
        action="store_false",
        help="Include LATAM countries",
    )
    parser.add_argument(
        "--verbose", action="store_true", default=False, help="Enable DEBUG logging"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    run_pipeline(args)


if __name__ == "__main__":
    main()
