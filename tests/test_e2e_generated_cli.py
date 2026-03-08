from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ENV = os.environ.copy()
ENV["PYTHONUTF8"] = "1"
ENV["PYTHONPATH"] = str(SRC)


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


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "law_api_mcp_korea.cli", *args],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class GeneratedCliOfflineTests(unittest.TestCase):
    def test_tool_catalog_json(self) -> None:
        result = _run_cli("tool-catalog", "--json")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["meta"]["generated_count"], 65)

    def test_tool_doc_json(self) -> None:
        result = _run_cli("tool-doc", "api_ministry_interpretation")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["requires_agency"])

    def test_invalid_generated_call_fails_with_exit_code_2(self) -> None:
        result = _run_cli(
            "tool",
            "api_ministry_interpretation",
            "--agency",
            "nts",
            "--mode",
            "info",
            "--param",
            "id=1",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("mode=list만 가능합니다", result.stderr)


@unittest.skipUnless(_live_oc(), "LAW_API_OC is required for live E2E")
class GeneratedCliLiveTests(unittest.TestCase):
    def test_ministry_list_tool(self) -> None:
        result = _run_cli(
            "tool",
            "api_ministry_interpretation",
            "--agency",
            "moleg",
            "--mode",
            "list",
            "--type",
            "JSON",
            "--param",
            "query=퇴직",
            "--param",
            "display=1",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status_code"], 200)
        self.assertEqual(payload["tool"]["name"], "api_ministry_interpretation")


if __name__ == "__main__":
    unittest.main()
