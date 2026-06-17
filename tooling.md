# Python Tooling Guide

**Stack: uv + pyright + ruff**

---

## uv — Package & Environment Manager

uv replaces pip, pip-tools, virtualenv, and pyenv for this project.

### Project Setup

```bash
# Create a new project
uv init my-project
cd my-project

# Pin Python version
uv python pin 3.14

# Add dependencies
uv add httpx
uv add --dev pytest pytest-asyncio

# Sync the environment (install all deps from lockfile)
uv sync

# Run a command inside the managed environment
uv run python main.py
uv run pytest
```

### pyproject.toml (minimum required fields)

```toml
[project]
name = "my-project"
version = "0.1.0"
requires-python = ">=3.14"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pyright>=1.1",
    "ruff>=0.5",
]
```

### Key Commands

| Command | Purpose |
|---|---|
| `uv sync` | Install all deps from lockfile |
| `uv add <pkg>` | Add a runtime dependency |
| `uv add --dev <pkg>` | Add a dev dependency |
| `uv remove <pkg>` | Remove a dependency |
| `uv lock` | Regenerate the lockfile |
| `uv run <cmd>` | Run a command in the project environment |
| `uv python pin 3.14` | Pin the Python version |

Always commit both `pyproject.toml` and `uv.lock`.

---

## pyright — Type Checker

Run in strict mode. Strict mode enables all type checks and disallows implicit `Any`.

### Configuration in pyproject.toml

```toml
[tool.pyright]
pythonVersion = "3.14"
typeCheckingMode = "strict"
reportMissingTypeStubs = false      # suppress noise for stubs-less packages
reportUnknownMemberType = false     # can be noisy in strict; enable when ready
venvPath = "."
venv = ".venv"
```

### Running pyright

```bash
uv run pyright                  # check entire project
uv run pyright src/module.py    # check a single file
```

### CI Gate

Pyright must pass with zero errors before a PR can merge. A single `# type: ignore` suppression requires an inline comment explaining why:

```python
result = external_lib.do_thing()  # type: ignore[no-any-return]  # no stubs available
```

### Common Strict-Mode Pitfalls

- All function parameters and return types must be annotated — pyright will error on missing annotations in strict mode
- `dict[str, object]` not `dict[str, Any]` — use `object` when the value type is genuinely unknown and you don't need to call methods on it
- Use `cast()` sparingly; prefer narrowing via `match`, `isinstance`, or `TypeIs` guards

---

## ruff — Linter & Formatter

ruff replaces flake8, isort, pyupgrade, and black. It is the single tool for all code style enforcement.

### Configuration in pyproject.toml

```toml
[tool.ruff]
target-version = "py314"
line-length = 88

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "UP",   # pyupgrade — enforces modern syntax (flags legacy typing imports)
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions — enforces comprehension usage
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking — moves type-only imports into TYPE_CHECKING blocks
    "PGH",  # pygrep-hooks
    "RUF",  # ruff-specific rules
]
ignore = [
    "E501",  # line length — handled by formatter
]

[tool.ruff.lint.isort]
known-first-party = ["my_project"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### The `UP` and `C4` rules directly enforce this style guide

- `UP006` / `UP007` — flags `List[...]`, `Dict[...]`, `Optional[...]`, `Union[...]` and auto-fixes them
- `C400`–`C417` — flags imperative list/dict/set construction and suggests comprehensions

### Running ruff

```bash
uv run ruff check .             # lint
uv run ruff check --fix .       # lint and auto-fix
uv run ruff format .            # format
uv run ruff format --check .    # format check (for CI)
```

### CI Gate

Both `ruff check` and `ruff format --check` must pass with zero findings.

---

## Putting It Together — CI Workflow

A minimal CI script (e.g. GitHub Actions step or local pre-commit):

```bash
uv sync
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

Run the same commands locally before pushing:

```bash
uv run ruff format . && uv run ruff check --fix . && uv run pyright && uv run pytest
```

---

## Editor Integration

**VS Code**
- Install the [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance) extension (uses pyright under the hood)
- Install the [Ruff](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff) extension
- Set Ruff as the default formatter and enable format-on-save

```json
{
  "editor.defaultFormatter": "charliermarsh.ruff",
  "editor.formatOnSave": true,
  "python.analysis.typeCheckingMode": "strict"
}
```

**JetBrains (PyCharm)**
- Install the [Ruff plugin](https://plugins.jetbrains.com/plugin/20574-ruff)
- Pyright can be run as an external tool or via the [Pyright plugin](https://plugins.jetbrains.com/plugin/24145-pyright)
