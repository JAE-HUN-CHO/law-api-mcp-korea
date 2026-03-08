from __future__ import annotations

import json
import os
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import requests

from .catalog import CatalogResolutionError, resolve_api, summarize_api
from .env import load_dotenv
from .generated_tools import (
    GeneratedToolError,
    generated_tool_metadata,
    get_generated_tool_doc,
    search_generated_tools,
    summarize_generated_tool,
    validate_generated_tool_call,
)


class LawOpenApiError(RuntimeError):
    """Base exception for this package."""


class MissingOCError(LawOpenApiError):
    """Raised when OC is missing."""


class UnsupportedResponseTypeError(LawOpenApiError):
    """Raised when the selected API does not support the requested response type."""


class RequestPreparationError(LawOpenApiError):
    """Raised when a request cannot be prepared."""


class HttpRequestError(LawOpenApiError):
    """Raised when the API request fails."""


class InvalidApiKeyError(LawOpenApiError):
    """Raised when the upstream API behaves like the OC is not valid."""


@dataclass(frozen=True)
class PreparedLawRequest:
    api: dict[str, Any]
    base_url: str
    query_params: dict[str, str]
    url: str
    response_type: str


def _bool_from_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _xml_to_data(element: ET.Element) -> Any:
    children = list(element)
    text = (element.text or "").strip()

    if not children and not element.attrib:
        return text

    payload: dict[str, Any] = {}
    if element.attrib:
        payload["@attributes"] = dict(element.attrib)

    if text:
        payload["#text"] = text

    grouped: dict[str, Any] = {}
    for child in children:
        value = _xml_to_data(child)
        if child.tag in grouped:
            if not isinstance(grouped[child.tag], list):
                grouped[child.tag] = [grouped[child.tag]]
            grouped[child.tag].append(value)
        else:
            grouped[child.tag] = value

    payload.update(grouped)
    return payload


def _is_invalid_api_key_api(api: dict[str, Any]) -> bool:
    target = str(dict(api.get("default_params", {})).get("target", "")).strip()
    return target == "baiPvcs"


def _invalid_api_key_message(api: dict[str, Any]) -> str:
    return (
        "유효한 API key가 아닙니다. "
        f"{api['title']} API는 현재 등록된 키로 정상 검증되지 않습니다."
    )


