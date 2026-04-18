from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from typing import Any

DOCS_PACKAGE = "law_api_mcp_korea.api_docs"
SUMMARY_FIELDS = (
    "index",
    "slug",
    "doc_key",
    "guide_html_name",
    "official_html_name",
    "official_html_names",
    "official_guide_url",
    "official_source",
    "official_list_titles",
    "title",
    "family",
    "filename",
    "guide_url",
    "endpoint",
    "supported_types",
    "sample_variants",
    "target_variants",
    "description",
    "evidence",
)
DETAIL_FIELDS = (
    "index",
    "slug",
    "doc_key",
    "guide_html_name",
    "official_html_name",
    "official_html_names",
    "official_guide_url",
    "official_source",
    "official_list_titles",
    "title",
    "family",
    "filename",
    "guide_url",
    "endpoint",
    "supported_types",
    "description",
    "request_params",
    "response_fields",
    "notes",
    "sample_requests",
    "sample_responses",
    "sample_variants",
    "target_variants",
    "evidence",
)


class CatalogResolutionError(LookupError):
    def __init__(self, message: str, candidates: list[str] | None = None) -> None:
        super().__init__(message)
        self.candidates = candidates or []


def _docs_root():
    return resources.files(DOCS_PACKAGE)


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    with _docs_root().joinpath("catalog.json").open("r", encoding="utf-8") as fp:
        return json.load(fp)


@lru_cache(maxsize=1)
def load_catalog_index() -> dict[str, Any]:
    with _docs_root().joinpath("catalog_index.json").open("r", encoding="utf-8") as fp:
        return json.load(fp)


def metadata() -> dict[str, Any]:
    data = load_catalog_index()
    return {
        "generated_at": data.get("generated_at"),
        "count": data.get("count"),
        "families": data.get("families", {}),
        "guide_list_displayed_count": data.get("guide_list_displayed_count"),
        "official_list_item_count": data.get("official_list_item_count"),
        "official_guide_count": data.get("official_guide_count"),
    }


def all_apis() -> list[dict[str, Any]]:
    return list(load_catalog_index().get("apis", []))


def normalize_text(value: str | None) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value or "").lower()


