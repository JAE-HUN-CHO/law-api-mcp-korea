from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .catalog import (
    CatalogResolutionError,
    get_api_doc_payload,
    get_doc_markdown,
    metadata,
    resolve_api,
    search_apis,
    summarize_api,
)
from .client import LawOpenApiClient, LawOpenApiError
from .env import save_dotenv_value
from .generated_tools import GeneratedToolError


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _parse_param_pairs(pairs: list[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(f"--param 형식이 잘못되었습니다: {pair} (예: key=value)")
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit(f"--param key가 비어 있습니다: {pair}")
        result[key] = value
    return result


def _print_catalog(items: list[dict[str, Any]]) -> None:
    for api in items:
        print(
            f"[{api['index']:03d}] {api['slug']} | {api['family']} | {api['title']} | "
            f"{', '.join(api.get('supported_types', []))}"
        )


def _print_generated_catalog(items: list[dict[str, Any]]) -> None:
    for item in items:
        print(f"- {item['name']}")
        print(f"  title: {item['title']}")
        print(f"  kind: {item['kind']}")
        if item.get("requires_mode"):
            print(f"  modes: {', '.join(item.get('supported_modes', []))}")
        if item.get("requires_agency"):
            print(f"  agencies: {', '.join(item.get('supported_agencies', []))}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="law-openapi-cli", description="법제처 OPEN API CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_catalog = sub.add_parser("catalog", help="API 카탈로그 검색")
    p_catalog.add_argument("--search", default="", help="검색어")
    p_catalog.add_argument("--family", default="", help="family 필터")
    p_catalog.add_argument("--limit", type=int, default=50, help="최대 개수")
    p_catalog.add_argument("--json", action="store_true", help="JSON 출력")
    p_catalog.add_argument("--view", choices=["summary", "detail"], default="detail", help="JSON 출력 view")

    p_tool_catalog = sub.add_parser("tool-catalog", help="생성된 tool 카탈로그 조회")
    p_tool_catalog.add_argument("--search", default="", help="검색어")
    p_tool_catalog.add_argument("--limit", type=int, default=100, help="최대 개수")
    p_tool_catalog.add_argument("--json", action="store_true", help="JSON 출력")

    p_tool_doc = sub.add_parser("tool-doc", help="생성된 tool 문서 조회")
    p_tool_doc.add_argument("tool", help="generated tool 이름")
    p_tool_doc.add_argument("--view", choices=["summary", "detail"], default="detail", help="출력 view")

    p_tool = sub.add_parser("tool", help="생성된 tool 실행")
    p_tool.add_argument("tool", help="generated tool 이름")
    p_tool.add_argument("--mode", default=None, help="list/info")
    p_tool.add_argument("--agency", default=None, help="기관 코드 또는 기관명")
    p_tool.add_argument("--type", default="JSON", help="HTML/XML/JSON")
    p_tool.add_argument("--oc", default=None, help="OC 값")
    p_tool.add_argument("--param", action="append", default=[], help="key=value")
    p_tool.add_argument("--save", default=None, help="응답 저장 파일 경로")

    p_doc = sub.add_parser("doc", help="API 문서 조회")
    p_doc.add_argument("api", help="slug / guide_html_name / 제목 / 파일명")
    p_doc.add_argument("--json", action="store_true", help="요약 JSON 출력")
    p_doc.add_argument("--summary", action="store_true", help="문서 본문 대신 요약 출력")
    p_doc.add_argument("--view", choices=["summary", "detail", "markdown"], default=None, help="출력 view")

    p_auth = sub.add_parser("auth", help="LAW_API_OC 인증값 저장")
    p_auth.add_argument("--oc", required=True, help="OC 값")
    p_auth.add_argument("--json", action="store_true", help="JSON 출력")

    p_build = sub.add_parser("build-url", help="실제 호출 URL 생성")
    p_build.add_argument("api")
    p_build.add_argument("--type", default="JSON", help="HTML/XML/JSON")
    p_build.add_argument("--oc", default=None, help="OC 값")
    p_build.add_argument("--param", action="append", default=[], help="key=value")

    p_call = sub.add_parser("call", help="범용 API 호출")
    p_call.add_argument("api")
    p_call.add_argument("--type", default="JSON", help="HTML/XML/JSON")
    p_call.add_argument("--oc", default=None, help="OC 값")
    p_call.add_argument("--param", action="append", default=[], help="key=value")
    p_call.add_argument("--save", default=None, help="응답 저장 파일 경로")

    sub.add_parser("live-sweep", help="191개 API live sweep 검증")

    p_search_law = sub.add_parser("search-law", help="현행법령(공포일) 목록 조회")
    p_search_law.add_argument("query")
    p_search_law.add_argument("--display", type=int, default=20)
    p_search_law.add_argument("--page", type=int, default=1)
    p_search_law.add_argument("--search", type=int, default=1)
    p_search_law.add_argument("--type", default="JSON")
    p_search_law.add_argument("--oc", default=None)

    p_get_law = sub.add_parser("get-law", help="현행법령(공포일) 본문 조회")
    p_get_law.add_argument("--id", default=None)
    p_get_law.add_argument("--mst", default=None)
    p_get_law.add_argument("--jo", default=None)
    p_get_law.add_argument(
        "--with-sub-articles",
        action="store_true",
        help="조항호목 상세를 모두 추가 조회",
    )
    p_get_law.add_argument("--type", default="JSON")
    p_get_law.add_argument("--oc", default=None)
    p_get_law.add_argument("--param", action="append", default=[], help="추가 key=value")

    p_search_moleg = sub.add_parser("search-moleg", help="법제처 법령해석 목록 조회")
    p_search_moleg.add_argument("query")
    p_search_moleg.add_argument("--display", type=int, default=20)
    p_search_moleg.add_argument("--page", type=int, default=1)
    p_search_moleg.add_argument("--search", type=int, default=1)
    p_search_moleg.add_argument("--expl-yd", default=None, help="예: 20240101~20240131")
    p_search_moleg.add_argument("--type", default="JSON")
    p_search_moleg.add_argument("--oc", default=None)

    p_get_moleg = sub.add_parser("get-moleg", help="법제처 법령해석 본문 조회")
    p_get_moleg.add_argument("--id", required=True)
    p_get_moleg.add_argument("--type", default="JSON")
    p_get_moleg.add_argument("--oc", default=None)

    p_mcp = sub.add_parser("mcp", help="MCP 서버 실행")
    p_mcp.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "catalog":
        items = search_apis(keyword=args.search, family=args.family, limit=args.limit)
        payload = {"meta": metadata(), "count": len(items), "items": [summarize_api(i, view=args.view) for i in items]}
        if args.json:
            print(_json_dump(payload))
        else:
            _print_catalog(items)
        return 0

    if args.command == "tool-catalog":
        client = LawOpenApiClient()
        payload = client.list_generated_tools(keyword=args.search, limit=args.limit)
        if args.json:
            print(_json_dump(payload))
        else:
            _print_generated_catalog(payload["items"])
        return 0

    if args.command == "tool-doc":
        client = LawOpenApiClient()
        print(_json_dump(client.get_generated_tool_doc(args.tool, view=args.view)))
        return 0

    if args.command == "doc":
        try:
            api = resolve_api(args.api)
        except CatalogResolutionError as exc:
            print(str(exc), file=sys.stderr)
            if exc.candidates:
                print("후보:", file=sys.stderr)
                for candidate in exc.candidates:
                    print(f"- {candidate}", file=sys.stderr)
            return 2

        view = args.view or ("detail" if (args.json or args.summary) else "markdown")
        if view == "markdown" and not args.json:
            print(get_doc_markdown(args.api))
        else:
            print(_json_dump(get_api_doc_payload(args.api, view=view)))
        return 0

    if args.command == "auth":
        dotenv_path = save_dotenv_value("LAW_API_OC", args.oc.strip())
        payload = {
            "authenticated": True,
            "oc": args.oc.strip(),
            "dotenv_path": str(dotenv_path),
        }
        if args.json:
            print(_json_dump(payload))
        else:
            print(f"LAW_API_OC saved to {dotenv_path}")
        return 0

    if args.command == "mcp":
        from .mcp_server import main as mcp_main

        return mcp_main(["--transport", args.transport])

    client = LawOpenApiClient()

    try:
        if args.command == "build-url":
            params = _parse_param_pairs(args.param)
            print(client.build_url(args.api, params=params, response_type=args.type, oc=args.oc))
            return 0

        if args.command == "call":
            params = _parse_param_pairs(args.param)
            payload = client.call_api(args.api, params=params, response_type=args.type, oc=args.oc)
            output = _json_dump(payload)
            if args.save:
                Path(args.save).write_text(output, encoding="utf-8")
            print(output)
            return 0

        if args.command == "live-sweep":
            print(_json_dump(client.run_live_sweep()))
            return 0

        if args.command == "tool":
            params = _parse_param_pairs(args.param)
            payload = client.call_generated_tool(
                args.tool,
                mode=args.mode,
                agency=args.agency,
                params=params,
                response_type=args.type,
                oc=args.oc,
            )
            output = _json_dump(payload)
            if args.save:
                Path(args.save).write_text(output, encoding="utf-8")
            print(output)
            return 0

        if args.command == "search-law":
            payload = client.search_current_law(
                query=args.query,
                display=args.display,
                page=args.page,
                search=args.search,
                response_type=args.type,
                oc=args.oc,
            )
            print(_json_dump(payload))
            return 0

        if args.command == "get-law":
            extra = _parse_param_pairs(args.param)
            if args.with_sub_articles:
                payload = client.get_current_law_with_sub_articles(
                    id=args.id,
                    mst=args.mst,
                    jo=args.jo,
                    response_type=args.type,
                    oc=args.oc,
                    **extra,
                )
            else:
                payload = client.get_current_law(
                    id=args.id,
                    mst=args.mst,
                    jo=args.jo,
                    response_type=args.type,
                    oc=args.oc,
                    **extra,
                )
            print(_json_dump(payload))
            return 0

        if args.command == "search-moleg":
            payload = client.search_moleg_interpretations(
                query=args.query,
                display=args.display,
                page=args.page,
                search=args.search,
                expl_yd=args.expl_yd,
                response_type=args.type,
                oc=args.oc,
            )
            print(_json_dump(payload))
            return 0

        if args.command == "get-moleg":
            payload = client.get_moleg_interpretation(id=args.id, response_type=args.type, oc=args.oc)
            print(_json_dump(payload))
            return 0

    except (CatalogResolutionError, GeneratedToolError, LawOpenApiError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
