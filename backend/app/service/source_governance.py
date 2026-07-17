"""半导体公开资料的采集、审核和本地归档工具。

这个模块故意不直接写入 PostgreSQL/Milvus：采集与知识库入库分离，
避免将版权不明、重复或低质量内容自动向量化。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import requests
import yaml


VALID_DOMAINS = {
    "chip_design_eda_ip",
    "materials_equipment",
    "wafer_fabrication",
    "packaging_testing",
}
VALID_POLICIES = {"fulltext_allowed", "metadata_only", "blocked"}
VALID_REVIEW_STATUSES = {"approved", "metadata_only", "pending", "rejected"}
VALID_CONTENT_FORMATS = {"pdf", "markdown"}
PRESERVED_LINE_END_PREFIXES = {
    "cross", "end", "full", "high", "in", "low", "multi", "next",
    "non", "real", "self", "state", "well",
}


def _line_fingerprint(line: str) -> str:
    """Normalize volatile page numbers before comparing headers and footers."""
    value = re.sub(r"\b\d+\b", "#", line.strip().casefold())
    return re.sub(r"\s+", " ", value)


def _repeated_page_margin_lines(pages: list[list[str]]) -> set[str]:
    """Find short lines repeated near page margins, not repeated body claims."""
    if len(pages) < 3:
        return set()
    occurrences: dict[str, set[int]] = {}
    for page_index, lines in enumerate(pages):
        nonempty = [line for line in lines if line.strip()]
        if len(nonempty) < 7:
            continue
        for line in nonempty[:2] + nonempty[-2:]:
            stripped = line.strip()
            if not stripped or len(stripped) > 120:
                continue
            fingerprint = _line_fingerprint(stripped)
            if fingerprint:
                occurrences.setdefault(fingerprint, set()).add(page_index)
    threshold = max(3, (len(pages) + 1) // 2)
    return {
        fingerprint
        for fingerprint, page_numbers in occurrences.items()
        if len(page_numbers) >= threshold
    }


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 140 or stripped.endswith((".", ";", ",")):
        return False
    if re.match(r"^[A-Z][.)]\s+\S+", stripped):
        return True
    letters = [char for char in stripped if char.isalpha()]
    return bool(letters) and len(letters) >= 4 and all(
        not char.islower() for char in letters
    )


def normalize_pdf_text(text: str) -> str:
    """Turn pdftotext layout output into stable, chunk-friendly Markdown.

    The transformation is deterministic: it removes repeated page margins,
    repairs end-of-line hyphenation, preserves list boundaries, and promotes
    likely section titles. It does not invent OCR text or headings.
    """
    raw_pages = [page.splitlines() for page in re.split(r"\f+", text)]
    pages = [page for page in raw_pages if any(line.strip() for line in page)]
    repeated_margins = _repeated_page_margin_lines(pages)
    kept: list[str] = []
    for lines in pages:
        nonempty_positions = [i for i, line in enumerate(lines) if line.strip()]
        margin_positions = (
            set(nonempty_positions[:2] + nonempty_positions[-2:])
            if len(nonempty_positions) >= 7
            else set()
        )
        for index, line in enumerate(lines):
            stripped = re.sub(r"[ \t]+", " ", line).strip()
            if (
                index in margin_positions
                and _line_fingerprint(stripped) in repeated_margins
            ):
                continue
            if index in margin_positions and re.fullmatch(
                r"(?:page\s+)?\d+", stripped, re.I
            ):
                continue
            if re.fullmatch(r"CHIPS\s+for\s+America\s+\d+", stripped, re.I):
                continue
            if re.search(r"(?:\.\s*){4,}\d+\s*$", stripped):
                continue
            kept.append(stripped)
        kept.append("")

    output: list[str] = []
    paragraph = ""

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            output.extend([paragraph.strip(), ""])
            paragraph = ""

    for line in kept:
        if not line:
            flush_paragraph()
            continue
        if re.match(r"^(?:[-*•]|\d+[.)])\s+", line):
            flush_paragraph()
            paragraph = re.sub(r"^•\s*", "- ", line)
            continue
        if _looks_like_heading(line):
            flush_paragraph()
            heading = re.sub(r"^#+\s*", "", line).strip()
            previous = output[-2] if len(output) >= 2 else ""
            starts_section = bool(re.match(r"^(?:CHAPTER\b|[A-Z][.)]\s)", heading))
            previous_is_chapter = bool(re.match(r"^## CHAPTER\b", previous))
            if previous.startswith("## ") and not starts_section and not previous_is_chapter:
                output[-2] = f"{previous} {heading}"
            else:
                output.extend([f"## {heading}", ""])
            continue
        if paragraph.endswith("-") and re.match(r"^[a-z]", line):
            prefix = re.search(r"([A-Za-z]+)-$", paragraph)
            if prefix and prefix.group(1).casefold() in PRESERVED_LINE_END_PREFIXES:
                paragraph += line
            else:
                paragraph = paragraph[:-1] + line
        elif paragraph:
            paragraph += " " + line
        else:
            paragraph = line
    flush_paragraph()
    normalized = "\n".join(output)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    # PDF source code comments such as ``# vector load`` are plain evidence,
    # not Markdown H1 headings. Escaping them prevents enormous breadcrumbs.
    return re.sub(r"(?m)^# (?=\S)", r"\\# ", normalized)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_id(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:20]


def resolve_managed_path(source_root: Path, value: str) -> Path:
    """Resolve a manifest path without allowing it to escape the source root."""
    root = source_root.resolve()
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"资料路径越界: {value}") from exc
    return resolved


def portable_managed_path(source_root: Path, value: str) -> str:
    """Serialize a managed path relative to the source root for portability."""
    return resolve_managed_path(source_root, value).relative_to(
        source_root.resolve()
    ).as_posix()


@dataclass
class SourceCandidate:
    candidate_id: str
    source_id: str
    source_name: str
    title: str
    domains: list[str]
    document_type: str
    source_url: str
    fulltext_url: str | None = None
    content_format: str = "pdf"
    published_at: str | None = None
    document_version: str | None = None
    authority_level: str = "unknown"
    claim_type: str = "unknown"
    doi: str | None = None
    external_id: str | None = None
    publisher: str | None = None
    container_title: str | None = None
    license_name: str | None = None
    license_url: str | None = None
    is_open_access: bool = False
    ingestion_policy: str = "metadata_only"
    review_status: str = "pending"
    quality_score: int = 0
    quality_reasons: list[str] = field(default_factory=list)
    retrieved_at: str = field(default_factory=utc_now)
    content_hash: str | None = None
    local_raw_path: str | None = None
    local_normalized_path: str | None = None
    validation_error: str | None = None

    def validate(self) -> None:
        if not self.title.strip():
            raise ValueError("title 不能为空")
        if not self.domains or not set(self.domains).issubset(VALID_DOMAINS):
            raise ValueError(f"无效领域: {self.domains}")
        if self.ingestion_policy not in VALID_POLICIES:
            raise ValueError(f"无效入库策略: {self.ingestion_policy}")
        if self.review_status not in VALID_REVIEW_STATUSES:
            raise ValueError(f"无效审核状态: {self.review_status}")
        if self.content_format not in VALID_CONTENT_FORMATS:
            raise ValueError(f"无效全文格式: {self.content_format}")
        for value in (self.source_url, self.fulltext_url):
            if value and urlparse(value).scheme != "https":
                raise ValueError(f"仅允许 HTTPS URL: {value}")
        if self.review_status == "approved" and self.ingestion_policy != "fulltext_allowed":
            raise ValueError("只有 fulltext_allowed 资料才能批准全文入库")

    def calculate_quality(self) -> None:
        score = 0
        reasons: list[str] = []
        authority_scores = {
            "official": 30,
            "industry_standard": 28,
            "academic": 24,
            "enterprise": 18,
            "media": 8,
            "unknown": 0,
        }
        authority = authority_scores.get(self.authority_level, 0)
        score += authority
        reasons.append(f"来源权威性 +{authority}")
        if self.doi or self.external_id:
            score += 15
            reasons.append("持久标识符 +15")
        if self.published_at:
            score += 10
            reasons.append("发布日期完整 +10")
        if self.document_version:
            score += 5
            reasons.append("版本可追溯 +5")
        if self.license_url:
            license_score = 15 if self.ingestion_policy == "fulltext_allowed" else 5
            score += license_score
            reasons.append(f"权利信息可追溯 +{license_score}")
        if self.source_url.startswith("https://"):
            score += 5
            reasons.append("HTTPS 原始链接 +5")
        if self.ingestion_policy == "fulltext_allowed":
            score += 10
            reasons.append("全文权利明确 +10")
        if self.claim_type in {"government_report", "industry_standard", "peer_reviewed_research"}:
            score += 10
            reasons.append("文档类型可核验 +10")
        self.quality_score = min(score, 100)
        self.quality_reasons = reasons


def load_registry(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        registry = yaml.safe_load(handle) or {}
    sources = registry.get("sources") or []
    source_ids = [source.get("id") for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("资料源白名单存在重复 id")
    return registry


def source_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {source["id"]: source for source in registry.get("sources", [])}


def candidate_from_registry(document: dict[str, Any], source: dict[str, Any]) -> SourceCandidate:
    candidate = SourceCandidate(
        candidate_id=document.get("id") or stable_id(document["source_url"]),
        source_id=source["id"],
        source_name=source["name"],
        title=document["title"],
        domains=list(document["domains"]),
        document_type=document.get("document_type", "unknown"),
        source_url=document["source_url"],
        fulltext_url=document.get("fulltext_url"),
        content_format=document.get("content_format", "pdf"),
        published_at=document.get("published_at"),
        document_version=document.get("document_version"),
        authority_level=source.get("authority_level", "unknown"),
        claim_type=source.get("claim_type", "unknown"),
        doi=document.get("doi"),
        external_id=document.get("external_id"),
        license_name=source.get("license_name"),
        license_url=source.get("license_url"),
        is_open_access=source.get("ingestion_policy") == "fulltext_allowed",
        ingestion_policy=source.get("ingestion_policy", "metadata_only"),
        review_status=document.get("review_status", "pending"),
    )
    candidate.validate()
    candidate.calculate_quality()
    return candidate


def allowed_domain(url: str, domains: Iterable[str]) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains)


def deduplicate(candidates: Iterable[SourceCandidate]) -> list[SourceCandidate]:
    selected: dict[str, SourceCandidate] = {}
    for candidate in candidates:
        # 同一官方索引页可以指向多份独立规范，因此全文 URL
        # 的去重优先级要高于来源页 URL。
        key = (candidate.doi or candidate.fulltext_url or candidate.source_url).strip().lower()
        existing = selected.get(key)
        if existing is None or candidate.quality_score > existing.quality_score:
            selected[key] = candidate
    return sorted(selected.values(), key=lambda item: (-item.quality_score, item.title.lower()))


def write_jsonl(path: Path, candidates: Iterable[SourceCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            handle.write(json.dumps(asdict(candidate), ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                candidates.append(SourceCandidate(**json.loads(line)))
    return candidates


def _safe_filename(candidate: SourceCandidate) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", candidate.candidate_id).strip("-")
    suffix = ".md" if candidate.content_format == "markdown" else ".pdf"
    return f"{slug or stable_id(candidate.source_url)}{suffix}"


def download_and_normalize(
    candidate: SourceCandidate,
    source: dict[str, Any],
    raw_dir: Path,
    normalized_dir: Path,
    timeout: int = 60,
    max_bytes: int = 50 * 1024 * 1024,
) -> SourceCandidate:
    candidate.validate()
    if candidate.review_status != "approved" or candidate.ingestion_policy != "fulltext_allowed":
        raise ValueError(f"{candidate.candidate_id}: 未通过全文入库闸门")
    if not candidate.fulltext_url:
        raise ValueError(f"{candidate.candidate_id}: 缺少 fulltext_url")
    allowed_domains = source.get("allowed_domains") or []
    if not allowed_domain(candidate.fulltext_url, allowed_domains):
        raise ValueError(f"{candidate.candidate_id}: 下载域名不在白名单")

    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / _safe_filename(candidate)
    temporary_path = raw_path.with_suffix(".part")

    headers = {"User-Agent": "SemiconductorResearchAssistant/1.0 (public-source curation)"}
    with requests.get(candidate.fulltext_url, headers=headers, timeout=timeout, stream=True) as response:
        response.raise_for_status()
        if not allowed_domain(response.url, allowed_domains):
            raise ValueError(f"{candidate.candidate_id}: 重定向目标不在白名单")
        digest = hashlib.sha256()
        size = 0
        with temporary_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 128):
                if not chunk:
                    continue
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError(f"{candidate.candidate_id}: 文件超过 {max_bytes} 字节")
                digest.update(chunk)
                handle.write(chunk)
    with temporary_path.open("rb") as handle:
        raw_bytes = handle.read()
    if candidate.content_format == "pdf" and not raw_bytes.startswith(b"%PDF-"):
        temporary_path.unlink(missing_ok=True)
        raise ValueError(f"{candidate.candidate_id}: 下载内容不是 PDF")
    temporary_path.replace(raw_path)

    if candidate.content_format == "markdown":
        try:
            text = raw_bytes.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ValueError(f"{candidate.candidate_id}: Markdown 不是 UTF-8") from exc
        if "\x00" in text or len(text) < 500:
            raise ValueError(f"{candidate.candidate_id}: Markdown 有效文本过少")
    else:
        text_path = raw_path.with_suffix(".txt")
        process = subprocess.run(
            # -raw follows the PDF content stream and is materially safer for
            # two-column reports than joining both visual columns line by line.
            ["pdftotext", "-raw", str(raw_path), str(text_path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(f"{candidate.candidate_id}: pdftotext 失败: {process.stderr.strip()}")
        text = text_path.read_text(encoding="utf-8", errors="replace").strip()
        text_path.unlink(missing_ok=True)
        if len(text) < 500:
            raise ValueError(f"{candidate.candidate_id}: PDF 可提取文本过少")
        text = normalize_pdf_text(text)
        if len(text) < 500:
            raise ValueError(f"{candidate.candidate_id}: PDF 规范化后有效文本过少")

    metadata = {
        "candidate_id": candidate.candidate_id,
        "title": candidate.title,
        "domains": candidate.domains,
        "source_name": candidate.source_name,
        "source_url": candidate.source_url,
        "document_type": candidate.document_type,
        "content_format": candidate.content_format,
        "published_at": candidate.published_at,
        "document_version": candidate.document_version,
        "authority_level": candidate.authority_level,
        "claim_type": candidate.claim_type,
        "doi": candidate.doi,
        "license_name": candidate.license_name,
        "license_url": candidate.license_url,
        "retrieved_at": candidate.retrieved_at,
        "content_hash": digest.hexdigest(),
        "is_synthetic": False,
    }
    normalized_path = normalized_dir / f"{raw_path.stem}.md"
    frontmatter = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip()
    normalized_path.write_text(
        f"---\n{frontmatter}\n---\n\n# {candidate.title}\n\n{text}\n",
        encoding="utf-8",
    )
    candidate.content_hash = digest.hexdigest()
    candidate.local_raw_path = str(raw_path.resolve())
    candidate.local_normalized_path = str(normalized_path.resolve())
    candidate.validation_error = None
    return candidate
