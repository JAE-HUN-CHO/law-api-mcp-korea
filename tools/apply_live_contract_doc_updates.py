from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.sync_api_docs import sync_docs  # noqa: E402
from tools.sync_source_docs_from_official import sync_source_docs_from_official  # noqa: E402

CATALOG_PATH = ROOT / "src" / "law_api_mcp_korea" / "api_docs" / "catalog.json"
REPORT_PATH = ROOT / "reports" / "live_contract_validation.json"
NORMALIZE_RE = re.compile(r"[^0-9A-Za-z가-힣]+")

REQUEST_PARAM_ADDITIONS: dict[str, list[dict[str, object]]] = {
    "조약 목록 조회": [
        {
            "name": "ID",
            "type_info": "char",
            "required": False,
            "description": "조약 ID",
        }
    ],
    "모바일 조약 목록 조회": [
        {
            "name": "ID",
            "type_info": "char",
            "required": False,
            "description": "조약 ID",
        }
    ],
    "모바일 조약 본문 조회": [
        {
            "name": "type",
            "type_info": "string",
            "required": False,
            "description": "출력 형태 : HTML",
        }
    ],
    "모바일 판례 본문 조회": [
        {
            "name": "mobileYn",
            "type_info": "char : Y (필수)",
            "required": True,
            "description": "모바일여부",
        }
    ],
    "모바일 헌재결정례 본문 조회": [
        {
            "name": "mobileYn",
            "type_info": "char : Y (필수)",
            "required": True,
            "description": "모바일여부",
        }
    ],
}
REQUEST_PARAM_REPLACEMENTS: dict[str, dict[str, list[dict[str, object]]]] = {
    "삭제 데이터 목록 조회": {
        "frmDt toDt": [
            {
                "name": "frmDt",
                "type_info": "int",
                "required": False,
                "description": "데이터 삭제 시작 일자 검색 (YYYYMMDD)",
            },
            {
                "name": "toDt",
                "type_info": "int",
                "required": False,
                "description": "데이터 삭제 종료 일자 검색 (YYYYMMDD)",
            },
        ]
    },
    "맞춤형 법령 조문 목록 조회": {
        "lj=jo": [
            {
                "name": "lj",
                "type_info": "string(필수)",
                "required": True,
                "description": "조문여부 (jo 고정)",
            }
        ]
    },
    "맞춤형 행정규칙 조문 목록 조회": {
        "lj=jo": [
            {
                "name": "lj",
                "type_info": "string(필수)",
                "required": True,
                "description": "조문여부 (jo 고정)",
            }
        ]
    },
    "맞춤형 자치법규 조문 목록 조회": {
        "lj=jo": [
            {
                "name": "lj",
                "type_info": "string(필수)",
                "required": True,
                "description": "조문여부 (jo 고정)",
            }
        ]
    },
}
SAMPLE_QUERY_KEY_REMOVALS: dict[str, list[str]] = {
    "자치법규 본문 조회": ["mobileYn"],
}
COMMON_RESPONSE_FIELDS = {"resultcode", "resultmsg", "numofrows", "content"}


def _normalize_name(value: str | None) -> str:
    return NORMALIZE_RE.sub("", value or "").lower()


def _clone_row(row: dict[str, object]) -> dict[str, object]:
    return {
        "name": str(row.get("name", "")),
        "type_info": str(row.get("type_info", "")),
        "required": bool(row.get("required", False)),
        "description": str(row.get("description", "")),
    }


def _load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _load_report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def _response_field_prototypes(catalog: dict) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    exact: dict[str, dict[str, str]] = {}
    normalized: dict[str, dict[str, str]] = {}
    for api in catalog.get("apis", []):
        for field in api.get("response_fields", []) or []:
            name = str(field.get("name") or "")
            if not name:
                continue
            payload = {
                "name": name,
                "type_info": str(field.get("type_info") or ""),
                "description": str(field.get("description") or ""),
            }
            exact.setdefault(name, payload)
            normalized.setdefault(_normalize_name(name), payload)
    return exact, normalized


