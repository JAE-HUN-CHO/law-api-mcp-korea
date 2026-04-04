from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

import requests

GUIDE_LIST_URL = "https://open.law.go.kr/LSO/openApi/guideList.do"
GUIDE_RESULT_URL = "https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName={html_name}"
SNAPSHOT_PATH = Path(__file__).resolve().parent / "api_docs" / "official_guides_snapshot.json"

LIST_ITEM_RE = re.compile(r"openApiGuide\('([^']+)'\)\">(.*?)</a>", flags=re.S)
DISPLAYED_COUNT_RE = re.compile(r"총\s*([0-9]+)\s*건")
DISPLAYED_COUNT_HTML_RE = re.compile(r"총\s*<span[^>]*>\s*([0-9]+)\s*</span>\s*건", flags=re.S)
REQUEST_URL_RE = re.compile(r"요청 URL\s*:\s*(https?://[^\s<]+)")
TABLE_RE = re.compile(r'<table class="blist guide">(.*?)</table>', flags=re.S)
ROW_RE = re.compile(r"<tr>(.*?)</tr>", flags=re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", flags=re.S)
TITLE_RE = re.compile(r"<h3>\s*(.*?)\s*</h3>", flags=re.S)
SAMPLE_TABLE_RE = re.compile(r'<table class="guide_table">(.*?)</table>', flags=re.S)
SAMPLE_URL_RE = re.compile(r"(https?://[^\s<]+)")

# Current grouped/internal APIs intentionally collapse multiple official guides.
GROUPED_OFFICIAL_HTML_NAMES: dict[str, list[str]] = {
    "위원회 결정문 목록 조회 (공정거래위원회·국민권익위원회·개인정보보호위원회)": [
        "ftcListGuide",
        "acrListGuide",
        "ppcListGuide",
    ],
    "위원회 결정문 본문 조회 (공정거래위원회·국민권익위원회·개인정보보호위원회)": [
        "ftcInfoGuide",
        "acrInfoGuide",
        "ppcInfoGuide",
    ],
}

# Internal docs that do not currently use the official htmlName directly.
TITLE_TO_OFFICIAL_HTML_NAME: dict[str, str] = {
    "위임법령 조회": "lsDelegated",
}


@dataclass(frozen=True)
class NormalizedUrl:
    scheme: str
    netloc: str
    path: str
    query_pairs: tuple[tuple[str, str], ...]


def _strip_tags(value: str) -> str:
    cleaned = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    return html.unescape(cleaned)


def _clean_text(value: str) -> str:
    return " ".join(_strip_tags(value).split())


def _clean_title(value: str) -> str:
    title = _clean_text(value)
    title = re.sub(r"\s+API$", "", title)
    title = re.sub(r"\s*가이드API$", "", title)
    return title.strip()


def _extract_guide_area(page_html: str) -> str:
    marker = '<div class="guide_area">'
    start = page_html.find(marker)
    if start < 0:
        raise ValueError("guide_area 블록을 찾지 못했습니다.")
    start += len(marker)

    end_markers = (
        "<!-- contents",
        '<div id="bottom">',
        '<div class="bottom_wrap">',
    )
    end_positions = [page_html.find(marker, start) for marker in end_markers]
    valid_end_positions = [position for position in end_positions if position >= 0]
    end = min(valid_end_positions) if valid_end_positions else len(page_html)
    return page_html[start:end]


def _parse_table_rows(table_html: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row_html in ROW_RE.findall(table_html):
        cells = [_clean_text(cell) for cell in CELL_RE.findall(row_html)]
        if cells:
            rows.append(cells)
    return rows


def _parse_request_params(table_html: str) -> list[dict[str, Any]]:
    rows = _parse_table_rows(table_html)
    params: list[dict[str, Any]] = []
    for row in rows[1:]:
        if len(row) < 3:
            continue
        name, type_info, description = row[0], row[1], row[2]
        params.append(
            {
                "name": name,
                "type_info": type_info,
                "required": "필수" in type_info,
                "description": description,
            }
        )
    return params


def _parse_response_fields(table_html: str) -> list[dict[str, str]]:
    rows = _parse_table_rows(table_html)
    fields: list[dict[str, str]] = []
    for row in rows[1:]:
        if len(row) < 3:
            continue
        fields.append(
            {
                "name": row[0],
                "type_info": row[1],
                "description": row[2],
            }
        )
    return fields


def _normalize_sample_url(url: str) -> str:
    normalized = html.unescape(url).replace("&amp;", "&").strip()
    normalized = normalized.replace("®Dt=", "&regDt=")
    return normalized


def _extract_sample_urls(guide_html: str) -> list[str]:
    sample_urls: list[str] = []
    match = SAMPLE_TABLE_RE.search(guide_html)
    if not match:
        return sample_urls
    sample_table = match.group(1)
    for row_html in ROW_RE.findall(sample_table):
        if "td_content" not in row_html:
            continue
        text = _clean_text(row_html)
        url_match = SAMPLE_URL_RE.search(text)
        if not url_match:
            continue
        sample_urls.append(_normalize_sample_url(url_match.group(1)))
    return sample_urls


def _supported_types_from_urls(sample_urls: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for url in sample_urls:
        query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
        response_type = (query.get("type") or "").upper()
        if response_type and response_type not in seen:
            seen.add(response_type)
            ordered.append(response_type)
    return ordered


def _dedupe_strings(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _build_sample_variants(sample_urls: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for url in sample_urls:
        query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
        target = query.get("target", "")
        mobile = query.get("mobileYn", "")
        grouped[(target, mobile)].append(url)

    variants: list[dict[str, Any]] = []
    for (target, mobile), urls in grouped.items():
        variants.append(
            {
                "target": target or None,
                "mobileYn": mobile or None,
                "response_types": _supported_types_from_urls(urls),
                "urls": urls,
            }
        )
    variants.sort(key=lambda item: ((item.get("target") or ""), (item.get("mobileYn") or "")))
    return variants


def parse_guide_list(page_html: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for html_name, label_html in LIST_ITEM_RE.findall(page_html):
        title = _clean_text(label_html)
        if not title:
            continue
        if html_name in {"openApiCase", "cuAsk"}:
            continue
        items.append(
            {
                "index": len(items) + 1,
                "official_html_name": html_name,
                "title": title,
                "guide_url": GUIDE_RESULT_URL.format(html_name=html_name),
            }
        )
    return items


def parse_guide_list_displayed_count(page_html: str) -> int | None:
    match = DISPLAYED_COUNT_HTML_RE.search(page_html)
    if not match:
        match = DISPLAYED_COUNT_RE.search(page_html)
    if not match:
        match = DISPLAYED_COUNT_RE.search(_clean_text(page_html))
    if not match:
        return None
    return int(match.group(1))


def parse_guide_detail(html_name: str, page_html: str, list_titles: list[str] | None = None) -> dict[str, Any]:
    guide_html = _extract_guide_area(page_html)

    title_match = TITLE_RE.search(guide_html)
    if not title_match:
        raise ValueError(f"{html_name}: 제목을 찾지 못했습니다.")
    request_url_match = REQUEST_URL_RE.search(guide_html)
    if not request_url_match:
        raise ValueError(f"{html_name}: 요청 URL을 찾지 못했습니다.")

    tables = TABLE_RE.findall(guide_html)
    if not tables:
        raise ValueError(f"{html_name}: 표 구조를 찾지 못했습니다.")

    request_params = _parse_request_params(tables[0])
    response_fields = _parse_response_fields(tables[1]) if len(tables) > 1 else []
    sample_urls = _extract_sample_urls(guide_html)

    return {
        "official_html_name": html_name,
        "guide_url": GUIDE_RESULT_URL.format(html_name=html_name),
        "title": _clean_title(title_match.group(1)),
        "request_url": _normalize_sample_url(request_url_match.group(1)),
        "request_params": request_params,
        "response_fields": response_fields,
        "sample_urls": sample_urls,
        "supported_types": _supported_types_from_urls(sample_urls),
        "sample_variants": _build_sample_variants(sample_urls),
        "official_list_titles": list_titles or [],
    }


def fetch_official_guides(session: requests.Session | None = None, timeout: float = 30) -> dict[str, Any]:
    http = session or requests.Session()
    http.headers.setdefault(
        "User-Agent",
        "law-api-mcp-korea/0.1.0 (+https://open.law.go.kr/)",
    )

    list_page = http.get(GUIDE_LIST_URL, timeout=timeout)
    list_page.raise_for_status()
    list_items = parse_guide_list(list_page.text)
    displayed_count = parse_guide_list_displayed_count(list_page.text)

    titles_by_html_name: dict[str, list[str]] = defaultdict(list)
    for item in list_items:
        titles_by_html_name[item["official_html_name"]].append(item["title"])

    official_guides: list[dict[str, Any]] = []
    for html_name in sorted(titles_by_html_name):
        page = http.get(GUIDE_RESULT_URL.format(html_name=html_name), timeout=timeout)
        page.raise_for_status()
        official_guides.append(
            parse_guide_detail(
                html_name=html_name,
                page_html=page.text,
                list_titles=titles_by_html_name[html_name],
            )
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "guide_list_url": GUIDE_LIST_URL,
        "guide_list_displayed_count": displayed_count,
        "official_list_item_count": len(list_items),
        "official_guide_count": len(official_guides),
        "official_list_items": list_items,
        "official_guides": official_guides,
    }


def load_official_guides_snapshot(path: Path = SNAPSHOT_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _official_guides_by_html_name(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        guide["official_html_name"]: guide
        for guide in snapshot.get("official_guides", [])
    }


def _casefold_html_name_map(snapshot: dict[str, Any]) -> dict[str, str]:
    return {
        guide["official_html_name"].lower(): guide["official_html_name"]
        for guide in snapshot.get("official_guides", [])
    }


def official_html_names_for_api(api: dict[str, Any], snapshot: dict[str, Any]) -> tuple[list[str], str]:
    title = str(api.get("title") or "")
    guide_html_name = str(api.get("guide_html_name") or "")
    official_by_name = _official_guides_by_html_name(snapshot)
    casefold = _casefold_html_name_map(snapshot)

    if title in GROUPED_OFFICIAL_HTML_NAMES:
        return list(GROUPED_OFFICIAL_HTML_NAMES[title]), "grouped"
    if title in TITLE_TO_OFFICIAL_HTML_NAME:
        return [TITLE_TO_OFFICIAL_HTML_NAME[title]], "override"
    if guide_html_name in official_by_name:
        return [guide_html_name], "direct"
    if guide_html_name.lower() in casefold:
        return [casefold[guide_html_name.lower()]], "case_insensitive"
    return [], "unmapped"


def augment_api_with_official_fields(api: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    official_by_name = _official_guides_by_html_name(snapshot)
    html_names, source = official_html_names_for_api(api, snapshot)
    official_guides = [official_by_name[name] for name in html_names if name in official_by_name]

    official_list_titles: list[str] = []
    sample_variants: list[dict[str, Any]] = []
    for guide in official_guides:
        official_list_titles.extend(guide.get("official_list_titles", []))
        for variant in guide.get("sample_variants", []):
            sample_variants.append(
                {
                    "official_html_name": guide["official_html_name"],
                    "official_title": guide["title"],
                    "guide_url": guide["guide_url"],
                    "target": variant.get("target"),
                    "mobileYn": variant.get("mobileYn"),
                    "response_types": list(variant.get("response_types", [])),
                    "urls": list(variant.get("urls", [])),
                }
            )

    deduped_titles = _dedupe_strings(official_list_titles)

    seen_variant_keys: set[tuple[str, str | None, str | None]] = set()
    deduped_variants: list[dict[str, Any]] = []
    for variant in sample_variants:
        key = (
            str(variant["official_html_name"]),
            variant.get("target"),
            variant.get("mobileYn"),
        )
        if key in seen_variant_keys:
            continue
        seen_variant_keys.add(key)
        deduped_variants.append(variant)

    target_variants = _dedupe_strings(
        [str(variant["target"]) for variant in deduped_variants if variant.get("target")]
    )
    official_supported_types = _dedupe_strings(
        [
            response_type
            for variant in deduped_variants
            for response_type in variant.get("response_types", [])
        ]
    )
    official_sample_requests = _dedupe_strings(
        [
            sample_url
            for guide in official_guides
            for sample_url in guide.get("sample_urls", [])
        ]
    )

    payload = dict(api)
    payload["doc_key"] = str(api.get("doc_key") or api.get("slug") or api.get("guide_html_name"))
    payload["official_html_name"] = html_names[0] if html_names else None
    payload["official_html_names"] = html_names
    payload["official_guide_url"] = official_guides[0]["guide_url"] if official_guides else None
    payload["official_source"] = source
    payload["official_list_titles"] = deduped_titles
    payload["sample_variants"] = deduped_variants
    payload["target_variants"] = target_variants
    if official_guides:
        representative = official_guides[0]
        representative_request_url = str(representative.get("request_url") or "")
        payload["guide_url"] = representative.get("guide_url")
        payload["endpoint"] = representative_request_url or payload.get("endpoint")
        if representative_request_url:
            parsed = urlparse(representative_request_url)
            payload["base_url"] = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        default_params = dict(payload.get("default_params", {}))
        if target_variants:
            default_params["target"] = target_variants[0]
        payload["default_params"] = default_params
        if official_supported_types:
            payload["supported_types"] = official_supported_types
        payload["request_params"] = list(representative.get("request_params", []))
        payload["response_fields"] = list(representative.get("response_fields", []))
        if official_sample_requests:
            payload["sample_requests"] = official_sample_requests
        payload["evidence"] = "direct" if source != "unmapped" else payload.get("evidence")
    return payload


def augment_catalog_with_official_fields(catalog: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    updated = dict(catalog)
    updated["guide_list_displayed_count"] = snapshot.get("guide_list_displayed_count")
    updated["official_list_item_count"] = snapshot.get("official_list_item_count")
    updated["official_guide_count"] = snapshot.get("official_guide_count")
    updated["apis"] = [augment_api_with_official_fields(api, snapshot) for api in catalog.get("apis", [])]
    return updated


def normalize_url(url: str) -> NormalizedUrl:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme in {"http", "https"}:
        scheme = "http+https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return NormalizedUrl(
        scheme=scheme,
        netloc=netloc,
        path=parsed.path,
        query_pairs=tuple(parse_qsl(parsed.query, keep_blank_values=True)),
    )


def semantic_url_equal(left: str, right: str) -> bool:
    left_normalized = normalize_url(left)
    right_normalized = normalize_url(right)
    if (
        left_normalized.scheme,
        left_normalized.netloc,
        left_normalized.path,
    ) != (
        right_normalized.scheme,
        right_normalized.netloc,
        right_normalized.path,
    ):
        return False
    return sorted(left_normalized.query_pairs) == sorted(right_normalized.query_pairs)
