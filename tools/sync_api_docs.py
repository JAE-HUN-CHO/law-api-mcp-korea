from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DOCS = ROOT / "api" / "docs"
PACKAGE_DOCS = ROOT / "src" / "law_api_mcp_korea" / "api_docs"
CATALOG_PATH = PACKAGE_DOCS / "catalog.json"

INDEX_FIELDS = (
    "index",
    "slug",
    "doc_key",
    "guide_html_name",
    "official_html_name",
    "official_html_names",
    "official_guide_url",
    "official_source",
    "official_list_titles",
    "title",
    "family",
    "filename",
    "stem",
    "guide_url",
    "endpoint",
    "base_url",
    "default_params",
    "description",
    "request_params",
    "supported_types",
    "sample_variants",
    "target_variants",
    "evidence",
)
DETAIL_FIELDS = (
    "request_params",
    "response_fields",
    "notes",
    "sample_requests",
    "sample_responses",
    "sample_variants",
    "target_variants",
)


def source_markdown_files(source_root: Path = SOURCE_DOCS) -> list[Path]:
    return sorted(
        path
        for path in source_root.rglob("*.md")
        if path.is_file() and path.name != "README.md"
    )


def nested_doc_to_flat_filename(path: Path, source_root: Path = SOURCE_DOCS) -> str:
    relative = path.relative_to(source_root)
    directories = list(relative.parts[:-1])

    if len(directories) < 2:
        return path.name

    parts = list(directories)
    if path.stem != directories[-1]:
        parts.append(path.stem)
    return "_".join(parts) + path.suffix


def load_raw_catalog(catalog_path: Path = CATALOG_PATH) -> dict:
    with catalog_path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def load_expected_filenames(catalog_path: Path = CATALOG_PATH) -> set[str]:
    data = load_raw_catalog(catalog_path)
    return {api["filename"] for api in data["apis"]}


def build_source_mapping(source_root: Path = SOURCE_DOCS) -> dict[Path, str]:
    mapping: dict[Path, str] = {}
    seen: dict[str, Path] = {}

    for path in source_markdown_files(source_root):
        filename = nested_doc_to_flat_filename(path, source_root)
        if filename in seen:
            raise RuntimeError(
                f"Duplicate flat filename generated: {filename}\n"
                f"- {seen[filename]}\n"
                f"- {path}"
            )
        mapping[path] = filename
        seen[filename] = path

    return mapping


def _index_api(api: dict) -> dict:
    payload = {field: api.get(field) for field in INDEX_FIELDS}
    payload["request_params"] = list(api.get("request_params", []))
    payload["default_params"] = dict(api.get("default_params", {}))
    return payload


def _detail_api(api: dict) -> dict:
    return {field: api.get(field, [] if field != "notes" else []) for field in DETAIL_FIELDS}


def _doc_key(api: dict) -> str:
    return str(api.get("doc_key") or api.get("slug") or api["guide_html_name"])


def write_split_metadata(package_root: Path = PACKAGE_DOCS) -> None:
    raw = load_raw_catalog(package_root / "catalog.json")
    index_payload = {
        "generated_at": raw.get("generated_at"),
        "source_zip": raw.get("source_zip"),
        "count": raw.get("count"),
        "families": raw.get("families", {}),
        "guide_list_displayed_count": raw.get("guide_list_displayed_count"),
        "official_list_item_count": raw.get("official_list_item_count"),
        "official_guide_count": raw.get("official_guide_count"),
        "apis": [_index_api(api) for api in raw.get("apis", [])],
    }
    (package_root / "catalog_index.json").write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    api_meta_root = package_root / "api_meta"
    api_meta_root.mkdir(parents=True, exist_ok=True)
    for path in api_meta_root.glob("*.json"):
        path.unlink()

    for api in raw.get("apis", []):
        target = api_meta_root / f"{_doc_key(api)}.json"
        target.write_text(
            json.dumps(_detail_api(api), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def sync_docs(source_root: Path = SOURCE_DOCS, package_root: Path = PACKAGE_DOCS) -> int:
    package_root.mkdir(parents=True, exist_ok=True)

    expected = load_expected_filenames(package_root / "catalog.json")
    mapping = build_source_mapping(source_root)
    actual = set(mapping.values())

    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details: list[str] = ["Source docs do not match packaged catalog."]
        if missing:
            details.append("Missing filenames:")
            details.extend(f"- {name}" for name in missing[:20])
        if extra:
            details.append("Extra filenames:")
            details.extend(f"- {name}" for name in extra[:20])
        raise RuntimeError("\n".join(details))

    for path in package_root.glob("*.md"):
        if path.name != "verification_report.md":
            path.unlink()

    for source_path, target_name in sorted(mapping.items(), key=lambda item: item[1]):
        shutil.copyfile(source_path, package_root / target_name)

    shutil.copyfile(source_root / "README.md", package_root / "README.md")
    write_split_metadata(package_root)
    return len(mapping)


def main(argv: list[str] | None = None) -> int:
    _ = argv
    copied = sync_docs()
    print(f"Synced {copied} API docs into {PACKAGE_DOCS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
