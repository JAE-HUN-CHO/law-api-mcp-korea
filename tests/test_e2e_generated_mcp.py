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


def _live_oc() -> str | None:
    value = os.getenv("LAW_API_OC")
    if value:
        return value
    dotenv_path = ROOT / ".env"
    if not dotenv_path.exists():
        return None
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw = stripped.split("=", 1)
        if key.strip() == "LAW_API_OC":
            return raw.strip().strip('"').strip("'")
    return None


def _server_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    configured_oc = _live_oc()
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


@unittest.skipUnless(MCP_AVAILABLE, "mcp package is required")
class GeneratedMcpOfflineTests(unittest.IsolatedAsyncioTestCase):
    async def test_generated_tools_visible(self) -> None:
        async with _session() as session:
            tools = await asyncio.wait_for(session.list_tools(), timeout=20)
            names = {tool.name for tool in tools.tools}
            self.assertIn("api_ministry_interpretation", names)

    async def test_generated_tool_catalog(self) -> None:
        async with _session() as session:
            result = await asyncio.wait_for(
                session.call_tool("list_generated_tools", {"keyword": "ministry", "limit": 10}),
                timeout=20,
            )
            self.assertFalse(result.isError)
            self.assertIn("api_ministry_interpretation", result.content[0].text)

    async def test_generated_tool_doc(self) -> None:
        async with _session() as session:
            result = await asyncio.wait_for(
                session.call_tool(
                    "get_generated_tool_doc",
                    {"tool_name": "api_ministry_interpretation"},
                ),
                timeout=20,
            )
            self.assertFalse(result.isError)
            self.assertIn("requires_agency", result.content[0].text)

    async def test_generated_bai_tool_doc_contains_note(self) -> None:
        async with _session() as session:
            result = await asyncio.wait_for(
                session.call_tool(
                    "get_generated_tool_doc",
                    {"tool_name": "api_bai_pre_consultation"},
                ),
                timeout=20,
            )
            self.assertFalse(result.isError)
            self.assertIn("유효한 API key", result.content[0].text)


@unittest.skipUnless(MCP_AVAILABLE and bool(_live_oc()), "mcp package and LAW_API_OC are required")
class GeneratedMcpLiveTests(unittest.IsolatedAsyncioTestCase):
    async def test_generated_live_call(self) -> None:
        async with _session() as session:
            result = await asyncio.wait_for(
                session.call_tool(
                    "api_ministry_interpretation",
                    {
                        "agency": "moleg",
                        "mode": "list",
                        "params": {"query": "퇴직", "display": 1},
                        "response_type": "JSON",
                    },
                ),
                timeout=30,
            )
            self.assertFalse(result.isError)
            self.assertIn('"status_code": 200', result.content[0].text)

    async def test_generated_bai_live_error(self) -> None:
        async with _session() as session:
            result = await asyncio.wait_for(
                session.call_tool(
                    "api_bai_pre_consultation",
                    {
                        "mode": "list",
                        "params": {"target": "baiPvcs", "query": "계약", "search": 1, "display": 1, "page": 1},
                        "response_type": "JSON",
                    },
                ),
                timeout=30,
            )
            self.assertTrue(result.isError)
            self.assertIn("유효한 API key", result.content[0].text)


if __name__ == "__main__":
    unittest.main()
