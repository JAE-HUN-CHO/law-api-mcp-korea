from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from .catalog import all_apis, get_api_detail, resolve_api

PLACEHOLDER_RE = re.compile(r"^\{([^}]+)\}$")
INVALID_API_KEY_TITLES = {
    "감사원 사전컨설팅 의견서 목록 조회",
    "감사원 사전컨설팅 의견서 본문 조회",
}
LIST_TITLE_ALIASES = {
    "법령 연혁 본문 조회": "현행법령(공포일) 목록 조회",
    "현행법령(시행일) 본문 조항호목 조회": "현행법령(시행일) 목록 조회",
    "현행법령(공포일) 본문 조항호목 조회": "현행법령(공포일) 목록 조회",
    "조문별 변경 이력 목록 조회": "현행법령(공포일) 목록 조회",
    "위원회 결정문 본문 조회 (공정거래위원회·국민권익위원회·개인정보보호위원회)": "위원회 결정문 목록 조회 (공정거래위원회·국민권익위원회·개인정보보호위원회)",
    "인사혁신처 소청심사위원회 특별행정심판례 본문 조회": "인사혁신처 소청심사위원회 특별행정심판재결례 목록 조회",
    "위임법령 조회": "3단 비교 목록 조회",
}
TITLE_QUERY_OVERRIDES = {
    "법령 연혁 목록 조회": ["행정"],
    "금융위원회 결정문 목록 조회": ["법"],
    "중앙토지수용위원회 결정문 목록 조회": ["행정"],
    "외교부 법령해석 목록 조회": ["외교", "행정"],
    "통일부 법령해석 목록 조회": ["통일", "행정"],
    "기상청 법령해석 목록 조회": ["기상"],
    "문화체육관광부 법령해석 목록 조회": ["행정", "문화"],
    "질병관리청 법령해석 목록 조회": ["질병", "보건", "행정"],
    "산림청 법령해석 목록 조회": ["산림", "행정"],
    "재외동포청 법령해석 목록 조회": ["외교"],
    "지식재산처 법령해석 목록 조회": ["행정"],
}
PLACEHOLDER_FIELD_CANDIDATES = {
    "법령ID": ["법령ID"],
    "행정규칙ID": ["행정규칙ID", "행정규칙일련번호"],
    "자치법규ID": ["자치법규ID", "자치법규일련번호"],
    "판례일련번호": ["판례일련번호"],
    "헌재결정례일련번호": ["헌재결정례일련번호"],
    "법령해석일련번호": ["법령해석일련번호"],
    "결정문일련번호": ["결정문일련번호"],
    "재결례일련번호": ["재결례일련번호", "특별행정심판재결례일련번호"],
    "조약ID": ["조약ID", "조약일련번호"],
    "용어ID": ["용어ID"],
    "의견서일련번호": ["감사원사전컨설팅의견서일련번호", "의견서일련번호"],
}


def _pick_sample_request(api: dict[str, Any]) -> tuple[str, dict[str, str], str]:
    urls = [item for item in api.get("sample_requests", []) if isinstance(item, str) and item.startswith("http")]
    if not urls:
        raise ValueError(f"{api['title']} API에 sample request URL이 없습니다.")
    json_urls = [item for item in urls if "TYPE=JSON" in item.upper()]
    url = json_urls[0] if json_urls else urls[0]
    query = parse_qs(urlparse(url).query, keep_blank_values=True)
    response_type = (query.pop("type", ["JSON"])[0] or "JSON").upper()
    query.pop("OC", None)
    return url, {key: values[-1] for key, values in query.items()}, response_type


