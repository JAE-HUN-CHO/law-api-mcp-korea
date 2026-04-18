"""TDD tests for aliases.py — written BEFORE implementation."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class TestResolveAlias(unittest.TestCase):
    def _fn(self):
        from law_api_mcp_korea.aliases import resolve_alias
        return resolve_alias

    def test_known_abbreviation_expands(self):
        fn = self._fn()
        self.assertEqual(fn("화관법"), "화학물질관리법")

    def test_known_abbreviation_근기법(self):
        fn = self._fn()
        self.assertEqual(fn("근기법"), "근로기준법")

    def test_unknown_query_returned_unchanged(self):
        fn = self._fn()
        self.assertEqual(fn("민법"), "민법")

    def test_full_name_returned_unchanged(self):
        fn = self._fn()
        self.assertEqual(fn("근로기준법"), "근로기준법")

    def test_strips_whitespace_before_lookup(self):
        fn = self._fn()
        self.assertEqual(fn("  화관법  "), "화학물질관리법")

    def test_공정거래법_abbreviation(self):
        fn = self._fn()
        self.assertEqual(fn("공정거래법"), "독점규제 및 공정거래에 관한 법률")

    def test_산안법_abbreviation(self):
        fn = self._fn()
        self.assertEqual(fn("산안법"), "산업안전보건법")


class TestNotFoundResponse(unittest.TestCase):
    def _fn(self):
        from law_api_mcp_korea.aliases import not_found_response
        return not_found_response

    def test_returns_dict_with_not_found_true(self):
        fn = self._fn()
        r = fn("화관법", "법령")
        self.assertTrue(r.get("not_found"))

    def test_marker_is_not_found_string(self):
        fn = self._fn()
        r = fn("화관법")
        self.assertEqual(r["marker"], "[NOT_FOUND]")

    def test_query_preserved_in_response(self):
        fn = self._fn()
        r = fn("민법", "판례")
        self.assertEqual(r["query"], "민법")

    def test_message_contains_marker(self):
        fn = self._fn()
        r = fn("없는법", "법령")
        self.assertIn("[NOT_FOUND]", r["message"])


class TestConstants(unittest.TestCase):
    def test_not_found_marker_constant(self):
        from law_api_mcp_korea.aliases import NOT_FOUND_MARKER
        self.assertEqual(NOT_FOUND_MARKER, "[NOT_FOUND]")

    def test_hallucination_marker_constant(self):
        from law_api_mcp_korea.aliases import HALLUCINATION_MARKER
        self.assertEqual(HALLUCINATION_MARKER, "[HALLUCINATION_DETECTED]")

    def test_law_aliases_dict_has_entries(self):
        from law_api_mcp_korea.aliases import LAW_ALIASES
        self.assertGreaterEqual(len(LAW_ALIASES), 30)
        self.assertIn("화관법", LAW_ALIASES)
        self.assertIn("근기법", LAW_ALIASES)


if __name__ == "__main__":
    unittest.main()
