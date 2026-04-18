# Repository Guidelines

## Project Structure & Module Organization
This repository is a Python package built from `src/`:
- `src/law_api_mcp_korea/`: core runtime code (`cli.py`, `client.py`, `mcp_server.py`, catalog/tool helpers).
- `src/law_api_mcp_korea/api_docs/`: packaged API docs and metadata used at runtime.
- `api/docs/`: human-maintained source docs (authoritative source).
- `tools/sync_api_docs.py`: syncs `api/docs/**` into packaged `src/.../api_docs/`.
- `tests/`: `unittest` test suite (`test_*.py`).

Keep generated/build artifacts out of commits (`build/`, `dist/`, `*.egg-info/`, `.env` are ignored).

## Build, Test, and Development Commands
Use Python 3.10+.

```bash
pip install -e .
python -m unittest discover -s tests -p "test_*.py"
python tools/sync_api_docs.py
python -m build --sdist --wheel
```

- `pip install -e .`: editable local development install.
- `unittest discover`: runs all tests (live API smoke tests skip automatically without `LAW_API_OC`).
- `sync_api_docs.py`: required after editing `api/docs/`.
- `python -m build`: creates release artifacts in `dist/`.

## Coding Style & Naming Conventions
Follow existing Python conventions:
- 4-space indentation, PEP 8 style, and type hints on public interfaces.
- `snake_case` for modules/functions/variables, `PascalCase` for classes, `UPPER_CASE` for constants/env keys.
- Keep CLI/MCP messages and errors explicit and user-actionable.

No repo-enforced formatter/linter is configured; match surrounding style in touched files.

## Testing Guidelines
- Framework: standard library `unittest`.
- File naming: `tests/test_*.py`; test methods/classes should start with `test_` / `*Tests`.
- Prefer offline, deterministic unit tests; mock network calls (see `tests/test_client.py`).
- When changing API docs packaging or generated behavior, add/adjust end-to-end tests in `tests/test_e2e_*.py`.

## Commit & Pull Request Guidelines
Recent history uses short, imperative commit subjects (e.g., `Add ...`, `Use ...`).
- Keep commits focused and atomic.
- In PRs, include: change summary, why it is needed, test evidence (exact command), and any API/env impact.
- Link related issues and include CLI/MCP output snippets when behavior changes.

## Security & Configuration Tips
- Set `LAW_API_OC` via environment variable or local `.env`; never commit secrets.
- Optional env vars: `LAW_API_TIMEOUT`, `LAW_API_FORCE_HTTPS`.
- Public distribution is GitHub Releases assets (`.whl`/`.tar.gz`), not PyPI.
