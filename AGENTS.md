# ClaudeSync – Coding Agent Brief

## Repository Overview
- Core Python package lives under `src/claudesync/` with orchestration in `syncmanager.py`, two-way sync flows in `workspace_manager.py`, and per-project helpers such as `project_instructions.py`.
- CLI entry point is Click-based (`claudesync` / `csync`) with nested command groups in `src/claudesync/cli/`; `docs/reference/commands.md` tracks the v2 hierarchy and newer utilities like `auth refresh`, `chat export`, and JSON table output.
- GUI code ships in `src/claudesync/gui/` (CustomTkinter). Alternate prototypes remain in `gui-simple/` for comparison and are launched via `python -m scripts.launch_gui --variant simple`.
- Obsidian integration lives in `obsidian-plugin/claudesync-plugin/` (TypeScript/Node build output) and is kept separate from the Python package.
- `.memory-bank/claude_ai.endpoints.openapi.yaml` captures the reverse-engineered Claude endpoints powering sync flows; keep it aligned with any API shape changes.

## Build & Test Workflow
- Create a dev environment with `pip install -r requirements.txt` followed by `pip install -e .`. Extras: `pip install -e .[gui]` for CustomTkinter UI, `pip install -e .[browser]` for Playwright/Selenium flows.
- Run `pytest` or `pytest -v --cov=claudesync --cov-report=term-missing` from the repo root; discovery is configured via `pytest.ini`.
- GUI smoke tests live under `src/claudesync/gui/` and can be exercised with `python -m scripts.launch_gui` plus `--deps-only` for dependency setup.

## Tooling & Scripts
- `python -m scripts.workspace_tools` exposes workspace migration and repair helpers used when syncing many projects locally.
- `scripts/ClaudeSync_GUI.bat` and `scripts/launch_gui_debug.*` provide Windows launchers for support/debug scenarios.
- Tests rely on fixtures in `tests/mock_http_server.py`; keep them in sync when updating provider contracts.

## Documentation Pointers
- Architecture notes: `docs/architecture/gui-implementation.md` for GUI design, `docs/guides/` for auth and GUI walkthroughs, `docs/reference/git-like-commands.md` plus `commands.md` for CLI deep dives.
- `.memory-bank/progress.md` records the 2025-08 v2 refactor (aliased command groups, new subcommands, JSON formatting). Use it when aligning future changes with the refactor goals.
- `TODO.md` tracks outstanding cleanup tasks; review before large refactors.

## Coding Standards & Practices
- Target Python 3.10+, run `python -m black src tests` before committing, and follow the existing type-hint usage (public entry points documented with docstrings).
- Preserve command aliases exposed via the `AliasedGroup` infrastructure when touching CLI modules.
- README currently contains mojibake characters from a bad encoding round-trip; plan to clean this as part of future documentation work.

## Testing Expectations
- Maintain or improve coverage from the default pytest command; add targeted tests under `tests/` mirroring affected modules (`test_file_config_manager.py`, `test_utils.py`, etc.).
- For GUI or CLI regressions, capture manual repro steps in PR notes and update docs if new flags or commands are introduced.