def _call_with_retry(
    client: Any,
    api_title: str,
    params: dict[str, Any],
    response_type: str,
    attempts: int = 2,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return client.call_api(api_title, params=params, response_type=response_type)
        except Exception as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def _placeholder_name(value: str) -> str | None:
    match = PLACEHOLDER_RE.match((value or "").strip())
    return match.group(1) if match else None


def _iter_dicts(node: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    queue: list[Any] = [node]
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            items.append(current)
            queue.extend(current.values())
        elif isinstance(current, list):
            queue.extend(current)
    return items


def _extract_first_record(data: Any) -> dict[str, Any] | None:
    identifier_keys = {
        candidate
        for values in PLACEHOLDER_FIELD_CANDIDATES.values()
        for candidate in values
    }
    for node in _iter_dicts(data):
        if any("상세링크" in key for key in node):
            return node
        if any(key in node for key in identifier_keys):
            return node
    return None


def _extract_detail_link(api_title: str, record: dict[str, Any]) -> str | None:
    links = [
        (key, value)
        for key, value in record.items()
        if isinstance(value, str) and "상세링크" in key and "/DRF/" in value
    ]
    if not links:
        return None
    if api_title == "위임법령 조회":
        for key, value in links:
            if "위임" in key:
                return value
    if api_title == "3단 비교 본문 조회":
        for key, value in links:
            if "인용" in key:
                return value
    return links[0][1]


def _detail_link_params(link: str | None) -> dict[str, str]:
    if not link:
        return {}
    query = parse_qs(urlparse(link).query, keep_blank_values=True)
    result: dict[str, str] = {}
    for key, values in query.items():
        if key in {"OC", "type", "target"}:
            continue
        value = values[-1]
        if value:
            result[key] = value
    return result


def _candidate_queries(list_title: str, sample_params: dict[str, str]) -> list[dict[str, str]]:
    key = "query" if "query" in sample_params else ("LM" if "LM" in sample_params else None)
    if not key:
        return [dict(sample_params)]

    extras = list(TITLE_QUERY_OVERRIDES.get(list_title, []))
    if extras:
        pass
    elif "법령해석" in list_title:
        extras = ["행정", "법", "허가", "처분", "기준"]
    elif "결정문" in list_title:
        extras = ["실업급여", "처분", "결정", "조정"]
    elif "특별행정심판" in list_title or "행정심판례" in list_title:
        extras = ["부가가치세", "행정", "처분", "조세"]
    elif "행정규칙" in list_title:
        extras = ["훈령", "행정", "기준"]
    elif "자치법규" in list_title:
        extras = ["조례", "행정", "부과"]
    elif "조약" in list_title:
        extras = ["협정", "대한민국", "조약"]
    elif "용어" in list_title:
        extras = ["행정", "법", "부가가치세"]
    else:
        extras = ["부가가치세법", "자동차관리법", "행정", "계약"]

    terms: list[str] = []
    original = sample_params.get(key, "").strip()
    if original and not _placeholder_name(original):
        terms.append(original)
    for term in extras:
        if term not in terms:
            terms.append(term)
    return [{**sample_params, key: term} for term in terms]


def _list_api_title_for(api_title: str) -> str | None:
    if api_title in LIST_TITLE_ALIASES:
        return LIST_TITLE_ALIASES[api_title]
    if api_title.endswith(" 본문 조회"):
        return api_title[:-6] + " 목록 조회"
    return None


def _extract_from_record(record: dict[str, Any], placeholder: str) -> str | None:
    for key in PLACEHOLDER_FIELD_CANDIDATES.get(placeholder, [placeholder]):
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _build_recovered_params(
    api_title: str,
    sample_params: dict[str, str],
    record: dict[str, Any],
) -> dict[str, str]:
    recovered = {
        key: value
        for key, value in sample_params.items()
        if not _placeholder_name(value)
    }
    recovered.update(_detail_link_params(_extract_detail_link(api_title, record)))

    if api_title == "법령 연혁 본문 조회":
        recovered.pop("ID", None)
        mst = str(recovered.get("MST") or record.get("법령일련번호") or record.get("MST") or "").strip()
        if mst:
            recovered["MST"] = mst
    elif api_title == "위임법령 조회":
        recovered["knd"] = "2"
        recovered.pop("ID", None)
        if "MST" not in recovered:
            mst = str(record.get("삼단비교일련번호") or "").strip()
            if mst:
                recovered["MST"] = mst
        if "MST" not in recovered:
            law_id = str(record.get("법령ID") or "").strip()
            if law_id:
                recovered["ID"] = law_id
    elif api_title == "3단 비교 본문 조회":
        recovered.setdefault("knd", "1")

    if api_title in {"현행법령(시행일) 본문 조항호목 조회", "현행법령(공포일) 본문 조항호목 조회"}:
        ef_yd = str(record.get("시행일자") or "").strip()
        if ef_yd:
            recovered["efYd"] = ef_yd

    for key, value in sample_params.items():
        placeholder = _placeholder_name(value)
        if not placeholder:
            continue
        if key == "knd":
            if api_title == "위임법령 조회":
                recovered["knd"] = "2"
            elif api_title == "3단 비교 본문 조회":
                recovered.setdefault("knd", "1")
            continue
        if recovered.get(key):
            continue
        extracted = _extract_from_record(record, placeholder)
        if extracted:
            recovered[key] = extracted
    return recovered


def _first_record_from_list_api(client: Any, list_title: str) -> tuple[dict[str, Any], dict[str, str], str]:
    list_api = get_api_detail(resolve_api(list_title))
    _, sample_params, response_type = _pick_sample_request(list_api)
    last_payload: dict[str, Any] | None = None
    last_error: Exception | None = None
    for params in _candidate_queries(list_title, sample_params):
        try:
            payload = _call_with_retry(client, list_title, params, response_type)
        except Exception as exc:
            last_error = exc
            continue
        record = _extract_first_record(payload.get("data"))
        if record:
            return record, params, response_type
        last_payload = payload
    raise RuntimeError(
        f"{list_title} 복구용 목록 조회에서 결과를 찾지 못했습니다."
        + (f" 마지막 응답: {last_payload.get('data')}" if last_payload else "")
        + (f" 마지막 오류: {last_error}" if last_error else "")
    )


def _recover_by_lm(client: Any, api_title: str, response_type: str) -> dict[str, Any] | None:
    if "법령해석 본문 조회" not in api_title:
        return None
    list_title = _list_api_title_for(api_title) or ""
    seen: set[str] = set()
    for params in _candidate_queries(list_title, {"LM": "행정"}):
        term = params["LM"]
        if term in seen:
            continue
        seen.add(term)
        payload = _call_with_retry(client, api_title, {"LM": term}, response_type)
        return {
            "strategy": "direct_lm",
            "recovered_params": {"LM": term},
            "payload": payload,
        }
    return None


def recover_api_from_live_sample(client: Any, api_title: str) -> dict[str, Any]:
    if api_title in INVALID_API_KEY_TITLES:
        raise RuntimeError(
            "유효한 API key가 아닙니다. "
            f"{api_title} API는 현재 등록된 키로 정상 검증되지 않습니다."
        )

    api = get_api_detail(api_title)
    _, sample_params, response_type = _pick_sample_request(api)
    list_title = _list_api_title_for(api_title)
    if not list_title:
        raise RuntimeError(f"{api_title} API에 대한 복구용 목록 조회를 찾지 못했습니다.")

    try:
        record, list_params, list_response_type = _first_record_from_list_api(client, list_title)
    except Exception:
        lm_recovery = _recover_by_lm(client, api_title, response_type)
        if lm_recovery is not None:
            return lm_recovery
        raise
    recovered_params = _build_recovered_params(api_title, sample_params, record)
    payload = _call_with_retry(client, api_title, recovered_params, response_type)
    return {
        "strategy": "list_then_detail",
        "list_api": list_title,
        "list_params": list_params,
        "list_response_type": list_response_type,
        "recovered_params": recovered_params,
        "payload": payload,
    }


def run_live_sweep(client: Any) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    counts = {
        "direct_ok": 0,
        "recovered_ok": 0,
        "invalid_api_key": 0,
        "unresolved": 0,
    }

    for summary_api in all_apis():
        api = get_api_detail(summary_api)
        url, sample_params, response_type = _pick_sample_request(api)
        entry: dict[str, Any] = {
            "title": api["title"],
            "guide_html_name": api["guide_html_name"],
            "family": api["family"],
            "sample_url": url,
        }
        try:
            payload = client.call_api(api["title"], params=sample_params, response_type=response_type)
            entry["status"] = "direct_ok"
            entry["status_code"] = payload["status_code"]
            counts["direct_ok"] += 1
        except Exception as exc:
            if api["title"] in INVALID_API_KEY_TITLES:
                entry["status"] = "invalid_api_key"
                entry["error"] = str(exc)
                counts["invalid_api_key"] += 1
            else:
                try:
                    recovered = recover_api_from_live_sample(client, api["title"])
                    entry["status"] = "recovered_ok"
                    entry["status_code"] = recovered["payload"]["status_code"]
                    entry["recovery_strategy"] = recovered.get("strategy", "list_then_detail")
                    if recovered.get("list_api") is not None:
                        entry["list_api"] = recovered["list_api"]
                    if recovered.get("list_params") is not None:
                        entry["list_params"] = recovered["list_params"]
                    entry["recovered_params"] = recovered["recovered_params"]
                    counts["recovered_ok"] += 1
                except Exception as recovery_exc:
                    entry["status"] = "unresolved"
                    entry["error"] = str(exc)
                    entry["recovery_error"] = str(recovery_exc)
                    counts["unresolved"] += 1
        entries.append(entry)

    return {
        "meta": {
            "total": len(entries),
            **counts,
        },
        "entries": entries,
    }
