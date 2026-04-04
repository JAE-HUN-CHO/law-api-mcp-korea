from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from law_api_mcp_korea.catalog import get_api_detail, resolve_api  # noqa: E402
from law_api_mcp_korea.client import LawOpenApiClient  # noqa: E402
from law_api_mcp_korea.official_guides import (  # noqa: E402
    load_official_guides_snapshot,
    semantic_url_equal,
)


class OfficialGuideSnapshotTests(unittest.TestCase):
    def test_snapshot_counts_match_current_official_site(self):
        snapshot = load_official_guides_snapshot()
        self.assertEqual(snapshot["guide_list_displayed_count"], 191)
        self.assertEqual(snapshot["official_list_item_count"], 195)
        self.assertEqual(snapshot["official_guide_count"], 195)
        self.assertEqual(
            snapshot["official_list_item_count"] - snapshot["guide_list_displayed_count"],
            4,
        )

    def test_override_api_exposes_official_html_name(self):
        api = resolve_api("위임법령 조회")
        self.assertEqual(api["guide_html_name"], "thdCmpInfoGuide")
        self.assertEqual(api["official_html_name"], "lsDelegated")
        self.assertEqual(api["official_source"], "override")

    def test_resolve_by_official_html_name(self):
        api = resolve_api("lsDelegated")
        self.assertEqual(api["title"], "위임법령 조회")

    def test_grouped_committee_api_exposes_target_variants(self):
        api = get_api_detail("위원회 결정문 목록 조회 (공정거래위원회·국민권익위원회·개인정보보호위원회)")
        self.assertEqual(api["official_source"], "grouped")
        self.assertEqual(api["target_variants"], ["ftc", "acr", "ppc"])
        self.assertIn("HTML", api["supported_types"])

    def test_grouped_committee_target_override_is_allowed(self):
        client = LawOpenApiClient(oc="test")
        prepared = client.prepare_request(
            "위원회 결정문 목록 조회 (공정거래위원회·국민권익위원회·개인정보보호위원회)",
            params={"target": "ppc"},
            response_type="JSON",
        )
        self.assertEqual(prepared.query_params["target"], "ppc")

    def test_semantic_url_equal_normalizes_transport_and_host(self):
        official = "http://law.go.kr/DRF/lawService.do?OC=test&target=admrulOldAndNew&ID=2100000248758&type=JSON"
        built = "https://www.law.go.kr/DRF/lawService.do?target=admrulOldAndNew&ID=2100000248758&OC=test&type=JSON"
        self.assertTrue(semantic_url_equal(official, built))


if __name__ == "__main__":
    unittest.main()
