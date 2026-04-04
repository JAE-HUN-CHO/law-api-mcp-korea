from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


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


def _test_env() -> dict[str, str]:
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


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "law_api_mcp_korea.cli", *args],
        cwd=ROOT,
        env=_test_env(),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
    )


def _load_json(result: subprocess.CompletedProcess[str]) -> dict:
    if result.returncode != 0:
        raise AssertionError(f"CLI failed with code {result.returncode}: {result.stderr}")
    return json.loads(result.stdout)


class CliOfflineE2ETests(unittest.TestCase):
    def test_catalog_alias_json_summary(self):
        result = _run_cli("search-api", "--search", "법령해석", "--limit", "1", "--json", "--view", "summary")
        payload = _load_json(result)
        self.assertEqual(payload["count"], 1)
        self.assertIn("법령해석", payload["items"][0]["title"])

    def test_catalog_json_summary(self):
        result = _run_cli("catalog", "--search", "법령해석", "--limit", "3", "--json", "--view", "summary")
        payload = _load_json(result)
        self.assertGreaterEqual(payload["count"], 1)
        self.assertEqual(payload["meta"]["count"], 191)
        self.assertNotIn("request_params", payload["items"][0])

    def test_catalog_json_detail(self):
        result = _run_cli("catalog", "--search", "법령해석", "--limit", "1", "--json", "--view", "detail")
        payload = _load_json(result)
        self.assertIn("request_params", payload["items"][0])

    def test_doc_summary_json(self):
        result = _run_cli("doc", "cgmExpcMolegListGuide", "--view", "summary", "--json")
        payload = _load_json(result)
        self.assertEqual(payload["api"]["guide_html_name"], "cgmExpcMolegListGuide")
        self.assertEqual(payload["api"]["title"], "법제처 법령해석 목록 조회")
        self.assertNotIn("request_params", payload["api"])

    def test_doc_alias_summary_json(self):
        result = _run_cli("inspect-api", "cgmExpcMolegListGuide", "--view", "summary", "--json")
        payload = _load_json(result)
        self.assertEqual(payload["api"]["guide_html_name"], "cgmExpcMolegListGuide")

    def test_tool_doc_detail_contains_bai_note(self):
        result = _run_cli("tool-doc", "api_bai_pre_consultation", "--view", "detail")
        payload = _load_json(result)
        self.assertTrue(any("유효한 API key" in note for note in payload["notes"]))

    def test_examples_contains_workflow_commands(self):
        result = _run_cli("examples")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("law-openapi-cli search-api --search 법령해석", result.stdout)
        self.assertIn("law-openapi-cli doctor", result.stdout)

    def test_doctor_json(self):
        result = _run_cli("doctor", "--json")
        payload = _load_json(result)
        self.assertIn("python_executable", payload)
        self.assertIn("oc_configured", payload)
        self.assertIn("dotenv_found", payload)

    def test_build_url(self):
        result = _run_cli(
            "build-url",
            "cgmExpcMolegListGuide",
            "--oc",
            "test",
            "--param",
            "query=퇴직",
            "--param",
            "display=1",
        )
        if result.returncode != 0:
            raise AssertionError(f"CLI failed with code {result.returncode}: {result.stderr}")
        url = result.stdout.strip()
        self.assertIn("target=molegCgmExpc", url)
        self.assertIn("query=%ED%87%B4%EC%A7%81", url)
        self.assertIn("display=1", url)
        self.assertIn("OC=test", url)


@unittest.skipUnless(_configured_oc(), "LAW_API_OC is required for live CLI smoke tests")
class CliLiveE2ETests(unittest.TestCase):
    def test_search_law_json(self):
        result = _run_cli("search-law", "자동차관리법", "--type", "JSON")
        payload = _load_json(result)
        self.assertEqual(payload["status_code"], 200)
        self.assertIn("request_url", payload)
        self.assertIn("data", payload)

    def test_search_moleg_json(self):
        result = _run_cli("search-moleg", "퇴직", "--type", "JSON")
        payload = _load_json(result)
        self.assertEqual(payload["status_code"], 200)
        self.assertIn("request_url", payload)
        self.assertIn("data", payload)


if __name__ == "__main__":
    unittest.main()
