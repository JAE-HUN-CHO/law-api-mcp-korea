from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from law_api_mcp_korea.official_guides import (  # noqa: E402
    SNAPSHOT_PATH,
    augment_catalog_with_official_fields,
    fetch_official_guides,
)

CATALOG_PATH = ROOT / "src" / "law_api_mcp_korea" / "api_docs" / "catalog.json"


def sync_official_guides() -> dict[str, int | None]:
    snapshot = fetch_official_guides()
    SNAPSHOT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with CATALOG_PATH.open("r", encoding="utf-8") as fp:
        catalog = json.load(fp)
    augmented = augment_catalog_with_official_fields(catalog, snapshot)
    CATALOG_PATH.write_text(
        json.dumps(augmented, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "guide_list_displayed_count": snapshot.get("guide_list_displayed_count"),
        "official_list_item_count": int(snapshot["official_list_item_count"]),
        "official_guide_count": int(snapshot["official_guide_count"]),
        "catalog_count": int(augmented["count"]),
    }


def main(argv: list[str] | None = None) -> int:
    _ = argv
    summary = sync_official_guides()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
