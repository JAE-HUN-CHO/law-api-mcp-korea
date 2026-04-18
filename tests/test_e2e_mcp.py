from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import importlib.util
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None

if MCP_AVAILABLE:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from pydantic import AnyUrl


def _configured_oc() -> str | None:
    oc = os.getenv("LAW_API_OC")
    if oc:
        return oc
    dotenv_path = ROOT / ".env"
    if not dotenv_path.is_file():
        return None
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("LAW_API_OC="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _server_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    configured_oc = _configured_oc()
    if configured_oc:
        env["LAW_API_OC"] = configured_oc
    pythonpath = [str(SRC), str(ROOT)]
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    return env


@asynccontextmanager
async def _session():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "law_api_mcp_korea.mcp_server", "--transport", "stdio"],
        env=_server_env(),
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=20)
            yield session


@unittest.skipUnless(MCP_AVAILABLE, "mcp package is required for MCP stdio E2E tests")
class McpOfflineE2ETests(unittest.IsolatedAsyncioTestCase):
    async def test_list_tools(self):
        async with _session() as session:
            response = await asyncio.wait_for(session.list_tools(), timeout=20)
            names = {tool.name for tool in response.tools}
            self.assertIn("list_apis", names)
            self.assertIn("get_api_doc", names)
            self.assertIn("call_api", names)

    async def test_call_list_apis(self):
        async with _session() as session:
            result = await asyncio.wait_for(
                session.call_tool("list_apis", {"keyword": "법령해석", "limit": 3}),
                timeout=20,
            )
            self.assertFalse(result.isError)
            self.assertGreaterEqual(result.structuredContent["count"], 1)
            self.assertNotIn("request_params", result.structuredContent["items"][0])

    async def test_call_get_api_doc(self):
        async with _session() as session:
            result = await asyncio.wait_for(
                session.call_tool(
                    "get_api_doc",
                    {"api_name": "cgmExpcMolegListGuide", "include_markdown": False},
                ),
                timeout=20,
            )
            self.assertFalse(result.isError)
            self.assertEqual(
                result.structuredContent["api"]["guide_html_name"],
                "cgmExpcMolegListGuide",
            )
            self.assertNotIn("request_params", result.structuredContent["api"])

    async def test_call_get_api_doc_markdown_opt_in(self):
        async with _session() as session:
            result = await asyncio.wait_for(
                session.call_tool(
                    "get_api_doc",
                    {"api_name": "cgmExpcMolegListGuide", "view": "markdown"},
                ),
                timeout=20,
            )
            self.assertFalse(result.isError)
            self.assertIn("markdown", result.structuredContent)

    async def test_read_catalog_resource(self):
        async with _session() as session:
            resource = await asyncio.wait_for(
                session.read_resource(AnyUrl("lawdoc://catalog")),
                timeout=20,
            )
            first = resource.contents[0]
            self.assertIn('"count": 191', first.text)
            self.assertNotIn("request_params", first.text)


@unittest.skipUnless(
    MCP_AVAILABLE and bool(_configured_oc()),
    "mcp package and LAW_API_OC are required for live MCP smoke tests",
)
class McpLiveE2ETests(McpOfflineE2ETests):
    async def test_search_current_law(self):
        async with _session() as session:
            result = await asyncio.wait_for(
                session.call_tool(
                    "search_current_law",
                    {"query": "자동차관리법", "display": 1, "response_type": "JSON"},
                ),
                timeout=30,
            )
            self.assertFalse(result.isError)
            self.assertEqual(result.structuredContent["status_code"], 200)
            self.assertIn("data", result.structuredContent)

    async def test_search_moleg_interpretations(self):
        async with _session() as session:
            result = await asyncio.wait_for(
                session.call_tool(
                    "search_moleg_interpretations",
                    {"query": "퇴직", "display": 1, "response_type": "JSON"},
                ),
                timeout=30,
            )
            self.assertFalse(result.isError)
            self.assertEqual(result.structuredContent["status_code"], 200)
            self.assertIn("data", result.structuredContent)


if __name__ == "__main__":
    unittest.main()
