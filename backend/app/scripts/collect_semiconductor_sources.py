"""收集高质量半导体公开资料，生成审核队列并下载获批全文。"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

import requests

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from service.source_governance import (  # noqa: E402
    SourceCandidate,
    candidate_from_registry,
    deduplicate,
    download_and_normalize,
    load_registry,
    read_jsonl,
    portable_managed_path,
    resolve_managed_path,
    source_map,
    stable_id,
    write_jsonl,
)


def _crossref_date(item: dict[str, Any]) -> str | None:
    date_parts = (item.get("published-print") or item.get("published-online") or {}).get("date-parts")
    if not date_parts or not date_parts[0]:
        return None
    parts = list(date_parts[0]) + [1, 1]
    try:
        return date(parts[0], parts[1], parts[2]).isoformat()
    except (TypeError, ValueError):
        return None


def discover_crossref(
    registry: dict[str, Any],
    rows_per_query: int,
    from_year: int,
) -> list[SourceCandidate]:
    source = source_map(registry)["crossref"]
    trusted_publishers = [
        value.casefold() for value in source.get("trusted_publishers", [])
    ]
    headers = {"User-Agent": "SemiconductorResearchAssistant/1.0"}
    mailto = os.getenv("CROSSREF_MAILTO")
    if mailto:
        headers["User-Agent"] += f" (mailto:{mailto})"
    candidates: list[SourceCandidate] = []
    for domain, queries in (registry.get("discovery_queries") or {}).items():
        for query in queries:
            params = {
                "query.bibliographic": query,
                "filter": f"from-pub-date:{from_year}-01-01,type:journal-article",
                "select": "DOI,title,publisher,published-online,published-print,URL,container-title,type,license",
                "rows": rows_per_query,
                "sort": "relevance",
                "order": "desc",
            }
            response = requests.get(
                "https://api.crossref.org/works",
                params=params,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            for item in response.json().get("message", {}).get("items", []):
                title_parts = item.get("title") or []
                doi = item.get("DOI")
                if not title_parts or not doi:
                    continue
                publisher = (item.get("publisher") or "").strip()
                if trusted_publishers and not any(
                    trusted in publisher.casefold() for trusted in trusted_publishers
                ):
                    continue
                license_entries = item.get("license") or []
                license_url = license_entries[0].get("URL") if license_entries else source.get("license_url")
                candidate = SourceCandidate(
                    candidate_id=f"crossref-{stable_id(doi)}",
                    source_id="crossref",
                    source_name=source["name"],
                    title=title_parts[0].strip(),
                    domains=[domain],
                    document_type=item.get("type", "journal-article"),
                    source_url=item.get("URL") or f"https://doi.org/{doi}",
                    published_at=_crossref_date(item),
                    authority_level=source["authority_level"],
                    claim_type=source["claim_type"],
                    doi=doi,
                    publisher=publisher,
                    container_title=(item.get("container-title") or [None])[0],
                    license_name=source.get("license_name"),
                    license_url=license_url,
                    is_open_access=bool(license_entries),
                    ingestion_policy="metadata_only",
                    review_status="metadata_only",
                )
                candidate.validate()
                candidate.calculate_quality()
                candidates.append(candidate)
    return candidates


def write_summary(path: Path, candidates: list[SourceCandidate]) -> None:
    by_status: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    for candidate in candidates:
        by_status[candidate.review_status] = by_status.get(candidate.review_status, 0) + 1
        for domain in candidate.domains:
            by_domain[domain] = by_domain.get(domain, 0) + 1
    lines = [
        "# 半导体公开资料采集报告",
        "",
        f"- 候选资料：{len(candidates)} 份",
        f"- 已批准全文：{by_status.get('approved', 0)} 份",
        f"- 仅元数据：{by_status.get('metadata_only', 0)} 份",
        f"- 待人工审核：{by_status.get('pending', 0)} 份",
        "",
        "## 领域覆盖",
        "",
    ]
    for domain, count in sorted(by_domain.items()):
        lines.append(f"- `{domain}`：{count} 份")
    lines.extend(["", "## 资料清单", ""])
    for item in candidates:
        lines.append(
            f"- [{item.title}]({item.source_url}) — {item.source_name}，"
            f"质量 {item.quality_score}/100，`{item.review_status}`"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="采集并归档高质量半导体公开资料")
    parser.add_argument(
        "--registry",
        type=Path,
        default=APP_DIR / "config" / "semiconductor_sources.yaml",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=APP_DIR.parents[1] / "data" / "semiconductor_sources",
    )
    parser.add_argument("--offline", action="store_true", help="仅使用白名单中的精选资料")
    parser.add_argument("--rows-per-query", type=int, default=2)
    parser.add_argument("--from-year", type=int, default=2023)
    parser.add_argument("--download-approved", action="store_true")
    parser.add_argument(
        "--refresh-approved",
        action="store_true",
        help="忽略已存在的规范化文档，重新下载并校验获批全文",
    )
    args = parser.parse_args()

    registry = load_registry(args.registry.resolve())
    sources = source_map(registry)
    candidates = [
        candidate_from_registry(document, sources[document["source_id"]])
        for document in registry.get("documents", [])
    ]
    if not args.offline:
        candidates.extend(discover_crossref(registry, args.rows_per_query, args.from_year))
    candidates = deduplicate(candidates)

    queue_path = args.output_dir / "review" / "candidates.jsonl"
    if queue_path.is_file():
        previous = {item.candidate_id: item for item in read_jsonl(queue_path)}
        for candidate in candidates:
            old = previous.get(candidate.candidate_id)
            if not old:
                continue
            try:
                cached_path = (
                    resolve_managed_path(args.output_dir, old.local_normalized_path)
                    if old.local_normalized_path
                    else None
                )
            except ValueError:
                cached_path = None
            if cached_path and cached_path.is_file():
                candidate.content_hash = old.content_hash
                candidate.local_raw_path = old.local_raw_path
                candidate.local_normalized_path = old.local_normalized_path

    if args.download_approved:
        for candidate in candidates:
            if candidate.review_status != "approved":
                continue
            if candidate.local_normalized_path and not args.refresh_approved:
                print(f"[CACHED] {candidate.candidate_id}: {candidate.title}")
                continue
            try:
                download_and_normalize(
                    candidate,
                    sources[candidate.source_id],
                    args.output_dir / "raw",
                    args.output_dir / "normalized",
                )
                print(f"[OK] {candidate.candidate_id}: {candidate.title}")
            except Exception as exc:
                candidate.validation_error = str(exc)
                print(f"[FAIL] {candidate.candidate_id}: {exc}")

    for candidate in candidates:
        if candidate.local_raw_path:
            candidate.local_raw_path = portable_managed_path(
                args.output_dir, candidate.local_raw_path
            )
        if candidate.local_normalized_path:
            candidate.local_normalized_path = portable_managed_path(
                args.output_dir, candidate.local_normalized_path
            )

    write_jsonl(queue_path, candidates)
    write_summary(args.output_dir / "review" / "SUMMARY.md", candidates)
    failures = [candidate for candidate in candidates if candidate.validation_error]
    print(f"采集完成: {len(candidates)} 份，下载失败 {len(failures)} 份")
    print(f"审核队列: {queue_path.resolve()}")
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