class LawOpenApiClient:
    def __init__(
        self,
        oc: str | None = None,
        timeout: float | None = None,
        force_https: bool | None = None,
        session: requests.Session | None = None,
    ) -> None:
        load_dotenv()
        self.oc = oc or os.getenv("LAW_API_OC")
        self.timeout = float(timeout or os.getenv("LAW_API_TIMEOUT") or 30)
        self.force_https = _bool_from_env("LAW_API_FORCE_HTTPS", False) if force_https is None else force_https
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent",
            "law-api-mcp-korea/0.1.0 (+https://open.law.go.kr/)",
        )

    def prepare_request(
        self,
        api_name: str,
        params: dict[str, Any] | None = None,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> PreparedLawRequest:
        api = resolve_api(api_name)
        response_type = (response_type or "JSON").upper().strip()

        supported = [t.upper() for t in api.get("supported_types", [])]
        if supported and response_type not in supported:
            raise UnsupportedResponseTypeError(
                f"{api['title']} API는 {', '.join(supported)} 형식만 지원합니다. 요청 형식: {response_type}"
            )

        oc_value = oc or self.oc
        if not oc_value:
            raise MissingOCError(
                "OC 값이 없습니다. 환경변수 LAW_API_OC 또는 함수 인자로 OC를 제공하세요."
            )

        user_params = dict(params or {})
        base_url = str(api["base_url"])
        if self.force_https and base_url.startswith("http://"):
            base_url = "https://" + base_url[len("http://") :]

        fixed_params = {k: str(v) for k, v in dict(api.get("default_params", {})).items()}
        query_params: dict[str, str] = dict(fixed_params)

        for reserved in ("OC", "type"):
            if reserved in user_params and str(user_params[reserved]).strip():
                raise RequestPreparationError(
                    f"{reserved} 파라미터는 별도 인자/환경변수로 관리됩니다. params에서 제거하세요."
                )

        for key, value in user_params.items():
            if value is None:
                continue
            value_str = _stringify(value)
            if key in fixed_params and fixed_params[key] != value_str:
                raise RequestPreparationError(
                    f"{key}={value_str} 는 선택한 API 문서의 고정값 {fixed_params[key]} 와 다릅니다."
                )
            query_params[key] = value_str

        query_params["OC"] = str(oc_value)
        query_params["type"] = response_type

        prepared = requests.Request("GET", base_url, params=query_params).prepare()
        if not prepared.url:
            raise RequestPreparationError("요청 URL 생성에 실패했습니다.")

        return PreparedLawRequest(
            api=api,
            base_url=base_url,
            query_params=query_params,
            url=prepared.url,
            response_type=response_type,
        )

    def build_url(
        self,
        api_name: str,
        params: dict[str, Any] | None = None,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> str:
        prepared = self.prepare_request(api_name, params=params, response_type=response_type, oc=oc)
        return prepared.url

    def call_api(
        self,
        api_name: str,
        params: dict[str, Any] | None = None,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        prepared = self.prepare_request(api_name, params=params, response_type=response_type, oc=oc)

        try:
            response = self.session.get(prepared.base_url, params=prepared.query_params, timeout=self.timeout)
        except requests.RequestException as exc:
            if _is_invalid_api_key_api(prepared.api):
                raise InvalidApiKeyError(_invalid_api_key_message(prepared.api)) from exc
            raise HttpRequestError(f"HTTP 요청 실패: {exc}") from exc

        if response.status_code >= 400:
            if _is_invalid_api_key_api(prepared.api):
                raise InvalidApiKeyError(_invalid_api_key_message(prepared.api))
            snippet = response.text[:1000]
            raise HttpRequestError(
                f"HTTP {response.status_code} 오류가 발생했습니다.\n"
                f"URL: {prepared.url}\n"
                f"응답 일부:\n{snippet}"
            )

        content_type = response.headers.get("Content-Type", "")
        payload: Any
        parse_error: str | None = None

        if prepared.response_type == "JSON" or "json" in content_type.lower():
            try:
                payload = response.json()
            except ValueError as exc:
                parse_error = f"JSON 파싱 실패: {exc}"
                payload = response.text
        elif prepared.response_type == "XML" or "xml" in content_type.lower():
            try:
                root = ET.fromstring(response.text)
                payload = {root.tag: _xml_to_data(root)}
            except ET.ParseError as exc:
                parse_error = f"XML 파싱 실패: {exc}"
                payload = response.text
        else:
            payload = response.text

        result = {
            "api": summarize_api(prepared.api),
            "request_url": prepared.url,
            "status_code": response.status_code,
            "content_type": content_type,
            "response_type": prepared.response_type,
            "data": payload,
        }
        if parse_error:
            result["parse_error"] = parse_error
        return result

    def list_generated_tools(self, keyword: str = "", limit: int = 100) -> dict[str, Any]:
        items = [summarize_generated_tool(tool) for tool in search_generated_tools(keyword, limit)]
        meta = generated_tool_metadata()
        return {
            "items": items,
            "meta": {
                "raw_count": meta["raw_api_count"],
                "logical_count": meta["logical_count"],
                "generated_count": meta["generated_count"],
            },
        }

    def get_generated_tool_doc(self, tool_name: str, view: str = "detail") -> dict[str, Any]:
        return get_generated_tool_doc(tool_name, view=view)

    def run_live_sweep(self) -> dict[str, Any]:
        from .live_sweep import run_live_sweep

        return run_live_sweep(self)

    def call_generated_tool(
        self,
        tool_name: str,
        mode: str | None = None,
        agency: str | None = None,
        params: dict[str, Any] | None = None,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        try:
            selection = validate_generated_tool_call(
                tool_name=tool_name,
                mode=mode,
                agency=agency,
                params=params,
            )
            payload = self.call_api(
                selection["api"]["title"],
                params=selection["params"],
                response_type=response_type,
                oc=oc,
            )
        except GeneratedToolError:
            raise
        except (CatalogResolutionError, LawOpenApiError) as exc:
            raise GeneratedToolError(str(exc)) from exc

        payload["tool"] = summarize_generated_tool(selection["tool"])
        if selection.get("mode") is not None:
            payload["mode"] = selection["mode"]
        if selection.get("agency") is not None:
            payload["agency"] = selection["agency"]
        return payload

    def search_current_law(
        self,
        query: str,
        display: int = 20,
        page: int = 1,
        search: int = 1,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        return self.call_api(
            "현행법령(공포일) 목록 조회",
            params={
                "query": query,
                "display": display,
                "page": page,
                "search": search,
            },
            response_type=response_type,
            oc=oc,
        )

    def get_current_law(
        self,
        id: str | None = None,
        mst: str | None = None,
        jo: str | None = None,
        response_type: str = "JSON",
        oc: str | None = None,
        **extra_params: Any,
    ) -> dict[str, Any]:
        params: dict[str, Any] = dict(extra_params)
        if id:
            params["ID"] = id
        if mst:
            params["MST"] = mst
        if jo:
            params["JO"] = jo
        return self.call_api("현행법령(공포일) 본문 조회", params=params, response_type=response_type, oc=oc)

    def get_current_law_with_sub_articles(
        self,
        id: str | None = None,
        mst: str | None = None,
        jo: str | None = None,
        response_type: str = "JSON",
        oc: str | None = None,
        **extra_params: Any,
    ) -> dict[str, Any]:
        if (response_type or "JSON").upper().strip() != "JSON":
            raise RequestPreparationError("조항호목 전체 확장 조회는 현재 JSON 형식만 지원합니다.")

        base_result = self.get_current_law(
            id=id,
            mst=mst,
            jo=jo,
            response_type="JSON",
            oc=oc,
            **extra_params,
        )

        request_params: dict[str, Any] = dict(extra_params)
        if id:
            request_params["ID"] = id
        if mst:
            request_params["MST"] = mst
            request_params.setdefault("efYd", self._extract_effective_date(base_result))

        jo_codes = [jo] if jo else self._extract_jo_codes(base_result)

        sub_article_api = summarize_api(resolve_api("현행법령(공포일) 본문 조항호목 조회"))
        sub_articles: list[dict[str, Any]] = []
        for jo_code in jo_codes:
            payload = self.call_api(
                "현행법령(공포일) 본문 조항호목 조회",
                params={**request_params, "JO": jo_code},
                response_type="JSON",
                oc=oc,
            )
            sub_articles.append(
                {
                    "jo": jo_code,
                    "request_url": payload["request_url"],
                    "data": payload["data"],
                }
            )

        return {
            **base_result,
            "sub_article_api": sub_article_api,
            "sub_article_count": len(sub_articles),
            "sub_articles": sub_articles,
        }

    def _extract_effective_date(self, payload: dict[str, Any]) -> str:
        law = payload.get("data", {}).get("법령", {})
        basic_info = law.get("기본정보", {})
        ef_yd = basic_info.get("시행일자")
        if not ef_yd:
            raise RequestPreparationError("MST 기반 조항호목 조회에는 시행일자(efYd)가 필요합니다.")
        return str(ef_yd)

    def _extract_jo_codes(self, payload: dict[str, Any]) -> list[str]:
        law = payload.get("data", {}).get("법령", {})
        article_section = law.get("조문", {})
        article_units = article_section.get("조문단위", [])
        if isinstance(article_units, dict):
            article_units = [article_units]

        jo_codes: list[str] = []
        seen: set[str] = set()
        for unit in article_units:
            if not isinstance(unit, dict):
                continue
            if unit.get("조문여부") != "조문":
                continue
            article_key = str(unit.get("조문키") or "").strip()
            if len(article_key) < 6 or not article_key[:6].isdigit():
                continue
            jo_code = article_key[:6]
            if jo_code in seen:
                continue
            seen.add(jo_code)
            jo_codes.append(jo_code)

        if not jo_codes:
            raise RequestPreparationError("조항호목 조회용 조문 번호를 추출하지 못했습니다.")

        return jo_codes

    def search_moleg_interpretations(
        self,
        query: str,
        display: int = 20,
        page: int = 1,
        search: int = 1,
        expl_yd: str | None = None,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "query": query,
            "display": display,
            "page": page,
            "search": search,
        }
        if expl_yd:
            params["explYd"] = expl_yd
        return self.call_api("법제처 법령해석 목록 조회", params=params, response_type=response_type, oc=oc)

    def get_moleg_interpretation(
        self,
        id: str,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        return self.call_api(
            "법제처 법령해석 본문 조회",
            params={"ID": id},
            response_type=response_type,
            oc=oc,
        )
