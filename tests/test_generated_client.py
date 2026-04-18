from __future__ import annotations

import json
import pathlib
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from law_api_mcp_korea.client import LawOpenApiClient  # noqa: E402
from law_api_mcp_korea.generated_tools import GeneratedToolError, UnsupportedAgencyError  # noqa: E402


class _DummyResponse:
    def __init__(self, data: dict[str, object]) -> None:
        self.status_code = 200
        self._data = data
        self.text = json.dumps(data, ensure_ascii=False)
        self.content = self.text.encode("utf-8")
        self.headers = {"Content-Type": "application/json"}

    def json(self) -> dict[str, object]:
        return self._data


class GeneratedToolClientTests(unittest.TestCase):
    def test_call_generated_tool(self) -> None:
        client = LawOpenApiClient(oc="test")
        with mock.patch.object(
            client.session,
            "get",
            return_value=_DummyResponse({"LawSearch": {"resultCode": "00"}}),
        ) as mocked_get:
            payload = client.call_generated_tool(
                "api_ministry_interpretation",
                mode="list",
                agency="moleg",
                params={"query": "퇴직", "display": 1},
                response_type="JSON",
            )
        self.assertEqual(payload["tool"]["name"], "api_ministry_interpretation")
        self.assertEqual(payload["agency"]["code"], "moleg")
        self.assertEqual(payload["mode"], "list")
        self.assertEqual(payload["status_code"], 200)
        mocked_get.assert_called_once()

    def test_generated_tool_validation_runs_before_network(self) -> None:
        client = LawOpenApiClient(oc="test")
        with mock.patch.object(client.session, "get") as mocked_get:
            with self.assertRaises(UnsupportedAgencyError):
                client.call_generated_tool(
                    "api_ministry_interpretation",
                    mode="list",
                    agency="abc",
                    params={"query": "퇴직"},
                )
        mocked_get.assert_not_called()

    def test_bai_generated_tool_returns_invalid_api_key_error(self) -> None:
        client = LawOpenApiClient(oc="test")
        response = mock.Mock(status_code=404, text="", headers={"Content-Type": "text/plain"})
        with mock.patch.object(client.session, "get", return_value=response):
            with self.assertRaises(GeneratedToolError) as ctx:
                client.call_generated_tool(
                    "api_bai_pre_consultation",
                    mode="list",
                    params={"target": "baiPvcs", "query": "계약", "search": 1, "display": 1, "page": 1},
                    response_type="JSON",
                )
        self.assertIn("유효한 API key가 아닙니다", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
