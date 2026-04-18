"""통합 판례·결정례 도메인 매핑 및 헬퍼."""
from __future__ import annotations

from typing import Any

DECISION_DOMAINS: dict[str, dict[str, Any]] = {
    "prec":  {"name": "대법원 판례",       "list": "precListGuide",            "info": "precInfoGuide",            "search_key": "PrecSearch",            "item_key": "prec"},
    "detc":  {"name": "헌법재판소 결정례",  "list": "detcListGuide",            "info": "detcInfoGuide",            "search_key": "DetcSearch",            "item_key": "detc"},
    "decc":  {"name": "행정심판례",         "list": "deccListGuide",            "info": "deccInfoGuide",            "search_key": "DeccSearch",            "item_key": "decc"},
    "expc":  {"name": "법령해석례",         "list": "expcListGuide",            "info": "expcInfoGuide",            "search_key": "ExpcSearch",            "item_key": "expc"},
    "tt":    {"name": "조세심판원",         "list": "specialDeccTtListGuide",   "info": "specialDeccTtInfoGuide",   "search_key": "TtSpecialDeccSearch",   "item_key": "ttSpecialDecc"},
    "kmst":  {"name": "해양안전심판원",     "list": "specialDeccKmstListGuide", "info": "specialDeccKmstInfoGuide", "search_key": "KmstSpecialDeccSearch", "item_key": "kmstSpecialDecc"},
    "nlrc":  {"name": "노동위원회",         "list": "nlrcListGuide",            "info": "nlrcInfoGuide",            "search_key": "NlrcSearch",            "item_key": "nlrc"},
    "acr":   {"name": "국민권익위원회",     "list": "specialDeccAcrListGuide",  "info": "specialDeccAcrInfoGuide",  "search_key": "AcrSpecialDeccSearch",  "item_key": "acrSpecialDecc"},
    "moleg": {"name": "법제처 법령해석",    "list": None,                       "info": None},
}

DOMAIN_ALIASES: dict[str, str] = {
    "판례": "prec",  "대법원": "prec",
    "헌재": "detc",  "헌법재판소": "detc",
    "행심": "decc",  "행정심판": "decc",
    "법령해석": "expc", "유권해석": "expc",
    "조심": "tt",   "조세심판": "tt",
    "해심": "kmst",  "해양심판": "kmst",
    "노위": "nlrc",  "노동위원회": "nlrc",
    "권익위": "acr", "국민권익위": "acr",
    "법제처": "moleg",
}


def resolve_domain(domain: str) -> str | None:
    """도메인 코드 또는 한국어 약어를 정규 도메인 코드로 변환. 없으면 None."""
    if domain in DECISION_DOMAINS:
        return domain
    return DOMAIN_ALIASES.get(domain)


def get_list_slug(domain_code: str) -> str | None:
    """도메인 코드에 해당하는 목록 조회 API slug 반환."""
    spec = DECISION_DOMAINS.get(domain_code)
    return spec["list"] if spec else None


def get_info_slug(domain_code: str) -> str | None:
    """도메인 코드에 해당하는 본문 조회 API slug 반환."""
    spec = DECISION_DOMAINS.get(domain_code)
    return spec["info"] if spec else None


def domain_name(domain_code: str) -> str:
    """도메인 코드의 한글 이름 반환."""
    spec = DECISION_DOMAINS.get(domain_code)
    return spec["name"] if spec else domain_code


def get_item_from_response(domain_code: str, data: dict[str, Any]) -> list[Any]:
    """API 응답 dict에서 도메인별 결과 목록을 추출한다.

    각 도메인의 search_key/item_key를 사용하여 응답 구조에서 아이템을 꺼낸다.
    결과가 dict이면 리스트로 감싸서 반환. 키가 없으면 빈 리스트.
    """
    spec = DECISION_DOMAINS.get(domain_code)
    if not spec or "search_key" not in spec:
        return []
    items = data.get(spec["search_key"], {}).get(spec["item_key"])
    if items is None:
        return []
    if isinstance(items, dict):
        return [items]
    return list(items)
