# Contributing to Solt Pre-commit

Thank you for your interest in contributing to solt-pre-commit!

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

## Project Structure

```
solt-pre-commit/
├── src/solt_pre_commit/          # Main package
│   ├── __init__.py
│   ├── checks_odoo_module.py           # Main orchestrator
│   ├── checks_odoo_module_csv.py       # CSV validations
│   ├── checks_odoo_module_po.py        # PO/POT validations
│   ├── checks_odoo_module_python.py    # Python validations
│   ├── checks_odoo_module_xml.py       # Basic XML validations
│   ├── checks_odoo_module_xml_advanced.py  # Advanced XML checks
│   ├── checks_branch_name.py           # Branch naming validation
│   └── config_loader.py                # Configuration management
├── configs/                      # Default configurations for client repos
│   ├── .pylintrc                 # Pylint config for Odoo
│   ├── pyproject-base.toml       # Python tools config (ruff, black, isort, pytest)
│   └── .solt-hooks-defaults.yaml # Default hook settings
├── templates/                    # Templates copied to client repos
│   ├── .pre-commit-config.yaml
│   ├── .pre-commit-config-local.yaml   # For monorepo setup
│   ├── .solt-hooks.yaml
│   └── github-workflows/
│       └── solt_validate.yml
├── scripts/                      # Setup utilities
│   ├── setup-repo.py             # Initialize hooks in a repo
│   ├── sync-configs.py           # Sync configs across repos
│   └── generate-badges.py        # Generate documentation badges
├── .github/workflows/
│   ├── ci.yml                    # Internal CI for this repo
│   └── solt-validate.yml         # Reusable workflow for client repos
└── tests/                        # Test suite
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

5. Add the check to `.solt-hooks-defaults.yaml` if it needs configurable severity

## Severity Levels

| Level | Usage | Blocks by Default |
|-------|-------|-------------------|
| `error` | Syntax errors, duplicates, runtime warnings | ✅ Yes |
| `warning` | Deprecated patterns, dangerous code, missing attributes | ❌ No (configurable) |
| `info` | Code style suggestions, best practices | ❌ No |

## Testing

Run tests locally:
```bash
pytest tests/ -v
```

Test against a real Odoo module:
```bash
# Basic validation
solt-check-odoo /path/to/odoo-module

# Show all issues including info
solt-check-odoo /path/to/odoo-module --show-info

# Force full repository validation
solt-check-odoo /path/to/odoo-module --scope full
```

Test branch name validation:
```bash
solt-check-branch feature/SOLT-123-my-feature
solt-check-branch invalid-branch  # Should fail
```

## Code Style

- Follow PEP 8 with max line length of 120
- Use type hints where practical
- Document public methods with docstrings
- Run checks before committing:
```bash
ruff check src/ scripts/
ruff format src/ scripts/
```

## Client Repository Setup

To test the setup process:
```bash
# Create a test directory
mkdir /tmp/test-odoo-module
cd /tmp/test-odoo-module

# Initialize with solt-pre-commit
python /path/to/solt-pre-commit/scripts/setup-repo.py .

# Verify files created
ls -la
# Should show: pyproject.toml, .pylintrc, .solt-hooks.yaml, .pre-commit-config.yaml
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

1. Update version in all locations:
   - `pyproject.toml`
   - `setup.py`
   - `src/solt_pre_commit/__init__.py`

2. Update CHANGELOG.md

3. Create and push a git tag:
```bash
git tag v1.x.0
git push origin v1.x.0
```

4. The CI will automatically create a GitHub release

## Files Reference

### Client Repository Files

When `setup-repo.py` runs, it creates these files in the client repo:

| File | Source | Purpose                                 |
|------|--------|-----------------------------------------|
| `pyproject.toml` | `configs/pyproject-base.toml` | Ruff, black, isort, pytest, mypy config |
| `.pylintrc` | `configs/.pylintrc` | Pylint-odoo configuration               |
| `.solt-hooks.yaml` | `templates/.solt-hooks.yaml` | Soltein validation settings             |
| `.pre-commit-config.yaml` | `templates/.pre-commit-config.yaml` | Pre-commit hooks                        |
| `.github/workflows/solt_validate.yml` | `templates/github-workflows/solt_validate.yml` | CI workflow                             |

### Configuration Priority

1. `.solt-hooks.yaml` in client repo (highest priority)
2. `.solt-hooks-defaults.yaml` in solt-pre-commit (defaults)

## Questions?

Open an issue on GitHub or contact the maintainers at dev@soltein.mx.