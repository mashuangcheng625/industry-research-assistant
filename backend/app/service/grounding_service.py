"""Deterministic validation and rendering for structured grounded answers."""
from __future__ import annotations

import json
import re
from typing import Any


CITATION_PATTERN = re.compile(r"\[\[(\d+)\]\]")
ASCII_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*", re.I)
CHINESE_RUN_PATTERN = re.compile(r"[一-鿿]+")
ALLOWED_UNCERTAINTY = {"certain", "limited"}
ALLOWED_STATUS = {"grounded", "insufficient"}
ENTAILMENT_VERDICTS = {"entailed", "not_entailed", "uncertain"}
CHINESE_STOP_BIGRAMS = {
    "因为", "所以", "可以", "通过", "进行", "一个", "这种", "具有",
    "用于", "以及", "需要", "能够", "实现", "其中", "相关", "系统",
}
ASCII_STOPWORDS = {
    "the", "and", "or", "a", "an", "of", "to", "in", "for", "with", "is", "are",
    "be", "by", "that", "this", "from", "as", "can", "will", "it", "its", "on",
}


class GroundingValidationError(ValueError):
    """Structured model output cannot be parsed or violates the outer schema."""


def _extract_json_object(raw: str) -> dict[str, Any]:
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.I)
        stripped = re.sub(r"\s*```$", "", stripped)
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end < start:
        raise GroundingValidationError("模型未返回 JSON 对象")
    try:
        payload = json.loads(stripped[start:end + 1])
    except json.JSONDecodeError as exc:
        raise GroundingValidationError(f"JSON 解析失败: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise GroundingValidationError("结构化回答顶层必须是对象")
    return payload


def parse_structured_answer(raw: str) -> dict[str, Any]:
    payload = _extract_json_object(raw)
    status = payload.get("answer_status")
    if status not in ALLOWED_STATUS:
        raise GroundingValidationError("answer_status 只允许 grounded/insufficient")
    claims = payload.get("claims", [])
    limitations = payload.get("limitations", [])
    if not isinstance(claims, list) or not isinstance(limitations, list):
        raise GroundingValidationError("claims/limitations 必须是数组")
    return {
        "answer_status": status,
        "claims": claims,
        "limitations": [str(item).strip() for item in limitations if str(item).strip()][:5],
    }


def _support_tokens(text: str) -> set[str]:
    folded = text.casefold()
    tokens = {
        token for token in ASCII_TOKEN_PATTERN.findall(folded)
        if len(token) >= 2 and token not in ASCII_STOPWORDS
    }
    for run in CHINESE_RUN_PATTERN.findall(folded):
        tokens.update(
            run[index:index + 2]
            for index in range(len(run) - 1)
            if run[index:index + 2] not in CHINESE_STOP_BIGRAMS
        )
    return tokens


def lexical_support_score(claim: str, evidence: str) -> float:
    """Return an auditable token-recall proxy in [0, 1]."""
    claim_tokens = _support_tokens(claim)
    if not claim_tokens:
        return 0.0
    evidence_tokens = _support_tokens(evidence)
    return len(claim_tokens & evidence_tokens) / len(claim_tokens)


def _normalized_quote(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _required_identifiers(text: str) -> set[str]:
    return {
        token.casefold()
        for token in ASCII_TOKEN_PATTERN.findall(text)
        if "_" in token
        or any(character.isdigit() for character in token)
        or (len(token) >= 2 and token.upper() == token)
    }


def validate_structured_answer(
    payload: dict[str, Any],
    references: list[dict[str, Any]],
    *,
    minimum_support_score: float = 0.12,
    max_claims: int = 12,
) -> dict[str, Any]:
    """Validate every claim independently and retain only supported claims."""
    threshold = min(1.0, max(0.0, float(minimum_support_score)))
    candidates = payload.get("claims", [])[:max_claims]
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    if payload.get("answer_status") == "insufficient":
        candidates = []

    for index, candidate in enumerate(candidates):
        reason = None
        if not isinstance(candidate, dict):
            rejected.append({"claim_index": index, "reason": "claim_not_object"})
            continue
        text = str(candidate.get("text") or "").strip()
        raw_ids = candidate.get("citation_ids", [])
        raw_quotes = candidate.get("evidence_quotes", [])
        uncertainty = str(candidate.get("uncertainty") or "certain")
        if not text or len(text) > 1200:
            reason = "invalid_claim_text"
        elif CITATION_PATTERN.search(text):
            reason = "citation_marker_inside_claim_text"
        elif uncertainty not in ALLOWED_UNCERTAINTY:
            reason = "invalid_uncertainty"
        elif not isinstance(raw_ids, list) or not raw_ids:
            reason = "missing_citations"
        elif not isinstance(raw_quotes, list):
            reason = "invalid_evidence_quotes"

        citation_ids: list[int] = []
        if reason is None:
            try:
                citation_ids = list(dict.fromkeys(int(value) for value in raw_ids))
            except (TypeError, ValueError):
                reason = "non_integer_citation"
            if reason is None and any(
                citation_id < 1 or citation_id > len(references)
                for citation_id in citation_ids
            ):
                reason = "citation_out_of_range"

        scores: dict[int, float] = {}
        support_basis: dict[int, str] = {}
        verified_quotes: list[dict[str, Any]] = []
        if reason is None:
            for quote_item in raw_quotes:
                if not isinstance(quote_item, dict):
                    continue
                try:
                    quote_citation_id = int(quote_item.get("citation_id"))
                except (TypeError, ValueError):
                    continue
                quote = str(quote_item.get("quote") or "").strip()
                if quote_citation_id not in citation_ids or len(quote) < 8:
                    continue
                reference = references[quote_citation_id - 1]
                evidence = str(
                    reference.get("content")
                    or reference.get("content_with_weight")
                    or ""
                )
                if _normalized_quote(quote) in _normalized_quote(evidence):
                    verified_quotes.append({
                        "citation_id": quote_citation_id,
                        "quote": quote[:500],
                    })

            verified_quote_ids = {
                int(item["citation_id"]) for item in verified_quotes
            }
            identifiers = _required_identifiers(text)
            supported_ids: list[int] = []
            for citation_id in citation_ids:
                reference = references[citation_id - 1]
                evidence = str(
                    reference.get("content")
                    or reference.get("content_with_weight")
                    or ""
                )
                score = lexical_support_score(text, evidence)
                scores[citation_id] = round(score, 4)
                evidence_folded = evidence.casefold()
                identifiers_ok = not identifiers or identifiers <= {
                    token.casefold() for token in ASCII_TOKEN_PATTERN.findall(evidence_folded)
                }
                # A verbatim quote proves provenance, but it must never authorize a
                # number or technical identifier that is absent from the evidence.
                if identifiers_ok and score >= threshold:
                    supported_ids.append(citation_id)
                    support_basis[citation_id] = "lexical_support"
                elif identifiers_ok and citation_id in verified_quote_ids:
                    supported_ids.append(citation_id)
                    support_basis[citation_id] = "verbatim_quote_provenance"
            if not supported_ids:
                reason = "insufficient_lexical_support"
            else:
                citation_ids = supported_ids

        if reason is not None:
            rejected.append({
                "claim_index": index,
                "reason": reason,
                "support_scores": scores,
                "verified_quote_count": len(verified_quotes),
            })
            continue
        provenance_only = any(
            support_basis.get(citation_id) == "verbatim_quote_provenance"
            for citation_id in citation_ids
        )
        accepted.append({
            "text": text.rstrip("。.!? "),
            "citation_ids": citation_ids,
            "uncertainty": "limited" if provenance_only else uncertainty,
            "proposed_uncertainty": uncertainty,
            "support_scores": scores,
            "support_basis": support_basis,
            "provenance_only": provenance_only,
            "semantic_entailment_verified": False,
            "verified_evidence_quotes": verified_quotes,
        })

    return {
        "requested_status": payload.get("answer_status"),
        "status": "grounded" if accepted else "insufficient",
        "accepted_claims": accepted,
        "rejected_claims": rejected,
        "candidate_claim_count": len(candidates),
        "accepted_claim_count": len(accepted),
        "rejected_claim_count": len(rejected),
        "minimum_support_score": threshold,
        "verified_quote_count": sum(
            len(claim["verified_evidence_quotes"]) for claim in accepted
        ),
        "semantic_entailment_verification": "not_performed",
        "limitations": payload.get("limitations", []),
    }


def build_semantic_entailment_cases(
    validation: dict[str, Any],
    references: list[dict[str, Any]],
    *,
    max_evidence_chars: int = 2400,
) -> list[dict[str, Any]]:
    """Build bounded, auditable claim/evidence inputs for a semantic judge."""
    evidence_limit = max(200, int(max_evidence_chars))
    cases: list[dict[str, Any]] = []
    for claim_index, claim in enumerate(validation.get("accepted_claims") or []):
        quotes_by_id: dict[int, list[str]] = {}
        for quote_item in claim.get("verified_evidence_quotes") or []:
            citation_id = int(quote_item["citation_id"])
            quotes_by_id.setdefault(citation_id, []).append(str(quote_item["quote"]))

        evidence_items: list[dict[str, Any]] = []
        for citation_id in claim.get("citation_ids") or []:
            if not 1 <= int(citation_id) <= len(references):
                continue
            reference = references[int(citation_id) - 1]
            verified_quotes = quotes_by_id.get(int(citation_id), [])
            evidence = "\n".join(verified_quotes) if verified_quotes else str(
                reference.get("content")
                or reference.get("content_with_weight")
                or ""
            )
            evidence_items.append({
                "citation_id": int(citation_id),
                "evidence": evidence[:evidence_limit],
            })
        cases.append({
            "claim_index": claim_index,
            "claim": claim.get("text", ""),
            "evidence": evidence_items,
        })
    return cases


def parse_semantic_entailment_response(
    raw: str,
    *,
    expected_claim_count: int,
) -> list[dict[str, Any]]:
    """Parse a complete one-verdict-per-claim response from the semantic judge."""
    payload = _extract_json_object(raw)
    judgments = payload.get("judgments")
    if not isinstance(judgments, list):
        raise GroundingValidationError("semantic judgments 必须是数组")

    normalized: list[dict[str, Any]] = []
    seen: set[int] = set()
    for item in judgments:
        if not isinstance(item, dict):
            raise GroundingValidationError("semantic judgment 必须是对象")
        try:
            claim_index = int(item.get("claim_index"))
        except (TypeError, ValueError) as exc:
            raise GroundingValidationError("semantic claim_index 必须是整数") from exc
        verdict = str(item.get("verdict") or "").strip().lower()
        if verdict not in ENTAILMENT_VERDICTS:
            raise GroundingValidationError("semantic verdict 非法")
        if claim_index < 0 or claim_index >= expected_claim_count:
            raise GroundingValidationError("semantic claim_index 越界")
        if claim_index in seen:
            raise GroundingValidationError("semantic claim_index 重复")
        seen.add(claim_index)
        normalized.append({
            "claim_index": claim_index,
            "verdict": verdict,
            "reason": str(item.get("reason") or "").strip()[:500],
        })

    if seen != set(range(expected_claim_count)):
        raise GroundingValidationError("semantic judgments 未完整覆盖所有 claim")
    return sorted(normalized, key=lambda item: item["claim_index"])


def apply_semantic_entailment_judgments(
    validation: dict[str, Any],
    judgments: list[dict[str, Any]],
    *,
    verifier: dict[str, Any],
) -> dict[str, Any]:
    """Retain only claims judged entailed and expose the judge as audit metadata."""
    result = dict(validation)
    prior_accepted = list(validation.get("accepted_claims") or [])
    by_index = {int(item["claim_index"]): item for item in judgments}
    if set(by_index) != set(range(len(prior_accepted))):
        raise GroundingValidationError("semantic judgments 与 accepted claims 不一致")

    accepted: list[dict[str, Any]] = []
    semantic_rejected: list[dict[str, Any]] = []
    for claim_index, claim in enumerate(prior_accepted):
        judgment = by_index[claim_index]
        audited_claim = dict(claim)
        audited_claim["semantic_entailment"] = judgment
        if judgment["verdict"] == "entailed":
            audited_claim["semantic_entailment_verified"] = True
            accepted.append(audited_claim)
        else:
            semantic_rejected.append({
                "claim_index": claim_index,
                "reason": f"semantic_{judgment['verdict']}",
                "semantic_entailment": judgment,
                "claim_text": claim.get("text", ""),
            })

    rejected = list(validation.get("rejected_claims") or []) + semantic_rejected
    result.update({
        "status": "grounded" if accepted else "insufficient",
        "accepted_claims": accepted,
        "rejected_claims": rejected,
        "accepted_claim_count": len(accepted),
        "rejected_claim_count": len(rejected),
        "semantic_entailment_verification": "llm_judge_performed",
        "semantic_entailment_verified_count": len(accepted),
        "semantic_entailment_rejected_count": len(semantic_rejected),
        "semantic_verifier": verifier,
    })
    return result


def fail_closed_semantic_entailment(
    validation: dict[str, Any],
    *,
    verifier: dict[str, Any],
    error: str,
) -> dict[str, Any]:
    """Reject all pre-screened claims when the semantic judge cannot be trusted."""
    result = dict(validation)
    prior_accepted = list(validation.get("accepted_claims") or [])
    rejected = list(validation.get("rejected_claims") or [])
    rejected.extend({
        "claim_index": claim_index,
        "reason": "semantic_verifier_error",
        "claim_text": claim.get("text", ""),
    } for claim_index, claim in enumerate(prior_accepted))
    result.update({
        "status": "insufficient",
        "accepted_claims": [],
        "rejected_claims": rejected,
        "accepted_claim_count": 0,
        "rejected_claim_count": len(rejected),
        "semantic_entailment_verification": "llm_judge_failed_closed",
        "semantic_entailment_verified_count": 0,
        "semantic_entailment_rejected_count": len(prior_accepted),
        "semantic_verifier": verifier,
        "semantic_verifier_error": str(error)[:500],
    })
    return result


def render_validated_answer(validation: dict[str, Any]) -> str:
    claims = validation.get("accepted_claims") or []
    if not claims:
        return (
            "当前候选回答未通过逐论断证据校验，无法基于可追溯证据给出结论。"
            "请补充资料或缩小问题范围后重试。"
        )
    rendered = []
    for claim in claims:
        citations = "".join(f"[[{value}]]" for value in claim["citation_ids"])
        uncertainty = "根据当前证据，" if claim["uncertainty"] == "limited" else ""
        rendered.append(f"- {uncertainty}{claim['text']}。{citations}")
    if validation.get("rejected_claim_count"):
        rendered.append("\n> 部分候选论断因未通过证据支持校验而未展示。")
    return "\n".join(rendered)
