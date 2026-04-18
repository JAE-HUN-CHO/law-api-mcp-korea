from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache
from typing import Any

from .catalog import all_apis, normalize_text, summarize_api

LIST_SUFFIX = " 목록 조회"
INFO_SUFFIX = " 본문 조회"
PAIR_MODES = ("list", "info")
MODE_ALIASES = {
    "list": "list",
    "info": "info",
    "목록": "list",
    "본문": "info",
}


class GeneratedToolError(RuntimeError):
    def __init__(self, message: str, candidates: list[str] | None = None) -> None:
        super().__init__(message)
        self.candidates = candidates or []


class GeneratedToolNotFoundError(GeneratedToolError):
    """Raised when a generated tool cannot be resolved."""


class UnsupportedModeError(GeneratedToolError):
    """Raised when the selected tool does not support the requested mode."""


class UnsupportedAgencyError(GeneratedToolError):
    """Raised when the selected tool does not support the requested agency."""


class UnsupportedAgencyModeError(GeneratedToolError):
    """Raised when a generated tool does not support the agency/mode pair."""


class MissingRequiredToolParamError(GeneratedToolError):
    """Raised when required generated-tool arguments are missing."""


def _camel_to_snake(value: str) -> str:
    value = re.sub(r"(?<!^)(?=[A-Z])", "_", value)
    value = re.sub(r"[^0-9A-Za-z]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_").lower()


def _base_title(title: str) -> str:
    for suffix in (LIST_SUFFIX, INFO_SUFFIX):
        if title.endswith(suffix):
            return title[: -len(suffix)]
    return title


def _is_pair(apis: list[dict[str, Any]]) -> bool:
    titles = {api["title"] for api in apis}
    return (
        len(apis) == 2
        and any(title.endswith(LIST_SUFFIX) for title in titles)
        and any(title.endswith(INFO_SUFFIX) for title in titles)
    )


def _pair_api_for_mode(apis: list[dict[str, Any]], mode: str) -> dict[str, Any] | None:
    suffix = LIST_SUFFIX if mode == "list" else INFO_SUFFIX
    for api in apis:
        if api["title"].endswith(suffix):
            return api
    return None


def _strip_pair_guide_name(guide_html_name: str) -> str:
    for suffix in ("ListGuide", "InfoGuide"):
        if guide_html_name.endswith(suffix):
            return guide_html_name[: -len(suffix)]
    return guide_html_name


def _strip_single_guide_name(guide_html_name: str) -> str:
    if guide_html_name.endswith("Guide"):
        return guide_html_name[:-5]
    return guide_html_name


def _tool_name_for_pair(guide_html_name: str) -> str:
    return "api_" + _camel_to_snake(_strip_pair_guide_name(guide_html_name))


def _tool_name_for_single(guide_html_name: str) -> str:
    return "api_" + _camel_to_snake(_strip_single_guide_name(guide_html_name))


def _visible_request_params(api: dict[str, Any]) -> list[dict[str, Any]]:
    hidden = set(api.get("default_params", {}))
    hidden.update({"OC", "type"})
    return [param for param in api.get("request_params", []) if param.get("name") not in hidden]


def _required_param_names(api: dict[str, Any]) -> list[str]:
    return [param["name"] for param in _visible_request_params(api) if param.get("required")]


def _mode_doc(api: dict[str, Any], mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "api": summarize_api(api),
        "representative_params": _visible_request_params(api),
        "required_params": _required_param_names(api),
    }


def _sorted_modes(mode_map: dict[str, Any]) -> list[str]:
    return [mode for mode in PAIR_MODES if mode in mode_map]


def _display_family(logical_tool: dict[str, Any]) -> str:
    families = logical_tool["source_families"]
    return families[0] if len(families) == 1 else "logical"


def _normalize_mode(mode: str | None) -> str | None:
    if mode is None:
        return None
    normalized = MODE_ALIASES.get(mode.strip().lower())
    if normalized:
        return normalized
    normalized = MODE_ALIASES.get(mode.strip())
    return normalized


def _list_to_message(values: list[str]) -> str:
    return ", ".join(values)


def _agency_aliases(code: str, label: str) -> list[str]:
    return [
        code,
        code.lower(),
        normalize_text(code),
        normalize_text(label),
    ]


def _summarize_agency(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": entry["code"],
        "label": entry["label"],
        "supported_modes": list(entry["supported_modes"]),
    }


