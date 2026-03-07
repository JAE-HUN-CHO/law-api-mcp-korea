from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DOCS = ROOT / "api" / "docs"
PACKAGE_DOCS = ROOT / "src" / "law_api_mcp_korea" / "api_docs"
CATALOG_PATH = PACKAGE_DOCS / "catalog.json"


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


def load_expected_filenames(catalog_path: Path = CATALOG_PATH) -> set[str]:
    with catalog_path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
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

    return len(mapping)


def main(argv: list[str] | None = None) -> int:
    _ = argv
    copied = sync_docs()
    print(f"Synced {copied} API docs into {PACKAGE_DOCS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
