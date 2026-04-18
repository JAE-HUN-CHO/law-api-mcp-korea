from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from law_api_mcp_korea.catalog import (  # noqa: E402
    CatalogResolutionError,
    get_api_detail,
    get_doc_markdown,
    metadata,
    resolve_api,
    search_apis,
)


class CatalogTests(unittest.TestCase):
    def test_catalog_count(self):
        self.assertEqual(metadata()["count"], 191)

    def test_resolve_by_title(self):
        api = resolve_api("법제처 법령해석 목록 조회")
        self.assertEqual(api["guide_html_name"], "cgmExpcMolegListGuide")

    def test_resolve_by_guide_html_name(self):
        api = resolve_api("lsNwListGuide")
        self.assertEqual(api["title"], "현행법령(공포일) 목록 조회")
        self.assertNotIn("response_fields", api)

    def test_resolve_by_filename(self):
        api = resolve_api("현행법령_공포일_목록_조회.md")
        self.assertEqual(api["guide_html_name"], "lsNwListGuide")

    def test_resolve_by_normalized_title(self):
        api = resolve_api("법제처법령해석목록조회")
        self.assertEqual(api["guide_html_name"], "cgmExpcMolegListGuide")

    def test_resolve_ambiguous_query(self):
        with self.assertRaises(CatalogResolutionError) as ctx:
            resolve_api("목록 조회")
        self.assertGreaterEqual(len(ctx.exception.candidates), 1)

    def test_resolve_not_found(self):
        with self.assertRaises(CatalogResolutionError):
            resolve_api("없는 API")

    def test_doc_markdown(self):
        text = get_doc_markdown("cgmExpcMolegInfoGuide")
        self.assertIn("# 법제처 법령해석 본문 조회", text)

    def test_detail_includes_constraints(self):
        api = get_api_detail("lsHstInfoGuide")
        self.assertEqual(api["default_params"]["target"], "lsHistory")
        self.assertIn("HTML", api["supported_types"])
        self.assertTrue(any("lsHistory" in note for note in api["notes"]))

    def test_baipvcs_detail_includes_constraint(self):
        api = get_api_detail("baiPvcsListGuide")
        self.assertTrue(any("유효한 API key" in note for note in api["notes"]))

    def test_search(self):
        items = search_apis(keyword="법령해석", limit=10)
        self.assertGreaterEqual(len(items), 1)


if __name__ == "__main__":
    unittest.main()
