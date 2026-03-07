from __future__ import annotations

import os
from pathlib import Path


def _find_dotenv(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def load_dotenv(override: bool = False) -> Path | None:
    dotenv_path = _find_dotenv()
    if dotenv_path is None:
        return None

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value

    return dotenv_path


def save_dotenv_value(key: str, value: str, dotenv_path: Path | None = None) -> Path:
    path = dotenv_path or _find_dotenv() or (Path.cwd() / ".env")
    lines: list[str] = []
    replaced = False

    if path.is_file():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith(f"{key}="):
                lines.append(f"{key}={value}")
                replaced = True
            else:
                lines.append(raw_line)

    if not replaced:
        lines.append(f"{key}={value}")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    os.environ[key] = value
    return path
