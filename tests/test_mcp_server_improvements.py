"""Unit tests for mcp_server improvements — written BEFORE implementation (TDD)."""
from __future__ import annotations

import asyncio
import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None


def _extract_tool_fn(mcp_server, name: str):
    """Extract a callable tool function from a FastMCP server instance."""
    mgr = getattr(mcp_server, "_tool_manager", None)
    if mgr is None:
        raise RuntimeError("FastMCP has no _tool_manager attribute")
    for attr in ("_tools", "tools"):
        tools = getattr(mgr, attr, None)
        if tools and name in tools:
            tool = tools[name]
            return getattr(tool, "fn", tool)
    raise KeyError(f"Tool '{name}' not found in FastMCP server")


def _call_tool(mcp_tool: str, **kwargs):
    from law_api_mcp_korea.mcp_server import create_server
    server = create_server()
    fn = _extract_tool_fn(server, mcp_tool)
    if asyncio.iscoroutinefunction(fn):
        return asyncio.run(fn(**kwargs))
    return fn(**kwargs)


# ---------------------------------------------------------------------------
# Step 1: try/except — LawOpenApiError → error dict
# ---------------------------------------------------------------------------

@unittest.skipUnless(MCP_AVAILABLE, "mcp package required")
class TestStep1ErrorHandling(unittest.TestCase):
    """Tools must catch LawOpenApiError and return {"error": True, ...} dict."""

    def test_call_api_returns_error_dict_on_law_error(self):
        from law_api_mcp_korea.client import HttpRequestError
        with patch(
            "law_api_mcp_korea.client.LawOpenApiClient.call_api",
            side_effect=HttpRequestError("connection failed"),
        ):
            result = _call_tool("call_api", api_name="someApi")
        self.assertTrue(result.get("error"), msg=f"Expected error dict, got: {result}")
        self.assertEqual(result["error_type"], "HttpRequestError")
        self.assertIn("connection failed", result["message"])

    def test_search_current_law_returns_error_dict_on_law_error(self):
        from law_api_mcp_korea.client import MissingOCError
        with patch(
            "law_api_mcp_korea.client.LawOpenApiClient.search_current_law",
            side_effect=MissingOCError("OC 없음"),
        ):
            result = _call_tool("search_current_law", query="test")
        self.assertTrue(result.get("error"), msg=f"Expected error dict, got: {result}")
        self.assertEqual(result["error_type"], "MissingOCError")
        self.assertIn("OC", result["message"])

    def test_get_current_law_returns_error_dict_on_law_error(self):
        from law_api_mcp_korea.client import MissingOCError
        with patch(
            "law_api_mcp_korea.client.LawOpenApiClient.get_current_law",
            side_effect=MissingOCError("OC 없음"),
        ):
            result = _call_tool("get_current_law", id="12345")
        self.assertTrue(result.get("error"), msg=f"Expected error dict, got: {result}")
        self.assertEqual(result["error_type"], "MissingOCError")

    def test_build_request_url_returns_error_dict_on_law_error(self):
        from law_api_mcp_korea.client import RequestPreparationError
        with patch("law_api_mcp_korea.mcp_server.resolve_api", return_value={}), \
             patch("law_api_mcp_korea.mcp_server.summarize_api", return_value={}), \
             patch(
                 "law_api_mcp_korea.client.LawOpenApiClient.build_url",
                 side_effect=RequestPreparationError("bad url"),
             ):
            result = _call_tool("build_request_url", api_name="someApi")
        self.assertTrue(result.get("error"), msg=f"Expected error dict, got: {result}")
        self.assertEqual(result["error_type"], "RequestPreparationError")

    def test_search_moleg_interpretations_returns_error_dict_on_law_error(self):
        from law_api_mcp_korea.client import MissingOCError
        with patch(
            "law_api_mcp_korea.client.LawOpenApiClient.search_moleg_interpretations",
            side_effect=MissingOCError("OC 없음"),
        ):
            result = _call_tool("search_moleg_interpretations", query="test")
        self.assertTrue(result.get("error"), msg=f"Expected error dict, got: {result}")
        self.assertEqual(result["error_type"], "MissingOCError")

    def test_get_moleg_interpretation_returns_error_dict_on_law_error(self):
        from law_api_mcp_korea.client import HttpRequestError
        with patch(
            "law_api_mcp_korea.client.LawOpenApiClient.get_moleg_interpretation",
            side_effect=HttpRequestError("timeout"),
        ):
            result = _call_tool("get_moleg_interpretation", id="999")
        self.assertTrue(result.get("error"), msg=f"Expected error dict, got: {result}")
        self.assertEqual(result["error_type"], "HttpRequestError")

    def test_list_generated_tools_returns_error_dict_on_law_error(self):
        from law_api_mcp_korea.client import MissingOCError
        with patch(
            "law_api_mcp_korea.client.LawOpenApiClient.list_generated_tools",
            side_effect=MissingOCError("OC 없음"),
        ):
            result = _call_tool("list_generated_tools")
        self.assertTrue(result.get("error"), msg=f"Expected error dict, got: {result}")
        self.assertEqual(result["error_type"], "MissingOCError")

    def test_get_generated_tool_doc_returns_error_dict_on_law_error(self):
        from law_api_mcp_korea.client import MissingOCError
        with patch(
            "law_api_mcp_korea.client.LawOpenApiClient.get_generated_tool_doc",
            side_effect=MissingOCError("OC 없음"),
        ):
            # "tool_name" conflicts with _call_tool's first positional arg; pass as dict unpack
            result = _call_tool("get_generated_tool_doc", tool_name="api_test")
        self.assertTrue(result.get("error"), msg=f"Expected error dict, got: {result}")
        self.assertEqual(result["error_type"], "MissingOCError")


