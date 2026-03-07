from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .catalog import (
    get_doc_markdown,
    manifest_json,
    metadata,
    resolve_api,
    search_apis,
    summarize_api,
    verification_report,
)
from .client import LawOpenApiClient


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
                "items": [summarize_api(api) for api in search_apis(limit=500)],
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.resource("lawdoc://manifest")
    def manifest_resource() -> str:
        return manifest_json()

    @mcp.resource("lawdoc://verification")
    def verification_resource() -> str:
        return verification_report()

    @mcp.resource("lawdoc://api/{api_name}")
    def api_doc_resource(api_name: str) -> str:
        return get_doc_markdown(api_name)

    @mcp.tool()
    def list_apis(keyword: str = "", family: str = "", limit: int = 50) -> dict[str, Any]:
        """법제처 OPEN API 문서 카탈로그를 검색합니다."""
        items = search_apis(keyword=keyword, family=family, limit=limit)
        return {
            "meta": metadata(),
            "count": len(items),
            "items": [summarize_api(item) for item in items],
        }

    @mcp.tool()
    def get_api_doc(api_name: str, include_markdown: bool = True) -> dict[str, Any]:
        """특정 API 문서와 파라미터 명세를 반환합니다."""
        api = resolve_api(api_name)
        payload: dict[str, Any] = {
            "api": summarize_api(api),
        }
        if include_markdown:
            payload["markdown"] = get_doc_markdown(api_name)
        return payload

    @mcp.tool()
    def authenticate(oc: str) -> dict[str, Any]:
        """세션에서 사용할 LAW_API_OC 값을 설정합니다."""
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
        """실제 호출 URL만 생성합니다."""
        client = _client_for_request(oc)
        return {
            "api": summarize_api(resolve_api(api_name)),
            "request_url": client.build_url(api_name, params=params, response_type=response_type, oc=oc),
        }

    @mcp.tool()
    def call_api(
        api_name: str,
        params: dict[str, Any] | None = None,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        """문서 카탈로그를 기반으로 범용 법제처 OPEN API를 호출합니다."""
        client = _client_for_request(oc)
        return client.call_api(api_name, params=params, response_type=response_type, oc=oc)

    @mcp.tool()
    def search_current_law(
        query: str,
        display: int = 20,
        page: int = 1,
        search: int = 1,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        """현행법령(공포일) 목록을 조회합니다."""
        client = _client_for_request(oc)
        return client.search_current_law(
            query=query,
            display=display,
            page=page,
            search=search,
            response_type=response_type,
            oc=oc,
        )

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
        """현행법령(공포일) 본문을 조회합니다."""
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
        """법제처 법령해석 목록을 조회합니다."""
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

    @mcp.tool()
    def get_moleg_interpretation(
        id: str,
        response_type: str = "JSON",
        oc: str | None = None,
    ) -> dict[str, Any]:
        """법제처 법령해석 본문을 조회합니다."""
        client = _client_for_request(oc)
        return client.get_moleg_interpretation(id=id, response_type=response_type, oc=oc)

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
