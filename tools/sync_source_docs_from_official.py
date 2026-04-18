from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.sync_api_docs import build_source_mapping  # noqa: E402

CATALOG_PATH = ROOT / "src" / "law_api_mcp_korea" / "api_docs" / "catalog.json"
SOURCE_ROOT = ROOT / "api" / "docs"


def _replace_section(text: str, section_no: int, title: str, body: str) -> str:
    pattern = re.compile(
        rf"## {section_no}\. {re.escape(title)}\s*\n.*?(?=\n## {section_no + 1}\. )",
        flags=re.S,
    )
    replacement = f"## {section_no}. {title}\n{body.rstrip()}\n"
    updated, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise ValueError(f"섹션 {section_no}. {title} 를 찾지 못했습니다.")
    return updated


def _replace_request_examples(text: str, sample_requests: list[str]) -> str:
    lines = ["#### 요청 예시"]
    for index, url in enumerate(sample_requests, start=1):
        query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
        response_type = str(query.get("type") or "").upper().strip()
        label = response_type if response_type else "RAW"
        lines.extend(
            [
                f"- 예시 {index} ({label})",
                "```text",
                url,
                "```",
            ]
        )
    replacement = "\n".join(lines).rstrip() + "\n"
    pattern = re.compile(r"#### 요청 예시\s*\n.*?(?=\n#### 응답 예시)", flags=re.S)
    updated, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise ValueError("요청 예시 블록을 찾지 못했습니다.")
    return updated


def _collapse_extra_sample_subsections(text: str) -> str:
    pattern = re.compile(r"(## 샘플 요청 및 응답 예시\s*\n.*?)(?=\n## 8\. 메타)", flags=re.S)
    match = pattern.search(text)
    if not match:
        return text

    section = match.group(1)
    subsection_matches = list(re.finditer(r"\n### ", section))
    if len(subsection_matches) <= 1:
        return text

    collapsed = section[: subsection_matches[1].start()].rstrip() + "\n"
    return text[: match.start(1)] + collapsed + text[match.end(1) :]


def _request_params_table(api: dict) -> str:
    lines = [
        "| 변수명 | 타입/필수 여부 | 설명 |",
        "| --- | --- | --- |",
    ]
    for param in api.get("request_params", []):
        lines.append(
            f"| {param.get('name', '')} | {param.get('type_info', '')} | {param.get('description', '')} |"
        )
    return "\n".join(lines)


def _response_fields_table(api: dict) -> str:
    lines = [
        "| 필드명 | 타입 | 설명 |",
        "| --- | --- | --- |",
    ]
    response_fields = list(api.get("response_fields", []) or [])
    if not response_fields:
        supported = "/".join(api.get("supported_types", []) or ["HTML"])
        lines.append(
            f"| 응답 본문 | {supported} | 공식 가이드는 개별 응답 필드 명세표를 제공하지 않음 |"
        )
        return "\n".join(lines)
    for field in response_fields:
        lines.append(
            f"| {field.get('name', '')} | {field.get('type_info', '')} | {field.get('description', '')} |"
        )
    return "\n".join(lines)


def sync_source_docs_from_official() -> int:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    by_filename = {api["filename"]: api for api in catalog["apis"]}
    mapping = build_source_mapping(SOURCE_ROOT)

    updated_count = 0
    for source_path, filename in mapping.items():
        api = by_filename[filename]
        guide_url = str(api.get("official_guide_url") or api.get("guide_url") or "").strip()
        endpoint = str(api.get("endpoint") or "").strip()
        sample_requests = [str(url) for url in api.get("sample_requests", []) or [] if str(url).strip()]
        if not guide_url or not endpoint or not sample_requests:
            continue

        text = source_path.read_text(encoding="utf-8")
        text = _replace_section(text, 2, "가이드 페이지 URL", f"- {guide_url}")
        text = _replace_section(text, 3, "요청 URL (Endpoint)", f"- {endpoint}")
        text = _replace_section(text, 4, "요청 변수 (Request Parameters) 명세표", _request_params_table(api))
        text = _replace_section(text, 5, "출력 결과 (Response Elements) 명세표", _response_fields_table(api))
        text = _replace_request_examples(text, sample_requests)
        text = _collapse_extra_sample_subsections(text)
        source_path.write_text(text, encoding="utf-8")
        updated_count += 1
    return updated_count


def main(argv: list[str] | None = None) -> int:
    _ = argv
    updated = sync_source_docs_from_official()
    print(f"Updated {updated} source docs from official guide snapshot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
