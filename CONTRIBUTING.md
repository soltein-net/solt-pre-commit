# Contributing to Solt Pre-commit

Thank you for your interest in contributing to solt-pre-commit!

- [Contributing to Solt Pre-commit](#contributing-to-solt-pre-commit)
  - [Development Setup](#development-setup)
  - [Adding a New Check](#adding-a-new-check)
  - [Severity Levels](#severity-levels)
  - [Testing](#testing)
  - [Code Style](#code-style)
  - [Pull Request Process](#pull-request-process)
    - [Commit Message Format](#commit-message-format)
  - [Releasing](#releasing)
  - [Configuration Priority](#configuration-priority)
  - [Questions?](#questions)


## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/soltein-net/solt-pre-commit.git
cd solt-pre-commit
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install in development mode:
```bash
pip install -e ".[dev]"
```

4. Install pre-commit hooks:
```bash
pre-commit install
```

## Adding a New Check

1. Identify the appropriate module for your check:
   - `checks_odoo_module_xml.py` for XML-related checks
   - `checks_odoo_module_xml_advanced.py` for complex XML patterns
   - `checks_odoo_module_python.py` for Python code checks
   - `checks_odoo_module_csv.py` for CSV file checks
   - `checks_odoo_module_po.py` for translation file checks

2. Add your check method following the pattern:
```python
def check_my_new_check(self):
    """Description of what this check validates."""
    for manifest_data in self.manifest_datas:
        # Your validation logic here
        if problem_found:
            self.checks_errors["my_new_check_id"].append(
                f"{manifest_data['filename']}:{line_number} Description of the issue"
            )
```

3. Register the check ID with a default severity in `DEFAULT_SEVERITY` dict in `config_loader.py`:
```python
DEFAULT_SEVERITY = {
    # ... existing checks ...
    "my_new_check_id": Severity.WARNING,  # or ERROR, INFO
}
```

4. Update the README.md to document the new check

5. Add the check to `templates/.solt-hooks.yaml` (the config template `setup-repo.py` installs into client repos) if it needs configurable severity

## Severity Levels

| Level | Usage | Blocks by Default |
|-------|-------|-------------------|
| `error` | Syntax errors, duplicates, runtime warnings | ✅ Yes |
| `warning` | Deprecated patterns, dangerous code, missing attributes | ❌ No (configurable) |
| `info` | Code style suggestions, best practices | ❌ No |

## Testing

Run the unit test suite:
```bash
pytest tests/ -v
pytest tests/ --cov=solt_pre_commit --cov-report=html   # with coverage
```

Verify a change against a real module - create a scratch one if you don't have a handy target:
```bash
mkdir -p test_module
cat > test_module/__manifest__.py << 'EOF'
{
    "name": "Test Module",
    "version": "17.0.1.0.0",
    "depends": ["base"],
    "installable": True,
}
EOF

solt-check-odoo test_module
solt-check-branch feature/SOLT-123-my-feature
```

See the main [README's CLI Usage](README.md#-cli-usage) section for the full
flag reference (`--show-info`, `--scope full`, etc.).

## Code Style

- Follow PEP 8 with max line length of 120
- Use type hints where practical
- Document public methods with docstrings
- Run the same lint + format check CI runs before committing:
```bash
scripts/lint.sh          # check only - fails on any violation, same as CI
scripts/lint.sh --fix    # auto-fix + reformat in place
```

## Pull Request Process

1. Create a feature branch: `feature/SOLT-XXX-description`
2. Make your changes with clear commit messages
3. Update documentation if needed
4. Ensure all tests pass
5. Submit PR with description of changes

### Commit Message Format

```
[TAG] component: brief description

Detailed explanation if needed.

Fixes #123
```

Tags: `[IMP]` improvement, `[FIX]` bugfix, `[ADD]` new feature, `[REM]` removal, `[REF]` refactor, `[DOC]` documentation

## Releasing

Version is derived automatically from the git tag (via `setuptools_scm`) -
there's nothing to hand-edit in `pyproject.toml` or `__init__.py` anymore.

1. Bump the `SOLT_PRE_COMMIT_VERSION` self-install pin
   (`pip install "git+...@vX.Y.Z"`) in **all three** reusable workflows
   - `.github/workflows/solt-validate.yml`,
   - `solt-coverage.yml`,
   - and `solt-update-badges.yml`

   Each carries its own identical env block, and
   it's the one version reference that can't be derived automatically since
   these are workflows referencing themselves.

   Missing any one of the three
   leaves that workflow silently running an older release even for
   consumers pinned to the new tag (`uses: ...@vX.Y.Z` only selects which
   *workflow file* runs - `SOLT_PRE_COMMIT_VERSION` inside it separately
   controls which *package release* gets installed).

2. Create and push a git tag:
```bash
git tag v1.x.0
git push origin v1.x.0
```

1. Everyone consuming this repo picks up the new version by running
   `setup-repo.py --update-only --batch repos.txt` against their own repos
   (or `--update-only` for a single repo) - it re-derives the current
   version from this repo's latest tag and stamps it into each consumer's
   `.pre-commit-config.yaml` / `solt-validate.yml`.

2. The CI will automatically create a GitHub release

## Configuration Priority

1. `.solt-hooks.yaml` in the client repo (highest priority)
2. `DEFAULT_SEVERITY` / `DEFAULT_SKIP_*` dicts in `src/solt_pre_commit/config_loader.py` (built-in defaults)

`templates/.solt-hooks.yaml` is the file `setup-repo.py` copies into a new client repo as its starting point — it mirrors the code defaults but is a template, not a second source of truth read at runtime.

## Questions?

Open an issue on GitHub or contact the maintainers at dev@soltein.mx.
