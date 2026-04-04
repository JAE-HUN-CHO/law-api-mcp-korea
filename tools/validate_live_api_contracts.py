from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from law_api_mcp_korea.catalog import all_apis, get_api_detail  # noqa: E402
from law_api_mcp_korea.client import LawOpenApiClient  # noqa: E402
from law_api_mcp_korea.live_sweep import (  # noqa: E402
    INVALID_API_KEY_TITLES,
    _pick_sample_request,
    recover_api_from_live_sample,
)

NORMALIZE_RE = re.compile(r"[^0-9A-Za-z가-힣]+")
COMMON_RESPONSE_FIELDS = {"resultcode", "resultmsg", "numofrows", "content"}
FIELD_ALIAS_PREFIXES = ("law", "admrul", "thdcmp", "oldandnew", "ordin", "ls", "jo")


def _normalize_name(value: str | None) -> str:
    return NORMALIZE_RE.sub("", value or "").lower()


def _alias_norms(value: str | None) -> set[str]:
    raw = (value or "").strip()
    if not raw:
        return set()

    aliases: set[str] = set()
    normalized = _normalize_name(raw)
    if normalized:
        aliases.add(normalized)

    if "=" in raw:
        left, _, right = raw.partition("=")
        left_norm = _normalize_name(left)
        right_norm = _normalize_name(right)
        if left_norm:
            aliases.add(left_norm)
        if right_norm:
            aliases.add(right_norm)

    if " " in raw:
        for token in raw.split():
            token_norm = _normalize_name(token)
            if token_norm:
                aliases.add(token_norm)

    expanded = list(aliases)
    for alias in expanded:
        for prefix in FIELD_ALIAS_PREFIXES:
            if alias.startswith(prefix) and len(alias) > len(prefix):
                aliases.add(alias[len(prefix) :])
        if alias.endswith("id"):
            aliases.add("id")
        if alias.endswith("num"):
            aliases.add("num")

    return aliases