# ---------------------------------------------------------------------------
# Step 2: parameter validation
# ---------------------------------------------------------------------------

@unittest.skipUnless(MCP_AVAILABLE, "mcp package required")
class TestStep2Validation(unittest.TestCase):
    """Parameter validation must return error dicts before calling the client."""

    def test_get_current_law_missing_all_ids(self):
        """get_current_law with no id/mst/jo must return MissingParamError."""
        result = _call_tool("get_current_law")  # id=None, mst=None, jo=None
        self.assertTrue(result.get("error"), msg=f"Expected error dict, got: {result}")
        self.assertEqual(result["error_type"], "MissingParamError")

    def test_list_apis_invalid_view(self):
        """list_apis with unsupported view must return InvalidParamError."""
        result = _call_tool("list_apis", view="NONSENSE")
        self.assertTrue(result.get("error"), msg=f"Expected error dict, got: {result}")
        self.assertEqual(result["error_type"], "InvalidParamError")

    def test_list_apis_minimal_view_is_invalid(self):
        """'minimal' is not a supported catalog view and must return InvalidParamError."""
        result = _call_tool("list_apis", view="minimal")
        self.assertTrue(result.get("error"), msg=f"Expected error dict, got: {result}")
        self.assertEqual(result["error_type"], "InvalidParamError")


# ---------------------------------------------------------------------------
# Step 4: _build_tool_description module-level helper
# ---------------------------------------------------------------------------

class TestStep4BuildToolDescription(unittest.TestCase):
    """_build_tool_description(spec) must be importable from mcp_server."""

    def _helper(self):
        import law_api_mcp_korea.mcp_server as mod
        if not hasattr(mod, "_build_tool_description"):
            self.fail("_build_tool_description not found in mcp_server module")
        return mod._build_tool_description

    def test_build_tool_description_basic(self):
        fn = self._helper()
        spec = {"title": "기본 도구", "description": None, "requires_agency": False, "requires_mode": False}
        result = fn(spec)
        self.assertIsInstance(result, str)
        self.assertIn("기본 도구", result)

    def test_build_tool_description_with_agency(self):
        fn = self._helper()
        spec = {"title": "기관 도구", "description": "기관 조회", "requires_agency": True, "requires_mode": False}
        result = fn(spec)
        self.assertIn("agency", result)

    def test_build_tool_description_with_mode(self):
        fn = self._helper()
        spec = {
            "title": "모드 도구",
            "description": "모드 조회",
            "requires_agency": False,
            "requires_mode": True,
            "modes": ["list", "info"],
        }
        result = fn(spec)
        self.assertIn("mode", result)


if __name__ == "__main__":
    unittest.main()
