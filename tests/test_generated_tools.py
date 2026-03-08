from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from law_api_mcp_korea.generated_tools import (  # noqa: E402
    MissingRequiredToolParamError,
    UnsupportedAgencyModeError,
    UnsupportedModeError,
    all_generated_tools,
    generated_tool_metadata,
    get_generated_tool_doc,
    resolve_generated_tool,
    validate_generated_tool_call,
)


class GeneratedToolRegistryTests(unittest.TestCase):
    def test_metadata_counts(self) -> None:
        meta = generated_tool_metadata()
        self.assertEqual(meta["raw_api_count"], 191)
        self.assertEqual(meta["logical_count"], 115)
        self.assertEqual(meta["generated_count"], 65)

    def test_ministry_tool_doc(self) -> None:
        doc = get_generated_tool_doc("api_ministry_interpretation")
        self.assertTrue(doc["requires_agency"])
        self.assertEqual(set(doc["supported_modes"]), {"list", "info"})
        self.assertIn("moleg", {agency["code"] for agency in doc["supported_agencies"]})

    def test_bai_tool_summary_doc_contains_note(self) -> None:
        doc = get_generated_tool_doc("api_bai_pre_consultation", view="summary")
        self.assertTrue(any("유효한 API key" in note for note in doc["notes"]))

    def test_committee_tool_exists(self) -> None:
        tool = resolve_generated_tool("api_committee_decision")
        self.assertEqual(tool["kind"], "collapsed_pair")
        self.assertTrue(tool["requires_agency"])

    def test_special_tool_exists(self) -> None:
        tool = resolve_generated_tool("api_special_adjudication_case")
        self.assertEqual(tool["kind"], "collapsed_pair")
        self.assertIn("tt", {agency["code"] for agency in tool["supported_agencies"]})

    def test_ministry_list_selection(self) -> None:
        selection = validate_generated_tool_call(
            "api_ministry_interpretation",
            mode="list",
            agency="moel",
            params={"query": "퇴직", "display": 1},
        )
        self.assertEqual(selection["mode"], "list")
        self.assertEqual(selection["agency"]["code"], "moel")
        self.assertEqual(selection["api"]["guide_html_name"], "cgmExpcMoelListGuide")

    def test_ministry_info_unsupported_for_nts(self) -> None:
        with self.assertRaises(UnsupportedAgencyModeError) as ctx:
            validate_generated_tool_call(
                "api_ministry_interpretation",
                mode="info",
                agency="nts",
                params={"id": "1"},
            )
        self.assertIn("mode=list만 가능합니다", str(ctx.exception))

    def test_pair_mode_is_required(self) -> None:
        with self.assertRaises(MissingRequiredToolParamError) as ctx:
            validate_generated_tool_call(
                "api_ministry_interpretation",
                None,
                "moleg",
                params={"query": "퇴직"},
            )
        self.assertIn("mode가 필요합니다", str(ctx.exception))

    def test_single_tool_rejects_mode(self) -> None:
        single_name = next(
            tool["name"]
            for tool in all_generated_tools()
            if not tool["requires_mode"] and not tool["requires_agency"]
        )
        with self.assertRaises(UnsupportedModeError) as ctx:
            validate_generated_tool_call(single_name, "list", None, {})
        self.assertIn("mode를 받지 않습니다", str(ctx.exception))

    def test_agency_alias_resolves(self) -> None:
        selection = validate_generated_tool_call(
            "api_ministry_interpretation",
            mode="list",
            agency="고용노동부",
            params={"query": "퇴직", "display": 1},
        )
        self.assertEqual(selection["agency"]["code"], "moel")


if __name__ == "__main__":
    unittest.main()