def _logical_tool_doc(logical_tool: dict[str, Any], *, name_override: str | None = None) -> dict[str, Any]:
    doc = {
        "name": name_override or logical_tool["name"],
        "kind": logical_tool["kind"],
        "title": logical_tool["title"],
        "family": _display_family(logical_tool),
        "source_families": logical_tool["source_families"],
        "source_api_count": len(logical_tool["apis"]),
        "requires_mode": logical_tool["kind"] == "pair",
        "requires_agency": False,
        "supported_modes": list(logical_tool["supported_modes"]),
        "supported_agencies": [],
        "agency_mode_exceptions": [],
        "notes": _tool_notes(logical_tool["apis"]),
    }
    if logical_tool["kind"] == "pair":
        doc["modes"] = {
            mode: _mode_doc(api, mode)
            for mode, api in logical_tool["mode_to_api"].items()
        }
    else:
        doc["api"] = summarize_api(logical_tool["api"])
        doc["representative_params"] = _visible_request_params(logical_tool["api"])
        doc["required_params"] = _required_param_names(logical_tool["api"])
    return doc


def _build_logical_registry() -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for api in all_apis():
        grouped[_base_title(api["title"])].append(api)

    logical_tools: list[dict[str, Any]] = []
    for base_title, apis in grouped.items():
        apis = sorted(apis, key=lambda item: item.get("index", 0))
        families = sorted({api["family"] for api in apis})
        if _is_pair(apis):
            list_api = _pair_api_for_mode(apis, "list")
            info_api = _pair_api_for_mode(apis, "info")
            assert list_api is not None and info_api is not None
            logical_tools.append(
                {
                    "id": base_title,
                    "name": _tool_name_for_pair(list_api["guide_html_name"]),
                    "kind": "pair",
                    "title": base_title,
                    "source_families": families,
                    "supported_modes": ["list", "info"],
                    "mode_to_api": {
                        "list": list_api,
                        "info": info_api,
                    },
                    "apis": apis,
                    "sort_index": min(api.get("index", 0) for api in apis),
                }
            )
        else:
            api = apis[0]
            logical_tools.append(
                {
                    "id": base_title,
                    "name": _tool_name_for_single(api["guide_html_name"]),
                    "kind": "single",
                    "title": api["title"],
                    "source_families": families,
                    "supported_modes": [],
                    "api": api,
                    "apis": apis,
                    "sort_index": api.get("index", 0),
                }
            )

    logical_tools.sort(key=lambda item: item["sort_index"])
    return logical_tools


def _build_agency_entry(code: str, label: str, sort_index: int) -> dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "supported_modes": [],
        "modes": {},
        "aliases": _agency_aliases(code, label),
        "sort_index": sort_index,
    }


def _add_agency_mode(
    agencies: dict[str, dict[str, Any]],
    *,
    code: str,
    label: str,
    mode: str,
    api: dict[str, Any],
) -> None:
    entry = agencies.setdefault(code, _build_agency_entry(code=code, label=label, sort_index=api.get("index", 0)))
    entry["modes"][mode] = api
    entry["supported_modes"] = _sorted_modes(entry["modes"])
    entry["sort_index"] = min(entry["sort_index"], api.get("index", 0))


def _build_collapsed_doc(
    *,
    name: str,
    title: str,
    source_families: list[str],
    agencies: dict[str, dict[str, Any]],
    sort_index: int,
) -> dict[str, Any]:
    agency_items = sorted(agencies.values(), key=lambda item: (item["sort_index"], item["label"]))
    mode_examples: dict[str, dict[str, Any]] = {}
    for mode in PAIR_MODES:
        for agency in agency_items:
            api = agency["modes"].get(mode)
            if api:
                mode_examples[mode] = _mode_doc(api, mode)
                break

    return {
        "name": name,
        "kind": "collapsed_pair",
        "title": title,
        "family": "collapsed",
        "source_families": source_families,
        "source_api_count": sum(len(agency["modes"]) for agency in agency_items),
        "requires_mode": True,
        "requires_agency": True,
        "supported_modes": ["list", "info"],
        "supported_agencies": [_summarize_agency(agency) for agency in agency_items],
        "notes": _tool_notes([api for agency in agency_items for api in agency["modes"].values()]),
        "agency_mode_exceptions": [
            {
                "code": agency["code"],
                "label": agency["label"],
                "supported_modes": list(agency["supported_modes"]),
                "message": (
                    f"{agency['label']} {title}은 "
                    f"mode={_list_to_message(list(agency['supported_modes']))}만 가능합니다."
                ),
            }
            for agency in agency_items
            if list(agency["supported_modes"]) != ["list", "info"]
        ],
        "modes": mode_examples,
        "agencies": agency_items,
        "sort_index": sort_index,
    }


