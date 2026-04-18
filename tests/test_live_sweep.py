from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from law_api_mcp_korea.catalog import resolve_api  # noqa: E402
from law_api_mcp_korea.client import InvalidApiKeyError, LawOpenApiClient  # noqa: E402
from law_api_mcp_korea.live_sweep import (  # noqa: E402
    INVALID_API_KEY_TITLES,
    _build_recovered_params,
    _list_api_title_for,
)


class LiveSweepUnitTests(unittest.TestCase):
    def test_alias_mapping(self) -> None:
        self.assertEqual(_list_api_title_for("고용노동부 법령해석 본문 조회"), "고용노동부 법령해석 목록 조회")
        self.assertEqual(
            _list_api_title_for("인사혁신처 소청심사위원회 특별행정심판례 본문 조회"),
            "인사혁신처 소청심사위원회 특별행정심판재결례 목록 조회",
        )
        self.assertEqual(_list_api_title_for("위임법령 조회"), "3단 비교 목록 조회")

    def test_build_recovered_params_for_delegated_law(self) -> None:
        params = _build_recovered_params(
            "위임법령 조회",
            {"knd": "{구분코드}", "ID": "{법령ID}"},
            {
                "법령ID": "001571",
                "삼단비교일련번호": "276117",
                "위임조문_삼단비교상세링크": "/DRF/lawService.do?target=thdCmp&MST=276117&knd=2&type=HTML&mobileYn=",
            },
        )
        self.assertEqual(params["MST"], "276117")
        self.assertEqual(params["knd"], "2")
        self.assertEqual(params["ID"], "001571")

    def test_ls_history_catalog_entry(self) -> None:
        api = resolve_api("법령 연혁 본문 조회")
        self.assertEqual(api["default_params"]["target"], "lsHistory")
        self.assertEqual(api["supported_types"], ["HTML"])

    def test_invalid_api_key_titles(self) -> None:
        self.assertEqual(
            INVALID_API_KEY_TITLES,
            {
                "감사원 사전컨설팅 의견서 목록 조회",
                "감사원 사전컨설팅 의견서 본문 조회",
            },
        )

    def test_baipvcs_error_is_standardized(self) -> None:
        client = LawOpenApiClient(oc="test")
        response = mock.Mock(status_code=404, text="", headers={"Content-Type": "text/plain"})
        with mock.patch.object(client.session, "get", return_value=response):
            with self.assertRaises(InvalidApiKeyError) as ctx:
                client.call_api(
                    "감사원 사전컨설팅 의견서 목록 조회",
                    params={"query": "계약", "search": 1, "display": 1, "page": 1},
                    response_type="JSON",
                )
        self.assertIn("유효한 API key가 아닙니다", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