def _iter_dicts(node: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    queue: list[Any] = [node]
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            items.append(current)
            queue.extend(current.values())
        elif isinstance(current, list):
            queue.extend(current)
    return items


def _collect_leaf_fields(node: Any, observed: dict[str, set[str]]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, (dict, list)):
                _collect_leaf_fields(value, observed)
            else:
                norm = _normalize_name(str(key))
                if norm:
                    observed.setdefault(norm, set()).add(str(key))
        return
    if isinstance(node, list):
        for item in node:
            _collect_leaf_fields(item, observed)


def _collect_observed_fields(data: Any, documented_norms: set[str]) -> dict[str, set[str]]:
    if isinstance(data, str):
        return {}

    matched_nodes: list[dict[str, Any]] = []
    all_nodes = _iter_dicts(data)
    for node in all_nodes:
        node_norms = {_normalize_name(str(key)) for key in node.keys()}
        if documented_norms and node_norms & documented_norms:
            matched_nodes.append(node)

    observed: dict[str, set[str]] = {}
    targets = matched_nodes if matched_nodes else all_nodes
    for node in targets:
        _collect_leaf_fields(node, observed)
    return observed


def _validate_request_contract(api: dict[str, Any], request_url: str) -> dict[str, Any]:
    query = parse_qs(urlparse(request_url).query, keep_blank_values=True)
    actual_keys = {key: _normalize_name(key) for key in query}
    actual_norms = set(actual_keys.values())
    documented_keys = {
        str(param.get("name")): _alias_norms(str(param.get("name")))
        for param in api.get("request_params", [])
    }
    documented_norms = {alias for aliases in documented_keys.values() for alias in aliases}

    undocumented_actual = sorted(
        key for key, norm in actual_keys.items() if norm and norm not in documented_norms
    )
    missing_required: list[str] = []
    conditionally_ignored_required: list[str] = []
    malformed_documented_keys = sorted(
        name for name in documented_keys if "=" in name or " " in name.strip()
    )
    for param in api.get("request_params", []):
        name = str(param.get("name"))
        aliases = documented_keys.get(name, set())
        if not aliases or not bool(param.get("required")):
            continue

        hints = f"{param.get('type_info', '')} {param.get('description', '')}"
        if "org 값 필수" in hints and "org" not in actual_norms:
            conditionally_ignored_required.append(name)
            continue
        if _normalize_name(name) == "efyd" and "id입력시에는무시" in _normalize_name(hints) and "id" in actual_norms:
            conditionally_ignored_required.append(name)
            continue
        if not (aliases & actual_norms):
            missing_required.append(name)

    untested_documented = sorted(
        name
        for name, aliases in documented_keys.items()
        if aliases and not (aliases & actual_norms)
    )

    return {
        "actual_keys": sorted(actual_keys.keys()),
        "documented_keys": sorted(documented_keys.keys()),
        "undocumented_actual_keys": undocumented_actual,
        "missing_required_keys": missing_required,
        "conditionally_ignored_required_keys": conditionally_ignored_required,
        "malformed_documented_keys": malformed_documented_keys,
        "untested_documented_keys": untested_documented,
        "ok": not undocumented_actual and not missing_required,
    }


def _validate_response_contract(api: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    documented_fields = [str(field.get("name")) for field in api.get("response_fields", []) if field.get("name")]
    documented_norms = {_normalize_name(name) for name in documented_fields if _normalize_name(name)}
    data = payload.get("data")
    response_type = str(payload.get("response_type") or "").upper()

    if isinstance(data, str):
        html_like = data.lstrip().startswith("<")
        return {
            "response_type": response_type,
            "mode": "text",
            "html_like": html_like,
            "text_length": len(data),
            "observed_fields": [],
            "matched_documented_fields": [],
            "ignored_common_fields": [],
            "observed_doc_gap_fields": [],
            "unobserved_documented_fields": documented_fields,
            "observed_documented_ok": True,
            "coverage_complete": False,
            "field_validation_skipped": True,
            "structured_without_documented_fields": False,
        }

    observed_map = _collect_observed_fields(data, documented_norms)
    observed_fields = sorted({name for names in observed_map.values() for name in names})
    observed_norms = {_normalize_name(name) for name in observed_fields if _normalize_name(name)}

    documented_aliases: dict[str, set[str]] = {}
    for name in documented_fields:
        for alias in _alias_norms(name):
            documented_aliases.setdefault(alias, set()).add(name)

    matched_documented_fields = sorted(
        {
            documented
            for observed_norm in observed_norms
            for documented in documented_aliases.get(observed_norm, set())
        }
    )
    ignored_common_fields = sorted(
        name for name in observed_fields if _normalize_name(name) in COMMON_RESPONSE_FIELDS
    )
    observed_doc_gap_fields = sorted(
        name
        for name in observed_fields
        if _normalize_name(name)
        and _normalize_name(name) not in COMMON_RESPONSE_FIELDS
        and _normalize_name(name) not in documented_aliases
    )
    unobserved_documented_fields = sorted(
        name for name in documented_fields if not (_alias_norms(name) & observed_norms)
    )
    structured_without_documented_fields = not documented_fields

    return {
        "response_type": response_type,
        "mode": "structured",
        "observed_fields": observed_fields,
        "matched_documented_fields": matched_documented_fields,
        "ignored_common_fields": ignored_common_fields,
        "observed_doc_gap_fields": observed_doc_gap_fields,
        "unobserved_documented_fields": unobserved_documented_fields,
        "observed_documented_ok": not observed_doc_gap_fields,
        "coverage_complete": not unobserved_documented_fields,
        "field_validation_skipped": False,
        "structured_without_documented_fields": structured_without_documented_fields,
    }


def _execute_api(client: LawOpenApiClient, api: dict[str, Any]) -> dict[str, Any]:
    sample_url, sample_params, response_type = _pick_sample_request(api)
    base_entry = {
        "title": api["title"],
        "guide_html_name": api["guide_html_name"],
        "family": api["family"],
        "sample_url": sample_url,
        "sample_params": sample_params,
        "sample_response_type": response_type,
    }

    try:
        payload = client.call_api(api["title"], params=sample_params, response_type=response_type)
        return {
            **base_entry,
            "status": "direct_ok",
            "request_url": payload["request_url"],
            "payload": payload,
        }
    except Exception as exc:
        if api["title"] in INVALID_API_KEY_TITLES:
            return {
                **base_entry,
                "status": "invalid_api_key",
                "error": str(exc),
            }
        try:
            recovered = recover_api_from_live_sample(client, api["title"])
            payload = recovered["payload"]
            return {
                **base_entry,
                "status": "recovered_ok",
                "request_url": payload["request_url"],
                "payload": payload,
                "recovery_strategy": recovered.get("strategy"),
                "recovered_params": recovered.get("recovered_params"),
                "list_api": recovered.get("list_api"),
                "list_params": recovered.get("list_params"),
                "list_response_type": recovered.get("list_response_type"),
            }
        except Exception as recovery_exc:
            return {
                **base_entry,
                "status": "unresolved",
                "error": str(exc),
                "recovery_error": str(recovery_exc),
            }


def build_live_contract_report() -> dict[str, Any]:
    client = LawOpenApiClient()
    entries: list[dict[str, Any]] = []

    summary = {
        "total": 0,
        "direct_ok": 0,
        "recovered_ok": 0,
        "invalid_api_key": 0,
        "unresolved": 0,
        "request_contract_ok": 0,
        "response_documented_ok": 0,
        "response_coverage_complete": 0,
        "response_field_validation_skipped": 0,
        "apis_with_request_doc_gaps": 0,
        "apis_with_response_doc_gaps": 0,
        "apis_with_unobserved_documented_fields": 0,
        "structured_apis_without_response_fields": 0,
    }

    for summary_api in all_apis():
        api = get_api_detail(summary_api)
        execution = _execute_api(client, api)
        entry: dict[str, Any] = {
            "title": execution["title"],
            "guide_html_name": execution["guide_html_name"],
            "family": execution["family"],
            "status": execution["status"],
            "sample_url": execution["sample_url"],
            "sample_response_type": execution["sample_response_type"],
        }
        summary["total"] += 1
        summary[execution["status"]] += 1

        if execution["status"] in {"invalid_api_key", "unresolved"}:
            entry["error"] = execution.get("error")
            if execution.get("recovery_error"):
                entry["recovery_error"] = execution.get("recovery_error")
            entries.append(entry)
            continue

        payload = execution["payload"]
        request_validation = _validate_request_contract(api, payload["request_url"])
        response_validation = _validate_response_contract(api, payload)

        entry["request_url"] = payload["request_url"]
        entry["response_type"] = payload["response_type"]
        entry["status_code"] = payload["status_code"]
        if execution.get("recovery_strategy"):
            entry["recovery_strategy"] = execution["recovery_strategy"]
        if execution.get("recovered_params"):
            entry["recovered_params"] = execution["recovered_params"]
        entry["request_validation"] = request_validation
        entry["response_validation"] = response_validation

        if request_validation["ok"]:
            summary["request_contract_ok"] += 1
        else:
            summary["apis_with_request_doc_gaps"] += 1

        if response_validation["field_validation_skipped"]:
            summary["response_field_validation_skipped"] += 1
        else:
            if response_validation["observed_documented_ok"]:
                summary["response_documented_ok"] += 1
            else:
                summary["apis_with_response_doc_gaps"] += 1

            if response_validation["coverage_complete"]:
                summary["response_coverage_complete"] += 1
            else:
                summary["apis_with_unobserved_documented_fields"] += 1

            if response_validation["structured_without_documented_fields"]:
                summary["structured_apis_without_response_fields"] += 1

        entries.append(entry)

    return {
        "meta": summary,
        "entries": entries,
    }


def _markdown_report(report: dict[str, Any]) -> str:
    meta = report["meta"]
    lines = [
        "# Live API Contract Validation",
        "",
        "## Summary",
        f"- total: **{meta['total']}**",
        f"- direct_ok: **{meta['direct_ok']}**",
        f"- recovered_ok: **{meta['recovered_ok']}**",
        f"- invalid_api_key: **{meta['invalid_api_key']}**",
        f"- unresolved: **{meta['unresolved']}**",
        f"- request_contract_ok: **{meta['request_contract_ok']}**",
        f"- response_documented_ok: **{meta['response_documented_ok']}**",
        f"- response_coverage_complete: **{meta['response_coverage_complete']}**",
        f"- response_field_validation_skipped: **{meta['response_field_validation_skipped']}**",
        f"- apis_with_request_doc_gaps: **{meta['apis_with_request_doc_gaps']}**",
        f"- apis_with_response_doc_gaps: **{meta['apis_with_response_doc_gaps']}**",
        f"- apis_with_unobserved_documented_fields: **{meta['apis_with_unobserved_documented_fields']}**",
        f"- structured_apis_without_response_fields: **{meta['structured_apis_without_response_fields']}**",
        "",
        "## Findings",
    ]

    request_issues = [entry for entry in report["entries"] if entry.get("request_validation", {}).get("ok") is False]
    response_doc_gaps = [
        entry
        for entry in report["entries"]
        if entry.get("response_validation", {}).get("observed_doc_gap_fields")
    ]
    unobserved_documented = [
        entry
        for entry in report["entries"]
        if entry.get("response_validation", {}).get("unobserved_documented_fields")
        and entry.get("response_validation", {}).get("field_validation_skipped") is False
    ]
    missing_response_docs = [
        entry
        for entry in report["entries"]
        if entry.get("response_validation", {}).get("structured_without_documented_fields")
    ]

    if not request_issues:
        lines.append("- request issues: none")
    else:
        for entry in request_issues[:20]:
            lines.append(
                f"- request doc gap: `{entry['title']}` -> undocumented={entry['request_validation']['undocumented_actual_keys']}, missing_required={entry['request_validation']['missing_required_keys']}"
            )

    if not response_doc_gaps:
        lines.append("- observed response fields outside docs: none")
    else:
        for entry in response_doc_gaps[:20]:
            lines.append(
                f"- response doc gap: `{entry['title']}` -> {entry['response_validation']['observed_doc_gap_fields']}"
            )

    if not unobserved_documented:
        lines.append("- unobserved documented fields in sampled payloads: none")
    else:
        for entry in unobserved_documented[:20]:
            missing = entry["response_validation"]["unobserved_documented_fields"][:10]
            lines.append(
                f"- sampled payload did not exercise documented fields: `{entry['title']}` -> {missing}"
            )

    if not missing_response_docs:
        lines.append("- structured APIs without response field docs: none")
    else:
        for entry in missing_response_docs[:20]:
            lines.append(f"- structured API without response docs: `{entry['title']}`")

    unresolved = [entry for entry in report["entries"] if entry["status"] == "unresolved"]
    if unresolved:
        lines.extend(["", "## Unresolved"])
        for entry in unresolved:
            lines.append(f"- `{entry['title']}` -> {entry.get('error')} / {entry.get('recovery_error')}")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run live contract validation across all 191 APIs.")
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-markdown", type=Path, default=None)
    args = parser.parse_args(argv)

    report = build_live_contract_report()

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(_markdown_report(report), encoding="utf-8")

    print(json.dumps(report["meta"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
