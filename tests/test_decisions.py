"""TDD tests for decisions.py — written BEFORE implementation."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class TestDecisionDomains(unittest.TestCase):
    def _mod(self):
        from law_api_mcp_korea import decisions
        return decisions

    def test_decision_domains_has_prec(self):
        m = self._mod()
        self.assertIn("prec", m.DECISION_DOMAINS)
        self.assertEqual(m.DECISION_DOMAINS["prec"]["name"], "대법원 판례")

    def test_decision_domains_has_detc(self):
        m = self._mod()
        self.assertIn("detc", m.DECISION_DOMAINS)

    def test_decision_domains_has_tt(self):
        m = self._mod()
        self.assertIn("tt", m.DECISION_DOMAINS)
        self.assertEqual(m.DECISION_DOMAINS["tt"]["list"], "specialDeccTtListGuide")

    def test_decision_domains_list_info_slugs(self):
        m = self._mod()
        for code, spec in m.DECISION_DOMAINS.items():
            if spec["list"] is not None:
                self.assertIsInstance(spec["list"], str, f"{code} list slug not str")
            if spec["info"] is not None:
                self.assertIsInstance(spec["info"], str, f"{code} info slug not str")


class TestDomainAliases(unittest.TestCase):
    def _fn(self):
        from law_api_mcp_korea.decisions import resolve_domain
        return resolve_domain

    def test_korean_판례_resolves_to_prec(self):
        fn = self._fn()
        self.assertEqual(fn("판례"), "prec")

    def test_korean_헌재_resolves_to_detc(self):
        fn = self._fn()
        self.assertEqual(fn("헌재"), "detc")

    def test_korean_조심_resolves_to_tt(self):
        fn = self._fn()
        self.assertEqual(fn("조심"), "tt")

    def test_code_passthrough(self):
        fn = self._fn()
        self.assertEqual(fn("prec"), "prec")
        self.assertEqual(fn("decc"), "decc")

    def test_unknown_domain_returns_none(self):
        fn = self._fn()
        self.assertIsNone(fn("UNKNOWN"))


class TestGetDecisionListSlug(unittest.TestCase):
    def _fn(self):
        from law_api_mcp_korea.decisions import get_list_slug, get_info_slug
        return get_list_slug, get_info_slug

    def test_prec_list_slug(self):
        ls, _ = self._fn()
        self.assertEqual(ls("prec"), "precListGuide")

    def test_prec_info_slug(self):
        _, gs = self._fn()
        self.assertEqual(gs("prec"), "precInfoGuide")

    def test_tt_list_slug(self):
        ls, _ = self._fn()
        self.assertEqual(ls("tt"), "specialDeccTtListGuide")

    def test_invalid_domain_returns_none(self):
        ls, gs = self._fn()
        self.assertIsNone(ls("NOSUCHCODE"))
        self.assertIsNone(gs("NOSUCHCODE"))


class TestDecisionDomainsSearchKeys(unittest.TestCase):
    """DECISION_DOMAINS must declare search_key and item_key for all non-moleg domains."""

    def _mod(self):
        from law_api_mcp_korea import decisions
        return decisions

    def test_all_non_moleg_domains_have_search_key(self):
        m = self._mod()
        for code, spec in m.DECISION_DOMAINS.items():
            if code == "moleg":
                continue
            self.assertIn("search_key", spec, f"Domain {code!r} missing 'search_key'")
            self.assertIsInstance(spec["search_key"], str)

    def test_all_non_moleg_domains_have_item_key(self):
        m = self._mod()
        for code, spec in m.DECISION_DOMAINS.items():
            if code == "moleg":
                continue
            self.assertIn("item_key", spec, f"Domain {code!r} missing 'item_key'")
            self.assertIsInstance(spec["item_key"], str)

    def test_prec_search_key(self):
        m = self._mod()
        self.assertEqual(m.DECISION_DOMAINS["prec"]["search_key"], "PrecSearch")
        self.assertEqual(m.DECISION_DOMAINS["prec"]["item_key"], "prec")

    def test_get_item_from_response_function_exists(self):
        from law_api_mcp_korea.decisions import get_item_from_response
        self.assertTrue(callable(get_item_from_response))

    def test_get_item_from_response_extracts_prec(self):
        from law_api_mcp_korea.decisions import get_item_from_response
        response_data = {"PrecSearch": {"prec": [{"id": "1"}]}}
        items = get_item_from_response("prec", response_data)
        self.assertEqual(items, [{"id": "1"}])

    def test_get_item_from_response_returns_empty_for_missing_key(self):
        from law_api_mcp_korea.decisions import get_item_from_response
        items = get_item_from_response("prec", {})
        self.assertEqual(items, [])

    def test_get_item_from_response_wraps_dict_in_list(self):
        from law_api_mcp_korea.decisions import get_item_from_response
        response_data = {"PrecSearch": {"prec": {"id": "1"}}}
        items = get_item_from_response("prec", response_data)
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 1)


if __name__ == "__main__":
    unittest.main()