def _ministry_agency_code(api: dict[str, Any]) -> str:
    target = str(api.get("default_params", {}).get("target") or "")
    match = re.match(r"(?P<code>.+)CgmExpc$", target)
    return match.group("code").lower() if match else target.lower()


def _committee_agency_code(api: dict[str, Any]) -> str:
    return str(api.get("default_params", {}).get("target") or "").lower()


def _special_agency_code(api: dict[str, Any]) -> str:
    target = str(api.get("default_params", {}).get("target") or "")
    match = re.match(r"(?P<code>.+)SpecialDecc$", target)
    return match.group("code").lower() if match else target.lower()


def _ministry_label(api: dict[str, Any]) -> str:
    title = api["title"]
    for suffix in (" 법령해석 목록 조회", " 법령해석 본문 조회"):
        if title.endswith(suffix):
            return title[: -len(suffix)]
    return title


def _committee_label(api: dict[str, Any]) -> str:
    title = api["title"]
    for suffix in (" 결정문 목록 조회", " 결정문 본문 조회"):
        if title.endswith(suffix):
            return title[: -len(suffix)]
    return title


def _special_label(api: dict[str, Any]) -> str:
    title = api["title"]
    for suffix in (
        " 특별행정심판례 목록 조회",
        " 특별행정심판례 본문 조회",
        " 특별행정심판재결례 목록 조회",
        " 특별행정심판재결례 본문 조회",
    ):
        if title.endswith(suffix):
            return title[: -len(suffix)]
    return title


def _build_collapsed_registry(logical_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ministry_bases = {
        logical["id"]
        for logical in logical_tools
        if set(logical["source_families"]).issubset({"ministry_list", "ministry_info"})
    }
    committee_bases = {
        logical["id"]
        for logical in logical_tools
        if logical["source_families"] == ["committee_single"]
    }
    audit_bases = {
        logical["id"]
        for logical in logical_tools
        if logical["source_families"] == ["special"]
        and any("감사원 사전컨설팅 의견서" in api["title"] for api in logical["apis"])
    }
    special_case_bases = {
        logical["id"]
        for logical in logical_tools
        if logical["source_families"] == ["special"] and logical["id"] not in audit_bases
    }

    generated: list[dict[str, Any]] = []
    consumed_ids = ministry_bases | committee_bases | audit_bases | special_case_bases

    if ministry_bases:
        agencies: dict[str, dict[str, Any]] = {}
        sort_index = min(logical["sort_index"] for logical in logical_tools if logical["id"] in ministry_bases)
        for logical in logical_tools:
            if logical["id"] not in ministry_bases:
                continue
            for api in logical["apis"]:
                code = _ministry_agency_code(api)
                label = _ministry_label(api)
                mode = "list" if api["family"] == "ministry_list" else "info"
                _add_agency_mode(agencies, code=code, label=label, mode=mode, api=api)
        generated.append(
            _build_collapsed_doc(
                name="api_ministry_interpretation",
                title="중앙부처 법령해석",
                source_families=["ministry_list", "ministry_info"],
                agencies=agencies,
                sort_index=sort_index,
            )
        )

    if committee_bases:
        agencies = {}
        sort_index = min(logical["sort_index"] for logical in logical_tools if logical["id"] in committee_bases)
        for logical in logical_tools:
            if logical["id"] not in committee_bases:
                continue
            for api in logical["apis"]:
                code = _committee_agency_code(api)
                label = _committee_label(api)
                mode = "list" if api["title"].endswith(LIST_SUFFIX) else "info"
                _add_agency_mode(agencies, code=code, label=label, mode=mode, api=api)
        generated.append(
            _build_collapsed_doc(
                name="api_committee_decision",
                title="위원회 결정문",
                source_families=["committee_single"],
                agencies=agencies,
                sort_index=sort_index,
            )
        )

    if special_case_bases:
        agencies = {}
        sort_index = min(logical["sort_index"] for logical in logical_tools if logical["id"] in special_case_bases)
        for logical in logical_tools:
            if logical["id"] not in special_case_bases:
                continue
            for api in logical["apis"]:
                code = _special_agency_code(api)
                label = _special_label(api)
                mode = "list" if api["title"].endswith(LIST_SUFFIX) else "info"
                _add_agency_mode(agencies, code=code, label=label, mode=mode, api=api)
        generated.append(
            _build_collapsed_doc(
                name="api_special_adjudication_case",
                title="특별행정심판례/재결례",
                source_families=["special"],
                agencies=agencies,
                sort_index=sort_index,
            )
        )

    if audit_bases:
        logical = next(item for item in logical_tools if item["id"] in audit_bases)
        generated.append(_logical_tool_doc(logical, name_override="api_bai_pre_consultation"))

    for logical in logical_tools:
        if logical["id"] in consumed_ids:
            continue
        generated.append(_logical_tool_doc(logical))

    generated.sort(key=lambda item: item.get("sort_index", 0))
    return generated


@lru_cache(maxsize=1)
def load_generated_tool_registry() -> dict[str, Any]:
    logical_tools = _build_logical_registry()
    generated_tools = _build_collapsed_registry(logical_tools)
    return {
        "raw_api_count": len(all_apis()),
        "logical_tools": logical_tools,
        "generated_tools": generated_tools,
        "logical_count": len(logical_tools),
        "generated_count": len(generated_tools),
    }


def generated_tool_metadata() -> dict[str, Any]:
    registry = load_generated_tool_registry()
    return {
        "raw_api_count": registry["raw_api_count"],
        "logical_count": registry["logical_count"],
        "generated_count": registry["generated_count"],
    }


def all_generated_tools() -> list[dict[str, Any]]:
    return list(load_generated_tool_registry()["generated_tools"])


def summarize_generated_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": tool["name"],
        "kind": tool["kind"],
        "title": tool["title"],
        "family": tool["family"],
        "source_families": tool.get("source_families", []),
        "source_api_count": tool.get("source_api_count", 0),
        "requires_mode": tool.get("requires_mode", False),
        "requires_agency": tool.get("requires_agency", False),
        "supported_modes": tool.get("supported_modes", []),
        "supported_agency_count": len(tool.get("supported_agencies", [])),
    }