def search_apis(keyword: str = "", family: str = "", limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    keyword_norm = normalize_text(keyword)
    items: list[dict[str, Any]] = []
    for api in all_apis():
        if family and api.get("family") != family:
            continue
        if keyword_norm:
            haystack = " ".join(
                [
                    str(api.get("slug", "")),
                    str(api.get("guide_html_name", "")),
                    str(api.get("official_html_name", "")),
                    str(api.get("title", "")),
                    str(api.get("filename", "")),
                    str(api.get("stem", "")),
                    str(api.get("description", "")),
                    " ".join(str(v) for v in api.get("official_list_titles", [])),
                    " ".join(p.get("name", "") for p in api.get("request_params", [])),
                ]
            )
            if keyword_norm not in normalize_text(haystack):
                continue
        items.append(api)
    items.sort(key=lambda item: item.get("index", 0))
    start = max(0, offset)
    end = start + max(1, limit)
    return items[start:end]


def _candidate_strings(api: dict[str, Any]) -> list[str]:
    return [
        str(api.get("slug") or ""),
        str(api.get("doc_key") or ""),
        str(api.get("guide_html_name") or ""),
        str(api.get("official_html_name") or ""),
        str(api.get("title") or ""),
        str(api.get("filename") or ""),
        str(api.get("stem") or ""),
        *(str(value) for value in api.get("official_html_names", []) or []),
        *(str(value) for value in api.get("official_list_titles", []) or []),
    ]


def _doc_key(api: dict[str, Any]) -> str:
    return str(api.get("doc_key") or api.get("slug") or api.get("guide_html_name"))


def resolve_api(api_name: str) -> dict[str, Any]:
    query = (api_name or "").strip()
    if not query:
        raise CatalogResolutionError("API 이름이 비어 있습니다.")

    items = all_apis()

    for getter in (
        lambda a: str(a.get("slug") or ""),
        lambda a: str(a.get("guide_html_name") or ""),
        lambda a: str(a.get("title") or ""),
        lambda a: str(a.get("filename") or ""),
        lambda a: str(a.get("stem") or ""),
    ):
        exact = [api for api in items if getter(api) == query]
        if len(exact) == 1:
            return exact[0]

    query_norm = normalize_text(query)
    normalized_exact = []
    for api in items:
        if any(normalize_text(candidate) == query_norm for candidate in _candidate_strings(api)):
            normalized_exact.append(api)
    if len(normalized_exact) == 1:
        return normalized_exact[0]
    if len(normalized_exact) > 1:
        raise CatalogResolutionError(
            f"API 식별자가 모호합니다: {query}",
            candidates=[api["title"] for api in normalized_exact[:10]],
        )

    contains = []
    for api in items:
        haystack = " ".join(_candidate_strings(api))
        if query_norm and query_norm in normalize_text(haystack):
            contains.append(api)
    if len(contains) == 1:
        return contains[0]
    if contains:
        raise CatalogResolutionError(
            f"API 식별자가 모호합니다: {query}",
            candidates=[api["title"] for api in contains[:10]],
        )

    raise CatalogResolutionError(f"API를 찾을 수 없습니다: {query}")


def _constraint_notes(api: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    target = str(dict(api.get("default_params", {})).get("target") or "").strip()
    title = str(api.get("title") or "")
    if title == "법령 연혁 본문 조회" or target == "lsHistory":
        notes.append("법령 연혁 본문 조회는 현재 lsHistory target의 HTML 형식만 안정적으로 지원합니다.")
    if target == "baiPvcs":
        notes.append("감사원 사전컨설팅 의견서 API는 현재 `유효한 API key가 아닙니다` 스타일 오류로 표준화됩니다.")
    return notes


@lru_cache(maxsize=None)
def _load_api_meta(guide_html_name: str) -> dict[str, Any]:
    with _docs_root().joinpath("api_meta").joinpath(f"{guide_html_name}.json").open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _merge_notes(*note_groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in note_groups:
        for note in group:
            text = str(note).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
    return merged


def get_api_detail(api_name: str | dict[str, Any]) -> dict[str, Any]:
    api = resolve_api(api_name) if isinstance(api_name, str) else dict(api_name)
    detail = dict(_load_api_meta(_doc_key(api)))
    merged = dict(api)
    merged.update(detail)
    merged["notes"] = _merge_notes(
        list(detail.get("notes", [])),
        _constraint_notes(merged),
    )
    return merged


def get_doc_markdown(api_name: str) -> str:
    api = resolve_api(api_name)
    with _docs_root().joinpath(api["filename"]).open("r", encoding="utf-8") as fp:
        return fp.read()


def summarize_api(api: dict[str, Any], view: str = "detail") -> dict[str, Any]:
    if view == "summary":
        return {field: api.get(field) for field in SUMMARY_FIELDS}
    if view != "detail":
        raise ValueError(f"지원하지 않는 API view입니다: {view}")

    detailed = api if "response_fields" in api or "sample_requests" in api or "notes" in api else get_api_detail(api)
    payload = {field: detailed.get(field) for field in DETAIL_FIELDS}
    payload["notes"] = _merge_notes(list(payload.get("notes", []) or []), _constraint_notes(detailed))
    return payload


def get_api_doc_payload(api_name: str, view: str = "summary", include_markdown: bool = False) -> dict[str, Any]:
    if view not in {"summary", "detail", "markdown"}:
        raise ValueError(f"지원하지 않는 API view입니다: {view}")

    summary = summarize_api(resolve_api(api_name), view="summary")
    if view == "summary":
        payload: dict[str, Any] = {"api": summary}
    elif view == "detail":
        payload = {"api": summarize_api(get_api_detail(api_name), view="detail")}
    else:
        payload = {"api": summary, "markdown": get_doc_markdown(api_name)}

    if include_markdown and view != "markdown":
        payload["markdown"] = get_doc_markdown(api_name)
    return payload


def catalog_json() -> str:
    with _docs_root().joinpath("catalog.json").open("r", encoding="utf-8") as fp:
        return fp.read()


def catalog_index_json() -> str:
    with _docs_root().joinpath("catalog_index.json").open("r", encoding="utf-8") as fp:
        return fp.read()


def manifest_json() -> str:
    with _docs_root().joinpath("manifest.json").open("r", encoding="utf-8") as fp:
        return fp.read()


def manifest_summary() -> dict[str, Any]:
    data = load_catalog_index()
    return {
        "count": data.get("count"),
        "items": [
            {
                "title": api.get("title"),
                "family": api.get("family"),
                "filename": api.get("filename"),
                "guide_url": api.get("guide_url"),
                "endpoint": api.get("endpoint"),
            }
            for api in data.get("apis", [])
        ],
    }


def verification_json() -> str:
    with _docs_root().joinpath("verification.json").open("r", encoding="utf-8") as fp:
        return fp.read()


def verification_summary() -> dict[str, Any]:
    return json.loads(verification_json())


def verification_report() -> str:
    with _docs_root().joinpath("verification_report.md").open("r", encoding="utf-8") as fp:
        return fp.read()
