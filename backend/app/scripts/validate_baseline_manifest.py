"""Validate the frozen portfolio baseline against its dataset and report."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_baseline(root: Path, manifest_path: Path) -> list[str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    if manifest.get("schema_version") != 1:
        errors.append("unsupported schema_version")

    dataset_config = manifest.get("dataset", {})
    report_config = manifest.get("report", {})
    dataset_path = root / str(dataset_config.get("path", ""))
    report_path = root / str(report_config.get("path", ""))

    for label, path, expected_hash in (
        ("dataset", dataset_path, dataset_config.get("sha256")),
        ("report", report_path, report_config.get("sha256")),
    ):
        if not path.is_file():
            errors.append(f"{label} file missing: {path}")
        elif _sha256(path) != expected_hash:
            errors.append(f"{label} sha256 mismatch: {path}")

    if errors:
        return errors

    dataset: Any = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases = dataset.get("cases", dataset) if isinstance(dataset, dict) else dataset
    if len(cases) != dataset_config.get("cases"):
        errors.append("dataset case count mismatch")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    metadata = report.get("metadata", {})
    summary = report.get("summary", {})
    if metadata.get("dataset_sha256") != dataset_config.get("sha256"):
        errors.append("report metadata dataset_sha256 mismatch")
    if metadata.get("generated_at") != report_config.get("generated_at"):
        errors.append("report generated_at mismatch")
    if "latest" in str(report_config.get("path", "")).casefold():
        errors.append("canonical baseline report must not use a latest filename")

    for metric, expected in manifest.get("accepted_metrics", {}).items():
        if summary.get(metric) != expected:
            errors.append(
                f"metric mismatch for {metric}: expected {expected!r}, got {summary.get(metric)!r}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest", default="reports/baseline-manifest.json"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    manifest_path = root / args.manifest
    errors = validate_baseline(root, manifest_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Baseline manifest valid: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
