"""Validate the reviewed source manifest without requiring external services."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from service.source_governance import (  # noqa: E402
    SourceCandidate,
    read_jsonl,
    resolve_managed_path,
)

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.S)


def _issue(
    level: str,
    code: str,
    message: str,
    candidate_id: str | None = None,
) -> dict[str, str]:
    issue = {"level": level, "code": code, "message": message}
    if candidate_id:
        issue["candidate_id"] = candidate_id
    return issue


def _frontmatter(path: Path) -> dict[str, Any]:
    match = FRONTMATTER_PATTERN.match(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("缺少 YAML frontmatter")
    metadata = yaml.safe_load(match.group(1)) or {}
    if not isinstance(metadata, dict):
        raise ValueError("YAML frontmatter 必须是对象")
    return metadata


def validate_manifest(
    manifest_path: Path,
    *,
    source_root: Path | None = None,
    min_approved: int = 1,
    require_raw: bool = False,
) -> tuple[list[SourceCandidate], list[dict[str, str]]]:
    manifest_path = manifest_path.resolve()
    root = (source_root or manifest_path.parent.parent).resolve()
    candidates = read_jsonl(manifest_path)
    issues: list[dict[str, str]] = []

    id_counts = Counter(candidate.candidate_id for candidate in candidates)
    for candidate_id, count in id_counts.items():
        if count > 1:
            issues.append(_issue(
                "error", "duplicate_candidate", f"候选资料重复 {count} 次", candidate_id
            ))

    approved = [item for item in candidates if item.review_status == "approved"]
    if len(approved) < min_approved:
        issues.append(_issue(
            "error", "approved_count", f"获批全文 {len(approved)} 份，少于要求 {min_approved} 份"
        ))

    hash_owners: dict[str, str] = {}
    for candidate in candidates:
        candidate_id = candidate.candidate_id
        try:
            candidate.validate()
        except ValueError as exc:
            issues.append(_issue("error", "invalid_candidate", str(exc), candidate_id))

        for field_name in ("local_raw_path", "local_normalized_path"):
            value = getattr(candidate, field_name)
            if value and Path(value).is_absolute():
                issues.append(_issue(
                    "error", "absolute_path", f"{field_name} 必须是相对路径", candidate_id
                ))

        if candidate.review_status != "approved":
            if candidate.local_raw_path or candidate.local_normalized_path:
                issues.append(_issue(
                    "error", "unapproved_local_file", "未获批资料不得配置本地全文", candidate_id
                ))
            continue

        if not candidate.license_name or not candidate.license_url:
            issues.append(_issue(
                "error", "missing_license", "获批全文缺少许可名称或链接", candidate_id
            ))
        if not candidate.content_hash or not SHA256_PATTERN.fullmatch(candidate.content_hash):
            issues.append(_issue(
                "error", "invalid_hash", "content_hash 必须是 64 位小写 SHA-256", candidate_id
            ))
        elif candidate.content_hash in hash_owners:
            issues.append(_issue(
                "error",
                "duplicate_content",
                f"与 {hash_owners[candidate.content_hash]} 的全文哈希重复",
                candidate_id,
            ))
        else:
            hash_owners[candidate.content_hash] = candidate_id

        if not candidate.local_normalized_path:
            issues.append(_issue(
                "error", "missing_normalized_path", "获批全文缺少规范化文档路径", candidate_id
            ))
            continue
        try:
            normalized_path = resolve_managed_path(root, candidate.local_normalized_path)
        except ValueError as exc:
            issues.append(_issue("error", "path_escape", str(exc), candidate_id))
            continue
        if not normalized_path.is_file():
            issues.append(_issue(
                "error", "missing_normalized_file", f"规范化文档不存在: {candidate.local_normalized_path}", candidate_id
            ))
            continue

        try:
            metadata = _frontmatter(normalized_path)
        except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
            issues.append(_issue("error", "invalid_frontmatter", str(exc), candidate_id))
            continue
        expected_metadata = {
            "candidate_id": candidate.candidate_id,
            "content_hash": candidate.content_hash,
            "source_url": candidate.source_url,
            "license_url": candidate.license_url,
            "is_synthetic": False,
        }
        for key, expected in expected_metadata.items():
            if metadata.get(key) != expected:
                issues.append(_issue(
                    "error",
                    "metadata_mismatch",
                    f"frontmatter.{key}={metadata.get(key)!r}，期望 {expected!r}",
                    candidate_id,
                ))

        if require_raw:
            if not candidate.local_raw_path:
                issues.append(_issue(
                    "error", "missing_raw_path", "获批全文缺少原始文件路径", candidate_id
                ))
            else:
                try:
                    raw_path = resolve_managed_path(root, candidate.local_raw_path)
                except ValueError as exc:
                    issues.append(_issue("error", "path_escape", str(exc), candidate_id))
                else:
                    if not raw_path.is_file():
                        issues.append(_issue(
                            "error", "missing_raw_file", f"原始文件不存在: {candidate.local_raw_path}", candidate_id
                        ))

    return candidates, issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--min-approved", type=int, default=1)
    parser.add_argument("--require-raw", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    candidates, issues = validate_manifest(
        args.manifest,
        source_root=args.source_root,
        min_approved=args.min_approved,
        require_raw=args.require_raw,
    )
    summary = {
        "manifest": str(args.manifest.resolve()),
        "candidate_count": len(candidates),
        "approved_count": sum(item.review_status == "approved" for item in candidates),
        "metadata_only_count": sum(
            item.review_status == "metadata_only" for item in candidates
        ),
        "errors": sum(issue["level"] == "error" for issue in issues),
        "warnings": sum(issue["level"] == "warning" for issue in issues),
        "issues": issues,
    }
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
