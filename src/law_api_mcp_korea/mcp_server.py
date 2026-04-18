from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .catalog import (
    catalog_json,
    get_doc_markdown,
    get_api_doc_payload,
    manifest_summary,
    manifest_json,
    metadata,
    resolve_api,
    search_apis,
    summarize_api,
    verification_json,
    verification_report,
    verification_summary,
)
from .aliases import NOT_FOUND_MARKER, not_found_response, resolve_alias
from .client import LawOpenApiClient, LawOpenApiError, InvalidParamError, MissingParamError
from .citations import VERIFIED_MARKER, build_citation_result, extract_citations
from .decisions import DECISION_DOMAINS, domain_name, get_info_slug, get_list_slug, resolve_domain
from .generated_tools import all_generated_tools


_VALID_VIEWS = {"summary", "detail"}


def _build_tool_description(spec: dict[str, Any]) -> str:
    """Build a human-readable description string for a generated tool spec."""
    parts = [spec.get("description") or spec["title"]]
    if spec.get("requires_agency"):
        parts.append("agency 파라미터 필수.")
    if spec.get("requires_mode"):
        modes = spec.get("modes") or []
        parts.append(f"mode: {modes}")
    return " ".join(parts)


def create_server(stateless_http: bool = False):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit(
            "mcp 패키지가 설치되어 있지 않습니다. `pip install mcp` 또는 `uv sync` 후 다시 실행하세요."
        ) from exc

    mcp = FastMCP("MOLEG Law OpenAPI", json_response=True, stateless_http=stateless_http)
    authenticated_oc: str | None = None

    def _client_for_request(oc: str | None = None) -> LawOpenApiClient:
        return LawOpenApiClient(oc=oc or authenticated_oc)

    @mcp.resource("lawdoc://catalog")
    def catalog_resource() -> str:
        return json.dumps(
            {
                "meta": metadata(),
                "items": [summarize_api(api, view="summary") for api in search_apis(limit=500)],
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.resource("lawdoc://catalog/raw")
    def catalog_raw_resource() -> str:
        return catalog_json()

    @mcp.resource("lawdoc://manifest")
    def manifest_resource() -> str:
        return json.dumps(manifest_summary(), ensure_ascii=False, indent=2)

    @mcp.resource("lawdoc://manifest/raw")
    def manifest_raw_resource() -> str:
        return manifest_json()

    @mcp.resource("lawdoc://verification")
    def verification_resource() -> str:
        return json.dumps(verification_summary(), ensure_ascii=False, indent=2)

    @mcp.resource("lawdoc://verification/raw")
    def verification_raw_resource() -> str:
        return verification_report()

    @mcp.resource("lawdoc://api/{api_name}")
    def api_doc_resource(api_name: str) -> str:
        return json.dumps(get_api_doc_payload(api_name, view="summary"), ensure_ascii=False, indent=2)

    @mcp.resource("lawdoc://api/{api_name}/detail")
    def api_doc_detail_resource(api_name: str) -> str:
        return json.dumps(get_api_doc_payload(api_name, view="detail"), ensure_ascii=False, indent=2)

    @mcp.resource("lawdoc://api/{api_name}/markdown")
    def api_doc_markdown_resource(api_name: str) -> str:
        return get_doc_markdown(api_name)

    @mcp.tool()
    def list_apis(
        keyword: str = "",
        family: str = "",
        limit: int = 50,
        offset: int = 0,
        view: str = "summary",
    ) -> dict[str, Any]:
        """법제처 OPEN API 문서 카탈로그를 검색합니다.

        언제 사용: 사용 가능한 API 목록을 탐색하거나 키워드로 검색할 때.
        파라미터:
          keyword: 검색 키워드 (선택, 기본값 "")
          family: API 패밀리 필터 (선택, 기본값 "")
          limit: 최대 반환 수 (선택, 기본값 50)
          offset: 페이지 오프셋 (선택, 기본값 0)
          view: 상세 수준 — "summary" | "detail" | "minimal" (선택, 기본값 "summary")
        반환: {meta, count, items[]}
        에러: view가 유효하지 않으면 {"error": true, "error_type": "InvalidParamError", ...}
        """
        if view not in _VALID_VIEWS:
            return {
                "error": True,
                "error_type": InvalidParamError.__name__,
                "message": f"view는 {sorted(_VALID_VIEWS)} 중 하나여야 합니다. 입력값: {view!r}",
            }
        keyword = resolve_alias(keyword) if keyword else keyword
        items = search_apis(keyword=keyword, family=family, limit=limit, offset=offset)
        return {
            "meta": metadata(),
            "count": len(items),
            "items": [summarize_api(item, view=view) for item in items],
        }

    @mcp.tool()
    def get_api_doc(api_name: str, view: str = "summary", include_markdown: bool = False) -> dict[str, Any]:
        """특정 API의 문서와 파라미터 명세를 반환합니다.

        언제 사용: 특정 API의 상세 스펙(파라미터, 응답 구조, 예제)이 필요할 때.
        파라미터:
          api_name: API 식별자 (필수, list_apis로 조회 가능)
          view: 상세 수준 — "summary" | "detail" | "minimal" (선택, 기본값 "summary")
          include_markdown: 마크다운 문서 포함 여부 (선택, 기본값 false)
        반환: {api, params[], notes[], sample_requests[], sample_responses[]}
        """
        return get_api_doc_payload(api_name, view=view, include_markdown=include_markdown)

    @mcp.tool()
    def list_generated_tools(keyword: str = "", limit: int = 100) -> dict[str, Any]:
        """생성된 logical/collapsed tool 목록을 반환합니다.

        언제 사용: 법령 유형별로 묶인 고수준 도구 목록을 탐색할 때.
        파라미터:
          keyword: 필터 키워드 (선택, 기본값 "")
          limit: 최대 반환 수 (선택, 기본값 100)
        반환: {meta, count, items[]}
        에러: {"error": true, "error_type": "...", "message": "..."}
        """
        try:
            client = _client_for_request()
            return client.list_generated_tools(keyword=keyword, limit=limit)
        except LawOpenApiError as exc:
            return {"error": True, "error_type": type(exc).__name__, "message": str(exc)}

    @mcp.tool()
    def get_generated_tool_doc(tool_name: str, view: str = "summary") -> dict[str, Any]:
        """생성된 logical/collapsed tool의 상세 문서를 반환합니다.

        언제 사용: 특정 generated tool의 파라미터와 지원 기관/모드를 확인할 때.
        파라미터:
          tool_name: 도구 이름 (필수, list_generated_tools로 조회)
          view: 상세 수준 — "summary" | "detail" (선택, 기본값 "summary")
        반환: {name, title, requires_agency, requires_mode, supported_modes[], supported_agencies[]}
        에러: {"error": true, "error_type": "...", "message": "..."}
        """
        try:
            client = _client_for_request()
            return client.get_generated_tool_doc(tool_name, view=view)
        except LawOpenApiError as exc:
            return {"error": True, "error_type": type(exc).__name__, "message": str(exc)}

    @mcp.tool()
    def authenticate(oc: str) -> dict[str, Any]:
        """세션 전체에서 사용할 LAW_API_OC 인증 코드를 설정합니다.

        언제 사용: 개별 도구 호출마다 oc를 전달하지 않고 세션 단위로 인증할 때.
        파라미터:
          oc: 법제처 Open API 인증키 (필수, open.law.go.kr에서 발급)
        반환: {authenticated: true, oc: "설정된 값"}
        에러: oc가 빈 문자열이면 ValueError 발생
        """
        nonlocal authenticated_oc
        oc = (oc or "").strip()
        if not oc:
            raise ValueError("OC 값이 비어 있습니다.")
        authenticated_oc = oc
        return {
            "authenticated": True,
            "oc": authenticated_oc,
        }

    @mcp.tool()
    def build_request_url(
        api_name: str,
        params: dict[str, Any] | None = None,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        """실제 API 호출 없이 요청 URL만 생성합니다.

        언제 사용: 직접 브라우저나 curl로 API를 테스트하거나 URL을 확인할 때.
        파라미터:
          api_name: API 식별자 (필수)
          params: API별 쿼리 파라미터 dict (선택)
          response_type: "JSON" | "XML" | "HTML" (선택, 기본값 "JSON")
          oc: 인증키 — 미설정 시 authenticate()로 세션에 설정된 값 사용 (선택)
        반환: {api, request_url}
        에러: {"error": true, "error_type": "...", "message": "..."}
        """
        try:
            client = _client_for_request(oc)
            return {
                "api": summarize_api(resolve_api(api_name)),
                "request_url": client.build_url(api_name, params=params, response_type=response_type, oc=oc),
            }
        except LawOpenApiError as exc:
            return {"error": True, "error_type": type(exc).__name__, "message": str(exc)}

    @mcp.tool()
    def call_api(
        api_name: str,
        params: dict[str, Any] | None = None,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        """문서 카탈로그를 기반으로 범용 법제처 OPEN API를 호출합니다.

        언제 사용: 특정 API를 직접 호출하고 응답을 받을 때. 전용 도구가 없는 API에 사용.
        파라미터:
          api_name: API 식별자 (필수, list_apis로 조회)
          params: API별 쿼리 파라미터 dict (선택)
          response_type: "JSON" | "XML" | "HTML" (선택, 기본값 "JSON")
          oc: 인증키 — 미설정 시 authenticate()로 세션에 설정된 값 사용 (선택)
        반환: {api, status_code, data}
        에러: {"error": true, "error_type": "...", "message": "..."}
        """
        try:
            client = _client_for_request(oc)
            return client.call_api(api_name, params=params, response_type=response_type, oc=oc)
        except LawOpenApiError as exc:
            return {"error": True, "error_type": type(exc).__name__, "message": str(exc)}

    @mcp.tool()
    def search_current_law(
        query: str,
        display: int = 20,
        page: int = 1,
        search: int = 1,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        """현행법령 목록을 키워드로 검색합니다.

        언제 사용: 법령명이나 키워드로 현행 법령 목록을 조회할 때.
        파라미터:
          query: 검색어 (필수)
          display: 페이지당 결과 수 1~100 (선택, 기본값 20)
          page: 페이지 번호 (선택, 기본값 1)
          search: 검색 범위 — 1=법령명, 2=본문 (선택, 기본값 1)
          response_type: "JSON" | "XML" (선택, 기본값 "JSON")
          oc: 인증키 (선택)
        반환: 법령 목록 응답 dict
        에러: {"error": true, "error_type": "MissingOCError"|"HttpRequestError", "message": "..."}
        """
        query = resolve_alias(query)
        try:
            client = _client_for_request(oc)
            result = client.search_current_law(
                query=query,
                display=display,
                page=page,
                search=search,
                response_type=response_type,
                oc=oc,
            )
            # NOT_FOUND 마커: 응답 data 안에 법령 목록이 비어있는 경우
            if isinstance(result, dict):
                data = result.get("data", result)
                laws = (
                    data.get("LawSearch", {}).get("law")
                    or data.get("law")
                    or []
                )
                if isinstance(laws, dict):
                    laws = [laws]
                if not laws:
                    return not_found_response(query, "법령")
            return result
        except LawOpenApiError as exc:
            return {"error": True, "error_type": type(exc).__name__, "message": str(exc)}

    @mcp.tool()
    def get_current_law(
        id: str | None = None,
        mst: str | None = None,
        jo: str | None = None,
        include_sub_articles: bool = False,
        response_type: str = "JSON",
        oc: str | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """현행법령 본문을 조회합니다.

        언제 사용: 특정 법령의 조문 내용을 가져올 때. id/mst/jo 중 하나는 반드시 필요.
        파라미터:
          id: 법령 일련번호 (선택, search_current_law 결과에서 획득)
          mst: 법령 마스터 번호 (선택)
          jo: 조문 번호 (선택, 특정 조문만 조회할 때)
          include_sub_articles:
            false(기본값) — 단일 조문/법령만 반환 (get_current_law 호출)
            true — 하위 조문 전체 포함 반환 (get_current_law_with_sub_articles 호출, 응답이 큼)
          response_type: "JSON" | "XML" | "HTML" (선택, 기본값 "JSON")
          oc: 인증키 (선택)
          extra_params: 추가 쿼리 파라미터 dict (선택)
        반환: 법령 본문 응답 dict
        에러:
          id/mst/jo 모두 None → {"error": true, "error_type": "MissingParamError", ...}
          API 오류 → {"error": true, "error_type": "MissingOCError"|"HttpRequestError", ...}
        """
        if not any([id, mst, jo]):
            return {
                "error": True,
                "error_type": MissingParamError.__name__,
                "message": "id, mst, jo 중 하나는 필수입니다.",
            }
        try:
            client = _client_for_request(oc)
            if include_sub_articles:
                return client.get_current_law_with_sub_articles(
                    id=id,
                    mst=mst,
                    jo=jo,
                    response_type=response_type,
                    oc=oc,
                    **(extra_params or {}),
                )
            return client.get_current_law(
                id=id,
                mst=mst,
                jo=jo,
                response_type=response_type,
                oc=oc,
                **(extra_params or {}),
            )
        except LawOpenApiError as exc:
            return {"error": True, "error_type": type(exc).__name__, "message": str(exc)}

    @mcp.tool()
    def search_moleg_interpretations(
        query: str,
        display: int = 20,
        page: int = 1,
        search: int = 1,
        expl_yd: str | None = None,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        """법제처 법령해석 목록을 키워드로 검색합니다.

        언제 사용: 법제처의 공식 법령해석 사례를 검색할 때.
        파라미터:
          query: 검색어 (필수)
          display: 페이지당 결과 수 (선택, 기본값 20)
          page: 페이지 번호 (선택, 기본값 1)
          search: 검색 범위 — 1=제목, 2=본문 (선택, 기본값 1)
          expl_yd: 해석 연도 필터 YYYY 형식 (선택)
          response_type: "JSON" | "XML" (선택, 기본값 "JSON")
          oc: 인증키 (선택)
        반환: 법령해석 목록 응답 dict
        에러: {"error": true, "error_type": "...", "message": "..."}
        """
        try:
            client = _client_for_request(oc)
            return client.search_moleg_interpretations(
                query=query,
                display=display,
                page=page,
                search=search,
                expl_yd=expl_yd,
                response_type=response_type,
                oc=oc,
            )
        except LawOpenApiError as exc:
            return {"error": True, "error_type": type(exc).__name__, "message": str(exc)}

    @mcp.tool()
    def get_moleg_interpretation(
        id: str,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        """법제처 법령해석 본문을 조회합니다.

        언제 사용: search_moleg_interpretations로 찾은 특정 해석의 전문을 가져올 때.
        파라미터:
          id: 법령해석 일련번호 (필수, search_moleg_interpretations 결과에서 획득)
          response_type: "JSON" | "XML" (선택, 기본값 "JSON")
          oc: 인증키 (선택)
        반환: 법령해석 본문 응답 dict
        에러: {"error": true, "error_type": "...", "message": "..."}
        """
        try:
            client = _client_for_request(oc)
            return client.get_moleg_interpretation(id=id, response_type=response_type, oc=oc)
        except LawOpenApiError as exc:
            return {"error": True, "error_type": type(exc).__name__, "message": str(exc)}

    _VALID_DOMAINS = sorted(DECISION_DOMAINS.keys())

    @mcp.tool()
    def search_decisions(
        query: str,
        domain: str = "prec",
        display: int = 20,
        page: int = 1,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        """판례·결정례·해석례를 도메인별로 통합 검색합니다.

        언제 사용: 대법원 판례, 헌재결정, 행정심판, 법령해석, 조세심판 등을 하나의 도구로 검색할 때.
        파라미터:
          query: 검색어 (필수, 법령 약어 자동 해석)
          domain: 도메인 코드 또는 한국어 약어 (선택, 기본값 "prec")
            코드: prec(대법원), detc(헌재), decc(행심), expc(법령해석),
                  tt(조세심판), kmst(해양심판), nlrc(노위), acr(권익위), moleg(법제처)
            한국어: 판례, 헌재, 행심, 법령해석, 조심, 해심, 노위, 권익위, 법제처
          display: 페이지당 결과 수 (선택, 기본값 20)
          page: 페이지 번호 (선택, 기본값 1)
          response_type: "JSON" | "XML" (선택, 기본값 "JSON")
          oc: 인증키 (선택)
        반환: {domain, domain_name, query, items[]} 또는 not_found_response
        에러: {"error": true, "error_type": "InvalidParamError"|"...", "message": "..."}
        """
        domain_code = resolve_domain(domain)
        if domain_code is None:
            return {
                "error": True,
                "error_type": InvalidParamError.__name__,
                "message": f"domain은 {_VALID_DOMAINS} 중 하나 또는 한국어 약어여야 합니다. 입력값: {domain!r}",
            }
        query = resolve_alias(query)

        # moleg 도메인은 기존 search_moleg_interpretations 위임
        if domain_code == "moleg":
            try:
                client = _client_for_request(oc)
                result = client.search_moleg_interpretations(
                    query=query, display=display, page=page, response_type=response_type, oc=oc
                )
                return {"domain": "moleg", "domain_name": "법제처 법령해석", "query": query, "data": result}
            except LawOpenApiError as exc:
                return {"error": True, "error_type": type(exc).__name__, "message": str(exc)}

        list_slug = get_list_slug(domain_code)
        try:
            client = _client_for_request(oc)
            result = client.call_api(
                list_slug,
                params={"query": query, "display": display, "page": page},
                response_type=response_type,
                oc=oc,
            )
            # 빈 결과 감지 (응답 구조는 API마다 다름)
            data = result.get("data", result)
            items = (
                data.get("PrecSearch", {}).get("prec")
                or data.get("DetcSearch", {}).get("detc")
                or data.get("DeccSearch", {}).get("decc")
                or data.get("ExpcSearch", {}).get("expc")
                or []
            )
            if isinstance(items, dict):
                items = [items]
            if not items:
                return not_found_response(query, domain_name(domain_code))
            return {
                "domain": domain_code,
                "domain_name": domain_name(domain_code),
                "query": query,
                "count": len(items),
                "items": items,
            }
        except LawOpenApiError as exc:
            return {"error": True, "error_type": type(exc).__name__, "message": str(exc)}

    @mcp.tool()
    def get_decision_text(
        id: str,
        domain: str,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        """판례·결정례·해석례 본문을 조회합니다.

        언제 사용: search_decisions로 찾은 결정의 전문을 가져올 때.
        파라미터:
          id: 결정 일련번호 (필수, search_decisions 결과에서 획득)
          domain: 도메인 코드 (필수)
            코드: prec, detc, decc, expc, tt, kmst, nlrc, acr
          response_type: "JSON" | "XML" (선택, 기본값 "JSON")
          oc: 인증키 (선택)
        반환: 결정 본문 응답 dict
        에러: {"error": true, "error_type": "...", "message": "..."}
        """
        domain_code = resolve_domain(domain)
        if domain_code is None:
            return {
                "error": True,
                "error_type": InvalidParamError.__name__,
                "message": f"domain은 {_VALID_DOMAINS} 중 하나여야 합니다. 입력값: {domain!r}",
            }
        if domain_code == "moleg":
            try:
                client = _client_for_request(oc)
                return client.get_moleg_interpretation(id=id, response_type=response_type, oc=oc)
            except LawOpenApiError as exc:
                return {"error": True, "error_type": type(exc).__name__, "message": str(exc)}

        info_slug = get_info_slug(domain_code)
        try:
            client = _client_for_request(oc)
            return client.call_api(
                info_slug,
                params={"ID": id},
                response_type=response_type,
                oc=oc,
            )
        except LawOpenApiError as exc:
            return {"error": True, "error_type": type(exc).__name__, "message": str(exc)}

    @mcp.tool()
    def verify_citations(
        text: str,
        oc: str | None = None,
    ) -> dict[str, Any]:
        """AI가 생성한 법률 텍스트의 법령 조문 인용을 실제 DB와 대조 검증합니다.

        언제 사용: AI가 생성한 법률 분석이나 판례 요약에서 조문 인용이 실제 존재하는지 확인할 때.
        파라미터:
          text: 검증할 법률 텍스트 (필수). 예: "민법 제750조에 따라 손해배상 책임이 있음"
          oc: 인증키 (선택, 없으면 DB 조회 없이 파싱만 수행)
        반환:
          {
            total: 발견된 인용 수,
            verified: 존재 확인된 수 (oc 없으면 0),
            not_found: 존재하지 않는 인용 수,
            skipped: oc 없어서 건너뛴 수,
            citations: [
              {raw, law_name, law_name_resolved, article, status, marker, detail}
            ]
          }
        마커:
          [VERIFIED] — 실제 DB에서 법령 존재 확인
          [HALLUCINATION_DETECTED] — 존재하지 않는 조문 (AI 환각 의심)
        에러: {"error": true, "error_type": "...", "message": "..."}
        """
        citations_raw = extract_citations(text)
        if not citations_raw:
            return {
                "total": 0,
                "verified": 0,
                "not_found": 0,
                "skipped": 0,
                "citations": [],
                "message": "텍스트에서 법령 조문 인용을 찾지 못했습니다.",
            }

        results = []
        verified_count = 0
        not_found_count = 0
        skipped_count = 0

        oc_value = oc or authenticated_oc
        for cit in citations_raw:
            if not oc_value:
                # OC 없으면 네트워크 조회 없이 parsed 상태로만 반환
                skipped_count += 1
                results.append(build_citation_result(
                    raw=cit["raw"],
                    law_name=cit["law_name"],
                    law_name_resolved=cit["law_name_resolved"],
                    article=cit["article"],
                    status="skipped",
                    detail={"reason": "OC 인증키 없음 — authenticate() 또는 oc 파라미터로 설정 필요"},
                ))
                continue

            try:
                client = _client_for_request(oc)
                search_result = client.search_current_law(
                    query=cit["law_name_resolved"],
                    display=5,
                    search=1,
                    oc=oc,
                )
                # 법령 존재 여부 확인 — 응답은 {"data": {"LawSearch": {...}}} 구조
                _sr_data = search_result.get("data", search_result)
                laws = (
                    _sr_data.get("LawSearch", {}).get("law")
                    or _sr_data.get("law")
                    or []
                )
                if isinstance(laws, dict):
                    laws = [laws]
                status = "verified" if laws else "not_found"
                if status == "verified":
                    verified_count += 1
                else:
                    not_found_count += 1
                results.append(build_citation_result(
                    raw=cit["raw"],
                    law_name=cit["law_name"],
                    law_name_resolved=cit["law_name_resolved"],
                    article=cit["article"],
                    status=status,
                    detail={"law_count": len(laws)},
                ))
            except LawOpenApiError as exc:
                skipped_count += 1
                results.append(build_citation_result(
                    raw=cit["raw"],
                    law_name=cit["law_name"],
                    law_name_resolved=cit["law_name_resolved"],
                    article=cit["article"],
                    status="error",
                    detail={"error": str(exc)},
                ))

        return {
            "total": len(results),
            "verified": verified_count,
            "not_found": not_found_count,
            "skipped": skipped_count,
            "citations": results,
        }

    def _register_generated_tool(spec: dict[str, Any]) -> None:
        description = _build_tool_description(spec)

        if spec.get("requires_agency"):

            def _generated_tool(
                agency: str | None = None,
                mode: str | None = None,
                params: dict[str, Any] | None = None,
                response_type: str = "JSON",
                oc: str | None = None,
            ) -> dict[str, Any]:
                client = _client_for_request(oc)
                return client.call_generated_tool(
                    spec["name"],
                    mode=mode,
                    agency=agency,
                    params=params,
                    response_type=response_type,
                    oc=oc,
                )

        elif spec.get("requires_mode"):

            def _generated_tool(
                mode: str | None = None,
                params: dict[str, Any] | None = None,
                response_type: str = "JSON",
                oc: str | None = None,
            ) -> dict[str, Any]:
                client = _client_for_request(oc)
                return client.call_generated_tool(
                    spec["name"],
                    mode=mode,
                    params=params,
                    response_type=response_type,
                    oc=oc,
                )

        else:

            def _generated_tool(
                params: dict[str, Any] | None = None,
                response_type: str = "JSON",
                oc: str | None = None,
            ) -> dict[str, Any]:
                client = _client_for_request(oc)
                return client.call_generated_tool(
                    spec["name"],
                    params=params,
                    response_type=response_type,
                    oc=oc,
                )

        _generated_tool.__name__ = spec["name"]
        mcp.add_tool(_generated_tool, name=spec["name"], description=description)

    for generated_tool in all_generated_tools():
        _register_generated_tool(generated_tool)

    return mcp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="law-openapi-mcp", description="법제처 OPEN API MCP 서버")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    args = parser.parse_args(argv)

    server = create_server(stateless_http=(args.transport == "streamable-http"))
    if args.transport == "stdio":
        server.run()
    else:
        server.run(transport="streamable-http")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
