from __future__ import annotations

import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from law_api_mcp_korea.client import LawOpenApiClient  # noqa: E402


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


@unittest.skipUnless(_live_oc(), "LAW_API_OC is required for live sweep")
class LiveSweepE2ETests(unittest.TestCase):
    def test_live_sweep_counts(self) -> None:
        client = LawOpenApiClient()
        payload = client.run_live_sweep()
        self.assertEqual(payload["meta"]["total"], 191)
        self.assertEqual(payload["meta"]["direct_ok"], 108)
        self.assertEqual(payload["meta"]["recovered_ok"], 81)
        self.assertEqual(payload["meta"]["invalid_api_key"], 2)
        self.assertEqual(payload["meta"]["unresolved"], 0)
        self.assertNotIn("external_unavailable", payload["meta"])


if __name__ == "__main__":
    unittest.main()