def _tool_notes(apis: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    targets = {str(api.get("default_params", {}).get("target") or "").strip() for api in apis}
    titles = {str(api.get("title") or "").strip() for api in apis}
    if "lsHistory" in targets or "법령 연혁 본문 조회" in titles:
        notes.append("법령 연혁 본문 조회는 현재 lsHistory target의 HTML 형식만 안정적으로 지원합니다.")
    if "baiPvcs" in targets:
        notes.append("감사원 사전컨설팅 의견서 API는 현재 `유효한 API key가 아닙니다` 스타일 오류로 표준화됩니다.")
    return notes


def summarize_generated_tool_doc(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": tool["name"],
        "kind": tool["kind"],
        "title": tool["title"],
        "family": tool["family"],
        "source_families": tool.get("source_families", []),
        "source_api_count": tool.get("source_api_count", 0),
        "requires_mode": tool.get("requires_mode", False),
        "requires_agency": tool.get("requires_agency", False),
        "supported_modes": tool.get("supported_modes", []),
        "supported_agencies": tool.get("supported_agencies", []),
        "agency_mode_exceptions": tool.get("agency_mode_exceptions", []),
        "notes": tool.get("notes", []),
    }


def search_generated_tools(keyword: str = "", limit: int = 100) -> list[dict[str, Any]]:
    query = normalize_text(keyword)
    items: list[dict[str, Any]] = []
    for tool in all_generated_tools():
        haystack = " ".join(
            [
                tool["name"],
                tool["title"],
                tool.get("family", ""),
                " ".join(
                    f"{agency['code']} {agency['label']}"
                    for agency in tool.get("supported_agencies", [])
                ),
            ]
        )
        if query and query not in normalize_text(haystack):
            continue
        items.append(tool)
    return items[: max(1, limit)]


def resolve_generated_tool(tool_name: str) -> dict[str, Any]:
    query = (tool_name or "").strip()
    if not query:
        raise GeneratedToolNotFoundError("tool 이름이 비어 있습니다.")

    items = all_generated_tools()
    for tool in items:
        if tool["name"] == query:
            return tool

    query_norm = normalize_text(query)
    exact = [tool for tool in items if normalize_text(tool["name"]) == query_norm]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise GeneratedToolNotFoundError(
            f"tool 식별자가 모호합니다: {query}",
            candidates=[tool["name"] for tool in exact[:10]],
        )

    contains = [
        tool
        for tool in items
        if query_norm in normalize_text(" ".join([tool["name"], tool["title"]]))
    ]
    if len(contains) == 1:
        return contains[0]
    if contains:
        raise GeneratedToolNotFoundError(
            f"tool 식별자가 모호합니다: {query}",
            candidates=[tool["name"] for tool in contains[:10]],
        )

    raise GeneratedToolNotFoundError(f"생성된 tool을 찾을 수 없습니다: {query}")


def get_generated_tool_doc(tool_name: str, view: str = "detail") -> dict[str, Any]:
    tool = resolve_generated_tool(tool_name)
    if view == "summary":
        return summarize_generated_tool_doc(tool)
    if view == "detail":
        return tool
    raise GeneratedToolError(f"지원하지 않는 tool view입니다: {view}")


def _resolve_agency_entry(tool: dict[str, Any], agency: str | None) -> dict[str, Any]:
    if not tool.get("requires_agency"):
        if agency:
            raise UnsupportedAgencyError("이 tool은 agency를 받지 않습니다.")
        raise UnsupportedAgencyError("이 tool은 agency를 사용하지 않습니다.")

    if not agency or not agency.strip():
        sample = tool["supported_agencies"][0]["code"] if tool["supported_agencies"] else "agency-code"
        raise MissingRequiredToolParamError(f"이 tool은 agency가 필요합니다. 예: --agency {sample}")

    query = agency.strip()
    query_norm = normalize_text(query)
    for entry in tool["agencies"]:
        if query.lower() == entry["code"] or query_norm in entry["aliases"]:
            return entry

    allowed = [entry["code"] for entry in tool["supported_agencies"]]
    raise UnsupportedAgencyError(
        f"지원하지 않는 기관입니다: {query}. 허용 기관: {_list_to_message(allowed)}"
    )


def _resolve_mode(tool: dict[str, Any], mode: str | None) -> str | None:
    if tool.get("requires_mode"):
        if not mode or not mode.strip():
            raise MissingRequiredToolParamError(
                f"이 tool은 mode가 필요합니다. 허용값: {_list_to_message(list(tool['supported_modes']))}"
            )
        normalized = _normalize_mode(mode)
        if not normalized or normalized not in tool["supported_modes"]:
            raise UnsupportedModeError(
                f"지원하지 않는 mode입니다: {mode}. 허용값: {_list_to_message(list(tool['supported_modes']))}"
            )
        return normalized

    if mode and mode.strip():
        raise UnsupportedModeError("이 tool은 mode를 받지 않습니다.")
    return None


def _validate_required_api_params(api: dict[str, Any], params: dict[str, Any]) -> None:
    missing = []
    for name in _required_param_names(api):
        if name not in params:
            missing.append(name)
            continue
        value = params[name]
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(name)
    if missing:
        raise MissingRequiredToolParamError(
            f"필수 파라미터가 없습니다: {_list_to_message(missing)}. params에 해당 키를 넣으세요."
        )


def validate_generated_tool_call(
    tool_name: str,
    mode: str | None,
    agency: str | None,
    params: dict[str, Any] | None,
) -> dict[str, Any]:
    tool = resolve_generated_tool(tool_name)
    if params is not None and not isinstance(params, dict):
        raise GeneratedToolError("params는 JSON object 형태여야 합니다.")
    payload = dict(params or {})
    selected_mode = _resolve_mode(tool, mode)

    if tool.get("requires_agency"):
        agency_entry = _resolve_agency_entry(tool, agency)
        api = agency_entry["modes"].get(selected_mode)
        if not api:
            raise UnsupportedAgencyModeError(
                f"{agency_entry['label']} {tool['title']}은 "
                f"mode={_list_to_message(list(agency_entry['supported_modes']))}만 가능합니다."
            )
        _validate_required_api_params(api, payload)
        return {
            "tool": tool,
            "mode": selected_mode,
            "agency": _summarize_agency(agency_entry),
            "api": api,
            "params": payload,
        }

    if tool["kind"] == "pair":
        api = tool["modes"][selected_mode]["api"]
        _validate_required_api_params(api, payload)
        return {
            "tool": tool,
            "mode": selected_mode,
            "agency": None,
            "api": api,
            "params": payload,
        }

    api = tool["api"]
    _validate_required_api_params(api, payload)
    return {
        "tool": tool,
        "mode": None,
        "agency": None,
        "api": api,
        "params": payload,
    }
