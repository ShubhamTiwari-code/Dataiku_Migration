# Application: Singular / PM Automation
# Process #1: Refresh PM Candidates
"""
scripts/dataiku_refresh_pm_candidates.py
==========================================
Produces a controlled snapshot of current Potential Match candidates
(PM_CANDIDATES_CURRENT contract, dataiku_migration/contracts/PM_CANDIDATES_CURRENT.schema.yaml)
by reusing (not duplicating) uat_08_generate_pm_reports.py's extract discovery
(_find_extract, EXTRACT_SELECTION_POLICY) and canonical pair_id construction
(_build_pair_id).

Does NOT: run predict, generate Excel, process steward decisions, modify models,
compute UAT approvals, or auto-update approved buckets (restrictions D1/L in
context_instructions/requirements/9_1_dataiku_migration_prompt.md).

Only --source-type csv_manual_upload is implemented today (reads uat/snowflake_extracts/
via uat_08's own extract-selection policy). --source-type snowflake_native is a
documented stub — it requires a Dataiku-Snowflake connection provisioned by an
administrator, not assumed to exist (see
dataiku_migration/design/recipe_refresh_pm_candidates.design.md).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

logger = logging.getLogger("dataiku_refresh_pm_candidates")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

ROOT = Path(__file__).resolve().parents[1]


def _load_uat_08(root: Path):
    """Load uat_08_generate_pm_reports.py as a module to reuse its extract discovery
    (_find_extract) and canonical pair_id builder (_build_pair_id) without duplicating them."""
    path = root / "scripts" / "uat_08_generate_pm_reports.py"
    spec = importlib.util.spec_from_file_location("_uat_08_for_refresh", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _resolve_markets(uat08, countries: str, exclude_countries: str) -> List[str]:
    all_isos = sorted(uat08.ISO_TO_SLUG.keys())
    if countries.strip().lower() == "all":
        selected = all_isos
    else:
        selected = [c.strip().upper() for c in countries.split(",") if c.strip()]
    excluded = {c.strip().upper() for c in (exclude_countries or "").split(",") if c.strip()}
    return [c for c in selected if c not in excluded]


def build_pm_candidates_current(
    uat08,
    markets: List[str],
    run_id: str,
    source_type: str,
) -> Tuple[pd.DataFrame, Dict]:
    rows = []
    row_count_raw = 0
    duplicates_removed = 0
    markets_included: List[str] = []

    for cc in markets:
        slug = uat08.ISO_TO_SLUG.get(cc.upper(), cc.lower())
        try:
            path, df = uat08._find_extract(cc, mode="non_uat")
        except Exception as exc:
            logger.warning("[%s] extract discovery failed: %s", cc, exc)
            continue
        if df is None or path is None:
            continue
        row_count_raw += len(df)

        try:
            df = uat08._build_pair_id(df, cc)
        except ValueError as exc:
            # D1 requirement: reject rows missing the columns needed for pair_id
            logger.warning("[%s] rejected (D1 validation): %s", cc, exc)
            continue

        n_before = len(df)
        df = df.drop_duplicates(subset=["pair_id"], keep="first")
        duplicates_removed += n_before - len(df)

        uri1_col = next(
            (c for c in df.columns if "PROFILE1" in c.upper() and "URI" in c.upper()), None
        )
        uri2_col = next(
            (c for c in df.columns if "PROFILE2" in c.upper() and "URI" in c.upper()), None
        )
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()

        rows.append(
            pd.DataFrame(
                {
                    "market_iso": cc.upper(),
                    "market_slug": slug,
                    "pair_id": df["pair_id"],
                    "entity_uri_left": df[uri1_col] if uri1_col else "",
                    "entity_uri_right": df[uri2_col] if uri2_col else "",
                    "source_extract_file": path.name,
                    "source_extract_mtime": mtime,
                    "source_type": source_type,
                    "row_status": "valid",
                    "snapshot_run_id": run_id,
                    "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        )
        markets_included.append(cc.upper())

    candidates = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if not candidates.empty:
        n_before = len(candidates)
        candidates = candidates.drop_duplicates(subset=["market_iso", "pair_id"], keep="first")
        duplicates_removed += n_before - len(candidates)

    manifest_stats = {
        "row_count_raw": row_count_raw,
        "row_count_valid": len(candidates),
        "duplicates_removed": duplicates_removed,
        "markets": markets_included,
    }
    return candidates, manifest_stats


def _atomic_write_parquet(df: pd.DataFrame, final_path: Path) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")
    df.to_parquet(tmp_path, index=False)
    tmp_path.replace(final_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-type",
        choices=["csv_manual_upload", "snowflake_native"],
        default="csv_manual_upload",
    )
    parser.add_argument(
        "--extracts-dir", default=None, help="Override uat/snowflake_extracts input directory"
    )
    parser.add_argument(
        "--snowflake-dataset",
        default=None,
        help="[snowflake_native, NOT YET IMPLEMENTED] Dataiku dataset name",
    )
    parser.add_argument("--countries", default="all", help="Comma-separated ISO codes, or 'all'")
    parser.add_argument("--exclude-countries", default="", help="Comma-separated ISO codes to skip")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "uat" / "pm_candidates_current"),
        help="Output directory (mirrors the pm_candidates_current Managed Folder)",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.source_type == "snowflake_native":
        raise NotImplementedError(
            "--source-type snowflake_native requires a Dataiku-Snowflake connection "
            "provisioned by an administrator (not assumed to exist). Use "
            "--source-type csv_manual_upload (default) today. See "
            "dataiku_migration/design/recipe_refresh_pm_candidates.design.md."
        )

    run_id = args.run_id or f"PM-CANDIDATES-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    uat08 = _load_uat_08(ROOT)
    if args.extracts_dir:
        uat08.SNOWFLAKE_DIR = Path(args.extracts_dir)

    markets = _resolve_markets(uat08, args.countries, args.exclude_countries)
    candidates, stats = build_pm_candidates_current(uat08, markets, run_id, args.source_type)

    schema_hash = (
        hashlib.sha256(",".join(sorted(candidates.columns)).encode()).hexdigest()
        if not candidates.empty
        else None
    )
    manifest = {
        "run_id": run_id,
        "process_name": "refresh_pm_candidates",
        "source_type": args.source_type,
        "source_identifier": args.extracts_dir or str(uat08.SNOWFLAKE_DIR),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": bool(args.dry_run),
        "row_count_raw": stats["row_count_raw"],
        "row_count_valid": stats["row_count_valid"],
        "duplicates_removed": stats["duplicates_removed"],
        "markets": stats["markets"],
        "schema_hash": schema_hash,
    }

    if args.dry_run:
        logger.info(
            "[DRY RUN] Would write %d candidate rows to %s\n%s",
            len(candidates),
            args.output_dir,
            json.dumps(manifest, indent=2, default=str),
        )
        return 0

    output_dir = Path(args.output_dir)
    run_dir = output_dir / run_id
    _atomic_write_parquet(candidates, run_dir / "PM_CANDIDATES_CURRENT.parquet")

    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    manifest["status"] = "SUCCESS"
    (run_dir / "RUN_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    latest_tmp = output_dir / "LATEST_RUN_ID.txt.tmp"
    latest_tmp.write_text(run_id, encoding="utf-8")
    latest_tmp.replace(output_dir / "LATEST_RUN_ID.txt")

    logger.info("refresh_pm_candidates complete: %s (%d rows)", run_dir, len(candidates))
    logger.info(json.dumps(manifest, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
