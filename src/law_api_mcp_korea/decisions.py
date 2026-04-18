"""통합 판례·결정례 도메인 매핑 및 헬퍼."""
from __future__ import annotations

from typing import Any

DECISION_DOMAINS: dict[str, dict[str, Any]] = {
    "prec":  {"name": "대법원 판례",       "list": "precListGuide",            "info": "precInfoGuide"},
    "detc":  {"name": "헌법재판소 결정례",  "list": "detcListGuide",            "info": "detcInfoGuide"},
    "decc":  {"name": "행정심판례",         "list": "deccListGuide",            "info": "deccInfoGuide"},
    "expc":  {"name": "법령해석례",         "list": "expcListGuide",            "info": "expcInfoGuide"},
    "tt":    {"name": "조세심판원",         "list": "specialDeccTtListGuide",   "info": "specialDeccTtInfoGuide"},
    "kmst":  {"name": "해양안전심판원",     "list": "specialDeccKmstListGuide", "info": "specialDeccKmstInfoGuide"},
    "nlrc":  {"name": "노동위원회",         "list": "nlrcListGuide",            "info": "nlrcInfoGuide"},
    "acr":   {"name": "국민권익위원회",     "list": "specialDeccAcrListGuide",  "info": "specialDeccAcrInfoGuide"},
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
