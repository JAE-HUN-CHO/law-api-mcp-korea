from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from law_api_mcp_korea.client import LawOpenApiClient  # noqa: E402
from law_api_mcp_korea.official_guides import (  # noqa: E402
    load_official_guides_snapshot,
    normalize_url,
    official_html_names_for_api,
    semantic_url_equal,
)
from tools.sync_api_docs import nested_doc_to_flat_filename, source_markdown_files  # noqa: E402

CATALOG_PATH = ROOT / "src" / "law_api_mcp_korea" / "api_docs" / "catalog.json"
URL_RE = re.compile(r"https?://[^\s)>\"]+")


def _sample_urls_from_markdown(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [
        match.group(0)
        for match in URL_RE.finditer(text)
        if "/DRF/" in match.group(0) and "OC=" in match.group(0)
    ]


def _official_sample_urls_for_api(api: dict[str, object], snapshot: dict[str, object]) -> list[str]:
    official_by_name = {
        guide["official_html_name"]: guide
        for guide in snapshot.get("official_guides", [])
    }
    html_names, _ = official_html_names_for_api(api, snapshot)
    urls: list[str] = []
    for html_name in html_names:
        guide = official_by_name.get(html_name)
        if not guide:
            continue
        urls.extend(list(guide.get("sample_urls", [])))
    return urls


def _infer_response_type(api: dict[str, Any], query_pairs: list[tuple[str, str]]) -> str:
    query = dict(query_pairs)
    explicit = str(query.get("type") or "").upper().strip()
    if explicit:
        return explicit

    target = str(query.get("target") or "")
    mobile_yn = str(query.get("mobileYn") or "")
    for variant in api.get("sample_variants", []) or []:
        if str(variant.get("target") or "") != target:
            continue
        if str(variant.get("mobileYn") or "") != mobile_yn:
            continue
        response_types = [str(value).upper() for value in variant.get("response_types", []) or [] if str(value).strip()]
        if response_types:
            return response_types[0]

    supported = [str(value).upper() for value in api.get("supported_types", []) or [] if str(value).strip()]
    if supported:
        return supported[0]
    return "JSON"


def _comparison_official_url(api: dict[str, Any], official_url: str, response_type: str) -> str:
    parsed = urlparse(official_url)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = dict(query_pairs)
    if "type" not in query:
        query_pairs.append(("type", response_type))

    fixed_params = {str(key): str(value) for key, value in dict(api.get("default_params", {})).items()}
    present_keys = {key for key, _ in query_pairs}
    for key, value in fixed_params.items():
        if key in {"OC", "type"}:
            continue
        if key not in present_keys:
            query_pairs.append((key, value))

    normalized_query = urlencode(query_pairs, doseq=True)
    return parsed._replace(query=normalized_query).geturl()


def build_audit_report() -> dict[str, object]:
    snapshot = load_official_guides_snapshot()
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    client = LawOpenApiClient(oc="test")
    by_filename = {api["filename"]: api for api in catalog["apis"]}

    source_mismatches: list[dict[str, object]] = []
    semantic_mismatches: list[dict[str, object]] = []
    string_only_differences: list[dict[str, object]] = []
    runtime_build_errors: list[dict[str, object]] = []

    for source_path in source_markdown_files(ROOT / "api" / "docs"):
        filename = nested_doc_to_flat_filename(source_path, ROOT / "api" / "docs")
        api = by_filename[filename]
        source_urls = _sample_urls_from_markdown(source_path)
        official_urls = _official_sample_urls_for_api(api, snapshot)
        if source_urls != official_urls:
            source_mismatches.append(
                {
                    "title": api["title"],
                    "filename": filename,
                    "source_urls": source_urls,
                    "official_urls": official_urls,
                }
            )

        for official_url in official_urls:
            query_pairs = parse_qsl(urlparse(official_url).query, keep_blank_values=True)
            params = {key: value for key, value in query_pairs if key not in {"OC", "type"}}
            response_type = _infer_response_type(api, query_pairs)
            comparable_official_url = _comparison_official_url(api, official_url, response_type)
            try:
                built_url = client.build_url(api["title"], params=params, response_type=response_type, oc="test")
            except Exception as exc:
                runtime_build_errors.append(
                    {
                        "title": api["title"],
                        "official_url": official_url,
                        "response_type": response_type,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                continue
            if not semantic_url_equal(comparable_official_url, built_url):
                semantic_mismatches.append(
                    {
                        "title": api["title"],
                        "official_url": official_url,
                        "comparison_official_url": comparable_official_url,
                        "built_url": built_url,
                        "official_normalized": normalize_url(comparable_official_url).__dict__,
                        "built_normalized": normalize_url(built_url).__dict__,
                    }
                )
            elif comparable_official_url != built_url:
                string_only_differences.append(
                    {
                        "title": api["title"],
                        "official_url": official_url,
                        "comparison_official_url": comparable_official_url,
                        "built_url": built_url,
                    }
                )

    return {
        "guide_list_displayed_count": snapshot.get("guide_list_displayed_count"),
        "official_list_item_count": snapshot.get("official_list_item_count"),
        "official_guide_count": snapshot.get("official_guide_count"),
        "catalog_count": catalog.get("count"),
        "guide_list_display_gap": (
            int(snapshot["official_list_item_count"]) - int(snapshot["guide_list_displayed_count"])
            if snapshot.get("guide_list_displayed_count") is not None
            else None
        ),
        "source_mismatches": source_mismatches,
        "semantic_mismatches": semantic_mismatches,
        "string_only_differences": string_only_differences,
        "runtime_build_errors": runtime_build_errors,
    }


def main(argv: list[str] | None = None) -> int:
    _ = argv
    report = build_audit_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
