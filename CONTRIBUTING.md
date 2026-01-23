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
├── checks_odoo_module.py           # Main orchestrator
├── checks_odoo_module_csv.py       # CSV validations
├── checks_odoo_module_po.py        # PO/POT validations
├── checks_odoo_module_python.py    # Python validations
├── checks_odoo_module_xml.py       # Basic XML validations
├── checks_odoo_module_xml_advanced.py  # Advanced XML checks
├── checks_branch_name.py           # Branch naming validation
├── config_loader.py                # Configuration management
├── doc_coverage.py                 # Documentation coverage analysis
├── setup-repo.py                   # Initialize hooks in client repos
├── _pylintrc                       # Pylint config for Odoo
├── _pre-commit-config.yaml         # Pre-commit hooks template
├── _pre-commit-config-local.yaml   # Local pre-commit (monorepo)
├── _pre-commit-hooks.yaml          # Hook definitions
├── _solt-hooks.yaml                # Soltein validation settings
├── _solt-hooks-defaults.yaml       # Default hook settings
├── pyproject-base.toml             # Base Python tools config
├── ci.yml                          # Internal CI workflow
├── solt-validate.yml               # Reusable workflow for clients
└── README-template.md              # README template for client repos
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

5. Add the check to `_solt-hooks-defaults.yaml` if it needs configurable severity

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
ruff check .
ruff format .
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

1. Update version in:
   - `pyproject.toml`
   - `setup.py`
   - `__init__.py`

2. Update CHANGELOG.md

3. Create and push a git tag:
```bash
git tag v1.x.0
git push origin v1.x.0
```

4. The CI will automatically create a GitHub release

## Configuration Priority

1. `.solt-hooks.yaml` in client repo (highest priority)
2. `_solt-hooks-defaults.yaml` in solt-pre-commit (defaults)

## Questions?

Open an issue on GitHub or contact the maintainers at dev@soltein.mx.
