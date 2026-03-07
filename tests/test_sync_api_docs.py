from __future__ import annotations

import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from tools.sync_api_docs import nested_doc_to_flat_filename, source_markdown_files  # noqa: E402


class SyncApiDocsTests(unittest.TestCase):
    def test_nested_doc_to_flat_filename(self):
        source_root = ROOT / "api" / "docs"
        sample = source_root / "관련법령" / "조회" / "조회.md"
        self.assertEqual(
            nested_doc_to_flat_filename(sample, source_root),
            "관련법령_조회.md",
        )

    def test_source_docs_match_catalog_filenames(self):
        source_root = ROOT / "api" / "docs"
        catalog_path = ROOT / "src" / "law_api_mcp_korea" / "api_docs" / "catalog.json"

        generated = {
            nested_doc_to_flat_filename(path, source_root)
            for path in source_markdown_files(source_root)
        }

        with catalog_path.open("r", encoding="utf-8") as fp:
            catalog = json.load(fp)

        expected = {api["filename"] for api in catalog["apis"]}
        self.assertEqual(generated, expected)
        self.assertEqual(len(generated), 191)

    def test_packaged_docs_match_catalog(self):
        package_root = ROOT / "src" / "law_api_mcp_korea" / "api_docs"
        catalog_path = package_root / "catalog.json"

        with catalog_path.open("r", encoding="utf-8") as fp:
            catalog = json.load(fp)

        expected = {api["filename"] for api in catalog["apis"]}
        actual = {
            path.name
            for path in package_root.glob("*.md")
            if path.name not in {"README.md", "verification_report.md"}
        }

        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 191)


if __name__ == "__main__":
    unittest.main()
