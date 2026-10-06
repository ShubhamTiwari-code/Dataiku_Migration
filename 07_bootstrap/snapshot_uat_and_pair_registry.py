"""
dataiku_migration/bootstrap/snapshot_uat_and_pair_registry.py

One-time (repeatable) bootstrap: takes a READ-ONLY snapshot of the current local
UAT state (uat/reports_decile/*.csv, models/paso_6_model_strategy_decision.json,
uat/manifest/*_uat_run_manifest.json) and PairRegistry state
(data/lineage/steward_events.parquet) and writes the initial versions of the
AUTOMATION_POLICY and RESOLVED_PAIR_REGISTRY contracts defined in
dataiku_migration/contracts/.

Does NOT modify src/lineage/pair_registry.py or any production file - it only
READS existing local artifacts and WRITES new snapshot files under
dataiku_migration/bootstrap/output/. Upload the resulting Parquet files to the
corresponding Dataiku Managed Folders as seed data; from that point forward,
Dataiku recipes maintain these two contracts - see
governance/GOVERNANCE_CONTINUITY.md for how governance is preserved.

Known limitations (see RUN_MANIFEST.json emitted per run):
- INGESTED_FILE_REGISTRY is bootstrapped EMPTY: historical source-file hashes for
  already-ingested pm_reports were never tracked and cannot be reconstructed.
- Legacy steward_events rows predate the `decision_source` field (PRE_IMPLEMENTATION_AUDIT
  finding F1) and are conservatively classified as LEGACY_DSR_FALLBACK, never HUMAN or
  AUTOMATED, per RULE-026.
- source_report / source_file_hash for legacy rows use documented sentinel values
  rather than fabricated data.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger("bootstrap_snapshot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

REPO_ROOT = Path(__file__).resolve().parents[2]
SENTINEL_LEGACY_SOURCE_REPORT = "LEGACY_BOOTSTRAP_NO_SOURCE_FILE"
SENTINEL_LEGACY_FILE_HASH = "UNKNOWN_LEGACY"


def _load_iso_to_slug(root: Path) -> Dict[str, str]:
    """Reuse (not duplicate) the canonical ISO<->slug mapping from uat_09, by loading
    the real script file as a module - avoids hand-copying a table that could drift."""
    path = root / "scripts" / "uat_09_process_pm_report_decisions.py"
    spec = importlib.util.spec_from_file_location("_uat_09_for_bootstrap", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return dict(module.ISO_TO_SLUG)


def _infer_slug_from_run_id(uat_run_id: str, known_slugs: set) -> Optional[str]:
    if uat_run_id in known_slugs:
        return uat_run_id
    matches = [s for s in known_slugs if uat_run_id.startswith(s + "_")]
    if not matches:
        return None
    return max(matches, key=len)


def build_automation_policy(root: Path, iso_to_slug: Dict[str, str], policy_version: str):
    slug_to_iso = {slug: iso for iso, slug in iso_to_slug.items()}
    paso6_path = root / "models" / "paso_6_model_strategy_decision.json"
    paso6 = json.loads(paso6_path.read_text(encoding="utf-8")) if paso6_path.exists() else {}
    by_country = paso6.get("decision", {}).get("by_country", {})
    routing_version = str(paso6.get("timestamp", ""))

    decile_dir = root / "uat" / "reports_decile"
    rows = []
    markets_skipped_no_iso = []
    for csv_path in sorted(decile_dir.glob("*_decile_combined_analysis.csv")):
        slug = csv_path.name[: -len("_decile_combined_analysis.csv")]
        market_iso = slug_to_iso.get(slug)
        if not market_iso:
            markets_skipped_no_iso.append(slug)
            continue
        try:
            df = pd.read_csv(csv_path, dtype=str)
        except Exception as exc:
            logger.warning("Could not read %s: %s", csv_path, exc)
            continue

        strategy_entry = by_country.get(slug, {})
        model_strategy = str(strategy_entry.get("decision", "UNKNOWN")).lower()
        if model_strategy == "custom":
            model_filename = f"model_custom_{slug}.pkl"
        elif model_strategy == "hybrid":
            model_filename = "model_hybrid.pkl"
        elif model_strategy == "global":
            model_filename = "model_global.pkl"
        else:
            model_filename = "UNKNOWN"

        manifest_path = root / "uat" / "manifest" / f"{slug}_uat_run_manifest.json"
        approved_run_id = "UNKNOWN"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                approved_run_id = str(manifest.get("uat_run_id", "UNKNOWN"))
            except Exception as exc:
                logger.warning("Could not read manifest %s: %s", manifest_path, exc)

        for _, r in df.iterrows():
            # Sourced from the CSV's `automation_recommendation` column (final
            # MANUAL/AUTO_MERGE/AUTO_NO_MERGE) — NOT the CSV's own `automation_action`
            # column, which is a different, candidate-level field (e.g. AUTO_MERGE_CANDIDATE).
            automation_action = str(r.get("automation_recommendation", "MANUAL"))
            if automation_action not in {"AUTO_MERGE", "AUTO_NO_MERGE", "MANUAL"}:
                automation_action = "MANUAL"
            sha_current = r.get("model_file_sha256_current")
            sha_manifest = r.get("model_file_sha256_manifest")
            version_status = str(r.get("model_version_status", "UNKNOWN"))

            approval_status = "APPROVED" if automation_action != "MANUAL" else "NOT_APPROVED"
            # RULE-025 fail-safe: any drift or unverifiable model version blocks approval
            if version_status != "STABLE" or (sha_current and sha_manifest and sha_current != sha_manifest):
                approval_status = "AMBIGUOUS"

            rows.append({
                "market_iso": market_iso,
                "market_slug": slug,
                "score_bucket": r.get("score_bucket"),
                "automation_action": automation_action,
                "approval_status": approval_status,
                "model_strategy": model_strategy,
                "model_filename": model_filename,
                "model_sha256": sha_manifest or "UNKNOWN",
                "routing_version": routing_version,
                "policy_version": policy_version,
                "approved_run_id": approved_run_id,
                "effective_from": r.get("generation_date"),
                "source_artifact": f"{csv_path.relative_to(root).as_posix()},models/paso_6_model_strategy_decision.json",
            })

    if markets_skipped_no_iso:
        logger.warning("AUTOMATION_POLICY: skipped %d markets with no ISO mapping: %s",
                        len(markets_skipped_no_iso), sorted(set(markets_skipped_no_iso)))
    return pd.DataFrame(rows), markets_skipped_no_iso


def build_resolved_pair_registry(root: Path, iso_to_slug: Dict[str, str], run_id: str) -> pd.DataFrame:
    slug_to_iso = {slug: iso for iso, slug in iso_to_slug.items()}
    known_slugs = set(slug_to_iso.keys())
    steward_path = root / "data" / "lineage" / "steward_events.parquet"
    if not steward_path.exists():
        logger.warning("No steward_events.parquet found at %s - RESOLVED_PAIR_REGISTRY bootstrap empty", steward_path)
        return pd.DataFrame()

    events = pd.read_parquet(steward_path)
    rows = []
    unresolved_run_ids = set()
    for _, e in events.iterrows():
        uat_run_id = str(e.get("uat_run_id", ""))
        slug = _infer_slug_from_run_id(uat_run_id, known_slugs)
        if not slug:
            unresolved_run_ids.add(uat_run_id)
            continue
        pair_id = e.get("pair_id")
        if not pair_id:
            continue
        steward_label = e.get("steward_label")
        normalized_decision = str(int(steward_label)) if pd.notna(steward_label) else None
        reviewed_at = e.get("review_date")
        rows.append({
            "market_iso": slug_to_iso[slug],
            "market_slug": slug,
            "pair_id": pair_id,
            "steward_decision": e.get("steward_decision"),
            "normalized_decision": normalized_decision,
            "decision_source": "LEGACY_DSR_FALLBACK",
            "reviewed_at": reviewed_at,
            "source_report": SENTINEL_LEGACY_SOURCE_REPORT,
            "source_file_hash": SENTINEL_LEGACY_FILE_HASH,
            "report_mode": "blind",
            "model_version": None,
            "model_sha256": None,
            "score_bucket": None,
            "ingestion_run_id": run_id,
            "first_seen_at": reviewed_at,
            "last_seen_at": reviewed_at,
            "record_status": "active",
        })

    if unresolved_run_ids:
        logger.warning("RESOLVED_PAIR_REGISTRY: %d uat_run_id values unmapped to a market slug: %s",
                        len(unresolved_run_ids), sorted(unresolved_run_ids)[:20])

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Conflict detection per contract: same (market_iso, pair_id), differing normalized_decision
    df = df.sort_values("reviewed_at")
    dup_mask = df.duplicated(subset=["market_iso", "pair_id"], keep=False)
    conflicts = df[dup_mask].groupby(["market_iso", "pair_id"])["normalized_decision"].nunique().gt(1)
    conflicting_keys = set(conflicts[conflicts].index)
    if conflicting_keys:
        df["record_status"] = df.apply(
            lambda row: "conflict" if (row["market_iso"], row["pair_id"]) in conflicting_keys else row["record_status"],
            axis=1,
        )
    df["_rank"] = df.groupby(["market_iso", "pair_id"]).cumcount()
    df.loc[(df["_rank"] > 0) & (df["record_status"] != "conflict"), "record_status"] = "superseded"
    df = df.drop(columns=["_rank"])
    return df


def _atomic_write_parquet(df: pd.DataFrame, final_path: Path) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")
    df.to_parquet(tmp_path, index=False)
    tmp_path.replace(final_path)  # atomic on same filesystem


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "dataiku_migration" / "bootstrap" / "output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run_id = f"BOOTSTRAP-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    run_dir = args.output_dir / run_id

    iso_to_slug = _load_iso_to_slug(args.root)
    policy_df, skipped_markets = build_automation_policy(args.root, iso_to_slug, policy_version=run_id)
    resolved_df = build_resolved_pair_registry(args.root, iso_to_slug, run_id=run_id)

    manifest = {
        "run_id": run_id,
        "process_name": "bootstrap_snapshot_uat_and_pair_registry",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": bool(args.dry_run),
        "automation_policy_rows": int(len(policy_df)),
        "automation_policy_markets_skipped_no_iso_mapping": sorted(set(skipped_markets)),
        "resolved_pair_registry_rows": int(len(resolved_df)),
        "resolved_pair_registry_conflicts": int((resolved_df["record_status"] == "conflict").sum()) if not resolved_df.empty else 0,
        "ingested_file_registry_rows": 0,
        "known_limitations": [
            "INGESTED_FILE_REGISTRY bootstrapped empty - no historical file hashes available.",
            "RESOLVED_PAIR_REGISTRY legacy rows use decision_source=LEGACY_DSR_FALLBACK and "
            "sentinel source_report/source_file_hash values (data not retroactively available).",
        ],
    }

    if args.dry_run:
        logger.info("[DRY RUN] Would write to %s\n%s", run_dir, json.dumps(manifest, indent=2, default=str))
        return 0

    _atomic_write_parquet(policy_df, run_dir / "AUTOMATION_POLICY.parquet")
    _atomic_write_parquet(resolved_df, run_dir / "RESOLVED_PAIR_REGISTRY.parquet")
    empty_ifr = pd.DataFrame(columns=[
        "file_name", "file_path", "file_hash", "market_iso", "discovered_at", "processed_at",
        "raw_rows", "rows_with_decision", "automated_rows_excluded", "invalid_decisions",
        "duplicates_within_file", "duplicates_across_files", "already_resolved",
        "new_resolved_pairs", "conflicting_decisions", "status", "error_message", "ingestion_run_id",
    ])
    _atomic_write_parquet(empty_ifr, run_dir / "INGESTED_FILE_REGISTRY.parquet")

    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    manifest["status"] = "SUCCESS"
    (run_dir / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    latest_tmp = args.output_dir / "LATEST_RUN_ID.txt.tmp"
    latest_tmp.write_text(run_id, encoding="utf-8")
    latest_tmp.replace(args.output_dir / "LATEST_RUN_ID.txt")

    logger.info("Bootstrap snapshot complete: %s", run_dir)
    logger.info(json.dumps(manifest, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
