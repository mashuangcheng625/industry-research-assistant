"""Rebuild archived PDF Markdown with deterministic layout cleanup.

The default output is a sibling ``normalized-v2`` directory. Existing indexed
documents are never overwritten, so reviewers can inspect diffs before re-ingestion.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

from service.source_governance import normalize_pdf_text, portable_managed_path


def read_frontmatter(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", content, re.S)
    if not match:
        raise ValueError(f"{path}: 缺少 YAML frontmatter")
    metadata = yaml.safe_load(match.group(1)) or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"{path}: frontmatter 必须是对象")
    return metadata


def extract_pdf_text(pdf_path: Path) -> str:
    with tempfile.NamedTemporaryFile(suffix=".txt") as output:
        process = subprocess.run(
            ["pdftotext", "-raw", str(pdf_path), output.name],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(f"{pdf_path}: pdftotext 失败: {process.stderr.strip()}")
        return Path(output.name).read_text(encoding="utf-8", errors="replace")


def renormalize_one(raw_path: Path, current_path: Path, output_path: Path) -> dict[str, Any]:
    metadata = read_frontmatter(current_path)
    raw_text = extract_pdf_text(raw_path)
    normalized = normalize_pdf_text(raw_text)
    if len(normalized) < 500:
        raise ValueError(f"{raw_path}: 规范化后有效文本过少")

    title = str(metadata.get("title") or raw_path.stem)
    frontmatter = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        f"---\n{frontmatter}\n---\n\n# {title}\n\n{normalized}\n",
        encoding="utf-8",
    )
    return {
        "document": output_path.name,
        "pages": len([page for page in raw_text.split("\f") if page.strip()]),
        "raw_characters": len(raw_text),
        "normalized_characters": len(normalized),
        "character_ratio": round(len(normalized) / max(len(raw_text), 1), 3),
        "markdown_headings": len(re.findall(r"(?m)^##\s+", normalized)),
        "remaining_form_feeds": normalized.count("\f"),
        "extraction_mode": "raw",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/semiconductor_sources"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--report", type=Path)
    parser.add_argument("--queue", type=Path, help="现有审核队列 JSONL")
    parser.add_argument("--output-queue", type=Path, help="写入指向 v2 文档的新队列")
    args = parser.parse_args()

    raw_dir = args.root / "raw"
    current_dir = args.root / "normalized"
    output_dir = args.output_dir or args.root / "normalized-v2"
    selected = set(args.candidate)
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for raw_path in sorted(raw_dir.glob("*.pdf")):
        if selected and raw_path.stem not in selected:
            continue
        current_path = current_dir / f"{raw_path.stem}.md"
        if not current_path.exists():
            failures.append({"document": raw_path.name, "error": "缺少现有规范化文档"})
            continue
        try:
            rows.append(
                renormalize_one(raw_path, current_path, output_dir / current_path.name)
            )
        except Exception as exc:  # keep batch processing and report every failure
            failures.append({"document": raw_path.name, "error": str(exc)})

    report = {
        "source_root": ".",
        "output_dir": portable_managed_path(args.root, str(output_dir.resolve())),
        "processed": len(rows),
        "failed": len(failures),
        "documents": rows,
        "failures": failures,
    }
    if bool(args.queue) != bool(args.output_queue):
        parser.error("--queue 与 --output-queue 必须同时提供")
    if args.queue and args.output_queue:
        processed_ids = {Path(row["document"]).stem for row in rows}
        queue_rows = [
            json.loads(line)
            for line in args.queue.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        updated = 0
        for candidate in queue_rows:
            if candidate.get("candidate_id") in processed_ids:
                candidate["local_normalized_path"] = portable_managed_path(
                    args.root,
                    str((output_dir / f"{candidate['candidate_id']}.md").resolve()),
                )
                updated += 1
        args.output_queue.parent.mkdir(parents=True, exist_ok=True)
        args.output_queue.write_text(
            "".join(
                json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n"
                for candidate in queue_rows
            ),
            encoding="utf-8",
        )
        report["output_queue"] = portable_managed_path(
            args.root, str(args.output_queue.resolve())
        )
        report["queue_candidates_updated"] = updated
    report_path = args.report or output_dir / "normalization-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
