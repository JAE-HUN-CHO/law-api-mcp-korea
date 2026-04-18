from __future__ import annotations

import os
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from law_api_mcp_korea.client import (  # noqa: E402
    LawOpenApiClient,
    MissingOCError,
    RequestPreparationError,
    UnsupportedResponseTypeError,
)


class ClientPreparationTests(unittest.TestCase):
    def setUp(self):
        self.client = LawOpenApiClient(oc="test")

    def test_build_url(self):
        url = self.client.build_url(
            "cgmExpcMolegListGuide",
            params={"query": "퇴직", "display": 5},
            response_type="JSON",
        )
        self.assertIn("target=molegCgmExpc", url)
        self.assertIn("query=%ED%87%B4%EC%A7%81", url)
        self.assertIn("display=5", url)
        self.assertIn("type=JSON", url)
        self.assertIn("OC=test", url)

    def test_fixed_param_override_blocked(self):
        with self.assertRaises(RequestPreparationError):
            self.client.build_url(
                "cgmExpcMolegListGuide",
                params={"target": "wrongTarget"},
                response_type="JSON",
            )

    def test_missing_oc(self):
        with patch.dict(os.environ, {}, clear=True), patch("law_api_mcp_korea.client.load_dotenv"):
            client = LawOpenApiClient(oc=None)
            with self.assertRaises(MissingOCError):
                client.build_url("cgmExpcMolegListGuide", params={"query": "퇴직"})

    def test_unsupported_response_type(self):
        with self.assertRaises(UnsupportedResponseTypeError):
            self.client.build_url("cgmExpcMolegListGuide", response_type="CSV")

    def test_prepare_request_merges_fixed_params(self):
        prepared = self.client.prepare_request(
            "현행법령(공포일) 목록 조회",
            params={"query": "자동차관리법", "display": 1},
            response_type="JSON",
        )
        self.assertEqual(prepared.query_params["target"], "law")
        self.assertEqual(prepared.query_params["query"], "자동차관리법")
        self.assertEqual(prepared.query_params["display"], "1")
        self.assertEqual(prepared.query_params["OC"], "test")
        self.assertEqual(prepared.query_params["type"], "JSON")

    def test_force_https_from_env(self):
        with patch.dict(os.environ, {"LAW_API_FORCE_HTTPS": "true"}, clear=True):
            client = LawOpenApiClient(oc="test")
            prepared = client.prepare_request("cgmExpcMolegListGuide", response_type="JSON")
        self.assertTrue(prepared.base_url.startswith("https://"))
        self.assertTrue(prepared.url.startswith("https://"))

    def test_call_api_parses_json(self):
        session = Mock()
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.text = '{"ok": true}'
        response.json.return_value = {"ok": True}
        session.get.return_value = response

        client = LawOpenApiClient(oc="test", session=session)
        payload = client.call_api(
            "cgmExpcMolegListGuide",
            params={"query": "퇴직", "display": 1},
            response_type="JSON",
        )

        self.assertEqual(payload["status_code"], 200)
        self.assertEqual(payload["data"], {"ok": True})
        self.assertEqual(payload["response_type"], "JSON")

    def test_call_api_parses_xml(self):
        session = Mock()
        response = Mock()
        response.status_code = 200
        response.headers = {"Content-Type": "application/xml"}
        response.text = "<response><item><id>1</id><name>테스트</name></item></response>"
        session.get.return_value = response

        client = LawOpenApiClient(oc="test", session=session)
        payload = client.call_api(
            "cgmExpcMolegListGuide",
            params={"query": "퇴직", "display": 1},
            response_type="XML",
        )

        self.assertEqual(payload["status_code"], 200)
        self.assertEqual(payload["data"]["response"]["item"]["id"], "1")
        self.assertEqual(payload["data"]["response"]["item"]["name"], "테스트")
        self.assertEqual(payload["response_type"], "XML")

    def test_convenience_preparation(self):
        url = self.client.build_url(
            "현행법령(공포일) 본문 조회",
            params={"ID": "000744"},
            response_type="JSON",
        )
        self.assertIn("lawService.do", url)
        self.assertIn("ID=000744", url)


if __name__ == "__main__":
    unittest.main()