def _ensure_request_additions(api: dict) -> None:
    rows = list(api.get("request_params", []) or [])
    existing = {str(row.get("name") or "") for row in rows}

    replacements = REQUEST_PARAM_REPLACEMENTS.get(str(api.get("title") or ""), {})
    if replacements:
        updated: list[dict[str, object]] = []
        for row in rows:
            name = str(row.get("name") or "")
            if name in replacements:
                for replacement in replacements[name]:
                    updated.append(_clone_row(replacement))
                continue
            updated.append(row)
        rows = updated
        existing = {str(row.get("name") or "") for row in rows}

    for addition in REQUEST_PARAM_ADDITIONS.get(str(api.get("title") or ""), []):
        name = str(addition["name"])
        if name not in existing:
            rows.append(_clone_row(addition))
            existing.add(name)

    api["request_params"] = rows


def _strip_sample_query_keys(api: dict) -> None:
    keys = SAMPLE_QUERY_KEY_REMOVALS.get(str(api.get("title") or ""), [])
    if not keys:
        return

    def strip_url(url: str) -> str:
        parsed = urlparse(url)
        pairs = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key not in keys
        ]
        return urlunparse(parsed._replace(query=urlencode(pairs)))

    api["sample_requests"] = [strip_url(str(url)) for url in api.get("sample_requests", []) or []]
    for variant in api.get("sample_variants", []) or []:
        variant["urls"] = [strip_url(str(url)) for url in variant.get("urls", []) or []]


def _response_row_from_field(
    field_name: str,
    exact_prototypes: dict[str, dict[str, str]],
    normalized_prototypes: dict[str, dict[str, str]],
) -> dict[str, str]:
    if field_name in exact_prototypes:
        prototype = exact_prototypes[field_name]
        return dict(prototype)

    normalized = _normalize_name(field_name)
    if normalized in normalized_prototypes:
        prototype = normalized_prototypes[normalized]
        return {
            "name": field_name,
            "type_info": prototype.get("type_info", ""),
            "description": prototype.get("description", "") or f"{field_name}",
        }

    return {
        "name": field_name,
        "type_info": "string",
        "description": f"{field_name}",
    }


def _ensure_response_additions(api: dict, entry: dict, exact_prototypes: dict[str, dict[str, str]], normalized_prototypes: dict[str, dict[str, str]]) -> None:
    validation = entry.get("response_validation") or {}
    if validation.get("field_validation_skipped"):
        return

    rows = list(api.get("response_fields", []) or [])
    existing = {str(row.get("name") or "") for row in rows}

    target_fields = [
        str(name)
        for name in validation.get("observed_doc_gap_fields", []) or []
        if _normalize_name(str(name)) not in COMMON_RESPONSE_FIELDS
    ]
    for field_name in target_fields:
        if field_name in existing:
            continue
        rows.append(_response_row_from_field(field_name, exact_prototypes, normalized_prototypes))
        existing.add(field_name)

    api["response_fields"] = rows


def apply_live_contract_doc_updates() -> dict[str, int]:
    catalog = _load_catalog()
    report = _load_report()
    exact_prototypes, normalized_prototypes = _response_field_prototypes(catalog)
    by_title = {str(api.get("title") or ""): api for api in catalog.get("apis", [])}

    request_touched = 0
    response_touched = 0
    sample_touched = 0
    for entry in report.get("entries", []):
        title = str(entry.get("title") or "")
        api = by_title.get(title)
        if api is None:
            continue

        before_request = json.dumps(api.get("request_params", []), ensure_ascii=False, sort_keys=True)
        before_samples = json.dumps(
            {
                "sample_requests": api.get("sample_requests", []),
                "sample_variants": api.get("sample_variants", []),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        before_response = json.dumps(api.get("response_fields", []), ensure_ascii=False, sort_keys=True)

        _ensure_request_additions(api)
        _strip_sample_query_keys(api)
        _ensure_response_additions(api, entry, exact_prototypes, normalized_prototypes)

        if json.dumps(api.get("request_params", []), ensure_ascii=False, sort_keys=True) != before_request:
            request_touched += 1
        if json.dumps(
            {
                "sample_requests": api.get("sample_requests", []),
                "sample_variants": api.get("sample_variants", []),
            },
            ensure_ascii=False,
            sort_keys=True,
        ) != before_samples:
            sample_touched += 1
        if json.dumps(api.get("response_fields", []), ensure_ascii=False, sort_keys=True) != before_response:
            response_touched += 1

    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sync_source_docs_from_official()
    sync_docs()
    return {
        "request_touched": request_touched,
        "response_touched": response_touched,
        "sample_touched": sample_touched,
    }


def main(argv: list[str] | None = None) -> int:
    _ = argv
    summary = apply_live_contract_doc_updates()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
