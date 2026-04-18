"""법령 인용 파서 및 AI 환각 검증 유틸리티."""
from __future__ import annotations

import re
from typing import Any

from .aliases import HALLUCINATION_MARKER, resolve_alias

VERIFIED_MARKER = "[VERIFIED]"
SKIPPED_MARKER = "[SKIPPED]"
ERROR_MARKER = "[ERROR]"

_MARKER_MAP: dict[str, str] = {
    "verified": VERIFIED_MARKER,
    "not_found": HALLUCINATION_MARKER,
    "skipped": SKIPPED_MARKER,
    "error": ERROR_MARKER,
}

# 한국 법령 조문 인용 패턴
# 예: "민법 제750조", "산업안전보건법 제38조의2", "화관법 제12조제3항"
_CITATION_RE = re.compile(
    r"([\w가-힣·]{1,30}법[\w가-힣]*)"  # 법령명 (공백 불포함, '법' 포함)
    r"\s*제\s*(\d+)\s*조"               # 제N조
    r"(?:의\s*(\d+))?"                   # 의N (선택)
    r"(?:\s*제\s*(\d+)\s*항)?"          # 제N항 (선택)
)


def extract_citations(text: str) -> list[dict[str, Any]]:
    """텍스트에서 법령 조문 인용을 추출한다. 중복 제거 후 반환."""
    seen: set[tuple[str, int]] = set()
    results: list[dict[str, Any]] = []

    for m in _CITATION_RE.finditer(text):
        law_name = m.group(1).strip()
        article = int(m.group(2))
        sub_article = int(m.group(3)) if m.group(3) else None
        clause = int(m.group(4)) if m.group(4) else None
        key = (law_name, article)
        if key in seen:
            continue
        seen.add(key)
        law_name_resolved = resolve_alias(law_name)
        raw = m.group(0).strip()
        results.append({
            "raw": raw,
            "law_name": law_name,
            "law_name_resolved": law_name_resolved,
            "article": article,
            "sub_article": sub_article,
            "clause": clause,
        })
    return results


def build_citation_result(
    *,
    raw: str,
    law_name: str,
    law_name_resolved: str,
    article: int,
    status: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """단일 인용 검증 결과 dict를 생성한다.

    status: "verified" → [VERIFIED], "not_found" → [HALLUCINATION_DETECTED],
            "skipped" → [SKIPPED], "error" → [ERROR]
    """
    marker = _MARKER_MAP.get(status, HALLUCINATION_MARKER)
    return {
        "raw": raw,
        "law_name": law_name,
        "law_name_resolved": law_name_resolved,
        "article": article,
        "status": status,
        "marker": marker,
        "detail": detail or {},
    }
