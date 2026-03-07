from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from typing import Any

DOCS_PACKAGE = "law_api_mcp_korea.api_docs"


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


def metadata() -> dict[str, Any]:
    data = load_catalog()
    return {
        "generated_at": data.get("generated_at"),
        "count": data.get("count"),
        "families": data.get("families", {}),
    }


def all_apis() -> list[dict[str, Any]]:
    return list(load_catalog().get("apis", []))


def normalize_text(value: str | None) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value or "").lower()


def search_apis(keyword: str = "", family: str = "", limit: int = 50) -> list[dict[str, Any]]:
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
                    str(api.get("title", "")),
                    str(api.get("filename", "")),
                    str(api.get("stem", "")),
                    str(api.get("description", "")),
                    " ".join(p.get("name", "") for p in api.get("request_params", [])),
                ]
            )
            if keyword_norm not in normalize_text(haystack):
                continue
        items.append(api)
    items.sort(key=lambda item: item.get("index", 0))
    return items[: max(1, limit)]


def _candidate_strings(api: dict[str, Any]) -> list[str]:
    return [
        str(api.get("slug") or ""),
        str(api.get("guide_html_name") or ""),
        str(api.get("title") or ""),
        str(api.get("filename") or ""),
        str(api.get("stem") or ""),
    ]


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


def get_doc_markdown(api_name: str) -> str:
    api = resolve_api(api_name)
    with _docs_root().joinpath(api["filename"]).open("r", encoding="utf-8") as fp:
        return fp.read()


def summarize_api(api: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": api.get("index"),
        "slug": api.get("slug"),
        "guide_html_name": api.get("guide_html_name"),
        "title": api.get("title"),
        "family": api.get("family"),
        "filename": api.get("filename"),
        "guide_url": api.get("guide_url"),
        "endpoint": api.get("endpoint"),
        "supported_types": api.get("supported_types", []),
        "description": api.get("description"),
        "request_params": api.get("request_params", []),
        "response_fields": api.get("response_fields", []),
        "notes": api.get("notes", []),
        "evidence": api.get("evidence"),
    }


def manifest_json() -> str:
    with _docs_root().joinpath("manifest.json").open("r", encoding="utf-8") as fp:
        return fp.read()


def verification_report() -> str:
    with _docs_root().joinpath("verification_report.md").open("r", encoding="utf-8") as fp:
        return fp.read()
