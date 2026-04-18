"""TDD tests for citations.py — written BEFORE implementation."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class TestExtractCitations(unittest.TestCase):
    def _fn(self):
        from law_api_mcp_korea.citations import extract_citations
        return extract_citations

    def test_simple_article_extraction(self):
        fn = self._fn()
        citations = fn("민법 제750조에 따라 손해배상 책임이 있습니다.")
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["law_name"], "민법")
        self.assertEqual(citations[0]["article"], 750)

    def test_multiple_citations(self):
        fn = self._fn()
        text = "근로기준법 제56조 및 산업안전보건법 제38조를 위반하였습니다."
        citations = fn(text)
        self.assertEqual(len(citations), 2)
        law_names = {c["law_name"] for c in citations}
        self.assertIn("근로기준법", law_names)
        self.assertIn("산업안전보건법", law_names)

    def test_alias_resolved_in_citation(self):
        fn = self._fn()
        citations = fn("화관법 제12조에 따른 화학물질 취급 기준.")
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["law_name_resolved"], "화학물질관리법")

    def test_raw_text_preserved(self):
        fn = self._fn()
        citations = fn("민법 제750조 적용.")
        self.assertIn("raw", citations[0])
        self.assertIn("민법", citations[0]["raw"])

    def test_empty_text_returns_empty_list(self):
        fn = self._fn()
        self.assertEqual(fn("아무 법령도 없는 텍스트"), [])

    def test_no_duplicates_for_same_citation(self):
        fn = self._fn()
        text = "민법 제750조는 중요합니다. 민법 제750조 참조."
        citations = fn(text)
        # 중복 제거되어야 함
        articles = [(c["law_name"], c["article"]) for c in citations]
        self.assertEqual(len(articles), len(set(articles)))


class TestVerifiedMarker(unittest.TestCase):
    def test_verified_marker_constant(self):
        from law_api_mcp_korea.citations import VERIFIED_MARKER
        self.assertEqual(VERIFIED_MARKER, "[VERIFIED]")

    def test_hallucination_marker_imported(self):
        from law_api_mcp_korea.citations import HALLUCINATION_MARKER
        self.assertEqual(HALLUCINATION_MARKER, "[HALLUCINATION_DETECTED]")

    def test_citation_result_structure(self):
        from law_api_mcp_korea.citations import build_citation_result
        result = build_citation_result(
            raw="민법 제750조",
            law_name="민법",
            law_name_resolved="민법",
            article=750,
            status="not_found",
        )
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(result["marker"], "[HALLUCINATION_DETECTED]")
        self.assertEqual(result["raw"], "민법 제750조")

    def test_verified_status_gets_verified_marker(self):
        from law_api_mcp_korea.citations import build_citation_result
        result = build_citation_result(
            raw="민법 제750조",
            law_name="민법",
            law_name_resolved="민법",
            article=750,
            status="verified",
        )
        self.assertEqual(result["marker"], "[VERIFIED]")

    def test_skipped_status_gets_skipped_marker(self):
        from law_api_mcp_korea.citations import build_citation_result
        result = build_citation_result(
            raw="민법 제750조",
            law_name="민법",
            law_name_resolved="민법",
            article=750,
            status="skipped",
        )
        self.assertEqual(result["marker"], "[SKIPPED]")

    def test_error_status_gets_error_marker(self):
        from law_api_mcp_korea.citations import build_citation_result
        result = build_citation_result(
            raw="민법 제750조",
            law_name="민법",
            law_name_resolved="민법",
            article=750,
            status="error",
        )
        self.assertEqual(result["marker"], "[ERROR]")


if __name__ == "__main__":
    unittest.main()
