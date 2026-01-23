# Solt Pre-commit

[![CI](https://github.com/soltein-net/solt-pre-commit/workflows/CI/badge.svg)](https://github.com/soltein-net/solt-pre-commit/actions)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Odoo 17.0-19.0](https://img.shields.io/badge/odoo-17.0--19.0-purple.svg)](https://www.odoo.com/)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL%20v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![PyPI version](https://badge.fury.io/py/solt-pre-commit.svg)](https://badge.fury.io/py/solt-pre-commit)

Custom pre-commit hooks for Odoo module validation with comprehensive documentation coverage analysis. Catches errors and runtime warnings **before** starting the server.

**Supports Odoo 17.0, 18.0, and 19.0** with automatic version detection.

---

## ðŸ“‹ Supported Versions

| Odoo Version | Python | Status |
|--------------|--------|--------|
| 17.0 | 3.10+ | Fully Supported |
| 18.0 | 3.10+ | Fully Supported |
| 19.0 | 3.11+ | Fully Supported |

---

## 🚀 Quick Start

### For New Repositories

```bash
# Clone solt-pre-commit
git clone https://github.com/soltein-net/solt-pre-commit.git

# Setup your Odoo repository (auto-detects version)
python solt-pre-commit/scripts/setup-repo.py /path/to/your-odoo-repo

# Or specify version explicitly
python solt-pre-commit/scripts/setup-repo.py /path/to/your-odoo-repo --odoo-version 18.0

# Batch setup multiple repos
python solt-pre-commit/scripts/setup-repo.py --batch solt-pre-commit/scripts/repos.txt

# Done! The script creates all necessary files
```

### For Existing Repositories

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/soltein-net/solt-pre-commit
    rev: v1.0.0  # Supports Odoo 17.0, 18.0, 19.0
    hooks:
      - id: solt-check-branch
      - id: solt-check-odoo
```

Install and run:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## Features

### Comprehensive Validation

| Check Type | Description | Blocks PR |
|------------|-------------|-----------|
| **Branch Names** | Enforces naming conventions | âœ… |
| **Odoo Runtime Warnings** | Detects issues before server start | âœ… |
| **XML Validations** | Syntax, duplicates, deprecations | âœ… |
| **Python Quality** | Docstrings, field attributes | Configurable |
| **CSV/PO Files** | Duplicate IDs, translation errors | âœ… |
| **Documentation Coverage** | Detailed reports with trends | â„¹ï¸ Informative |

### Configuration

```yaml
# .solt-hooks.yaml
validation_scope: changed  # or 'full'

severity:
  python_field_missing_string: warning
  python_method_missing_docstring: warning

skip_docstring_methods:
  - create
  - write
```

### ðŸ”„ Centralized Workflows

Use our reusable GitHub Actions workflow:

```yaml
# .github/workflows/validate.yml
jobs:
  validate:
    uses: soltein-net/solt-pre-commit/.github/workflows/solt-validate.yml@v1.0.0
    with:
      validation-scope: 'changed'
      fail-on-warnings: false
```

---

## Available Hooks

| Hook ID | Description | Use Case |
|---------|-------------|----------|
| `solt-check-branch` | Branch naming validation | All repos |
| `solt-check-odoo` | Full module validation | Primary hook |
| `solt-check-xml` | XML files only | Targeted checks |
| `solt-check-csv` | CSV files only | Data validation |
| `solt-check-po` | Translation files only | i18n checks |
| `solt-check-python` | Python files only | Code quality |

---

## Odoo Runtime Warnings Detected

Catches these Odoo warnings **before** they appear in your logs:

| Odoo Warning | Check Name |
|--------------|------------|
| `Two fields have the same label` | `python_duplicate_field_label` |
| `inconsistent 'compute_sudo'` | `python_inconsistent_compute_sudo` |
| `tracking value will be ignored` | `python_tracking_without_mail_thread` |
| `selection attribute will be ignored` | `python_selection_on_related` |
| `Using active_id is deprecated` | `xml_deprecated_active_id_usage` |
| `Alert must have role` | `xml_alert_missing_role` |

---

## All Validation Checks

<details>
<summary><strong> Python Checks</strong></summary>

### Runtime Errors (Block)
- `python_duplicate_field_label` - Same label on multiple fields
- `python_inconsistent_compute_sudo` - Inconsistent compute_sudo
- `python_tracking_without_mail_thread` - tracking without inheritance
- `python_selection_on_related` - Selection on related fields

### Documentation (Configurable)
- `python_field_missing_string` - Fields without string attribute
- `python_field_missing_help` - Fields without help text
- `python_method_missing_docstring` - Methods without docstring
- `python_docstring_too_short` - Docstrings < 10 chars
- `python_docstring_uninformative` - Generic docstrings

</details>

<details>
<summary><strong> XML Checks</strong></summary>

### Errors (Block)
- `xml_syntax_error` - XML parse errors
- `xml_duplicate_record_id` - Duplicate record IDs
- `xml_duplicate_fields` - Duplicate field definitions
- `xml_deprecated_active_id_usage` - Deprecated active_id usage
- `xml_alert_missing_role` - Alert without role attribute

### Warnings
- `xml_deprecated_tree_attribute` - Deprecated tree attributes
- `xml_hardcoded_id` - Hardcoded IDs instead of ref()
- `xml_create_user_wo_reset_password` - User creation issue
- `xml_dangerous_filter_wo_user` - Filter without user_id

</details>

<details>
<summary><strong> CSV Checks</strong></summary>

- `csv_syntax_error` - CSV parse errors
- `csv_duplicate_record_id` - Duplicate XML IDs

</details>

<details>
<summary><strong> PO/POT Checks</strong></summary>

- `po_syntax_error` - Translation file errors
- `po_duplicate_message_definition` - Duplicate translations
- `po_requires_module` - Missing module comment
- `po_python_parse_printf` - Printf variable errors
- `po_python_parse_format` - Format string errors

</details>

---

## Configuration

### Odoo Version

Configure the Odoo version (auto-detected by default):

```yaml
# .solt-hooks.yaml
odoo_version: auto  # Auto-detect from manifest (default)
# odoo_version: 17.0  # Force specific version
# odoo_version: 18.0
# odoo_version: 19.0
```

Or via command line:
```bash
solt-check-odoo /path/to/module --odoo-version 18.0
```

Or via environment variable:
```bash
export SOLT_ODOO_VERSION=18.0
solt-check-odoo /path/to/module
```

### Validation Scope

Control what gets validated:

```yaml
# .solt-hooks.yaml
validation_scope: changed  # Only validate modified files (recommended for legacy)
# validation_scope: full   # Validate all files
```

### Severity Customization

```yaml
# .solt-hooks.yaml
severity:
  # Make docstring checks non-blocking
  python_method_missing_docstring: info
  python_docstring_too_short: info

  # Make field attributes blocking
  python_field_missing_string: error
```

### Skip Lists

```yaml
# .solt-hooks.yaml
skip_string_fields:
  - active
  - name
  - sequence

skip_help_fields:
  - active
  - name

skip_docstring_methods:
  - create
  - write
  - unlink
```

### Branch Naming

```yaml
branch_naming:
  strict: true  # Requires ticket: feature/SOLT-123-description
  # strict: false  # Allows: feature/description

  ticket_prefixes:
    - SOLT
    - PROJ

  allowed_types:
    - feature
    - fix
    - hotfix
    - refactor
```

---

## CLI Usage

```bash
# Validate module
solt-check-odoo /path/to/module

# Force full validation (ignore scope config)
solt-check-odoo /path/to/module --scope full

# Show info-level issues
solt-check-odoo /path/to/module --show-info

# Validate branch name
solt-check-branch feature/SOLT-123-my-feature
```


---

## 📂 Repository Structure

```
solt-pre-commit/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Internal CI pipeline
│       ├── solt-update-badges.yml    # Weekly badge updates
│       └── solt-validate.yml         # Reusable workflow for clients
├── configs/
│   ├── .pylintrc                     # Pylint configuration for Odoo
│   ├── .solt-hooks-defaults.yaml     # Default hook settings
│   └── pyproject-base.toml           # Base Python tools config (Ruff, etc.)
├── docs/
│   └── RUFF_LEVELS.md                # Ruff configuration levels guide
├── scripts/
│   ├── generate-badges.py            # Badge generation utility
│   ├── repos.txt                     # Batch setup repository list
│   └── setup-repo.py                 # Initialize hooks in client repos
├── src/
│   └── solt_pre_commit/
│       ├── __init__.py               # Package exports
│       ├── checks_branch_name.py     # Branch naming validation
│       ├── checks_odoo_module.py     # Main orchestrator
│       ├── checks_odoo_module_csv.py # CSV validations
│       ├── checks_odoo_module_po.py  # PO/POT validations
│       ├── checks_odoo_module_python.py  # Python validations
│       ├── checks_odoo_module_xml.py     # Basic XML validations
│       ├── checks_odoo_module_xml_advanced.py  # Advanced XML checks
│       ├── config_loader.py          # Configuration management
│       └── doc_coverage.py           # Documentation coverage analysis
├── templates/
│   ├── .pre-commit-config.yaml       # Pre-commit template (GitHub)
│   └── .pre-commit-config-local.yaml # Pre-commit template (local/monorepo)
├── .pre-commit-config.yaml           # This repo's pre-commit config
├── .pre-commit-hooks.yaml            # Hook definitions for consumers
├── pyproject.toml                    # Package configuration
├── setup.py                          # Package setup
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

---

## 🚀 Setup New Repository

### Automatic Setup

```bash
# From solt-pre-commit directory
python scripts/setup-repo.py ../your-repo

# With options
python scripts/setup-repo.py ../your-repo --scope full --dry-run

# Batch setup multiple repos
python scripts/setup-repo.py --batch scripts/repos.txt
```

This creates:
- `.pre-commit-config.yaml` - Hook configuration
- `.solt-hooks.yaml` - Validation settings
- `.pylintrc` - Pylint rules
- `pyproject.toml` - Python tools config (Ruff, etc.)
- `.github/workflows/solt-validate.yml` - CI workflow

### For Monorepo

```bash
python scripts/setup-repo.py ../solt-addons --local
```

Uses local Python paths instead of GitHub URLs.

---

## 🧪 Development

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=solt_pre_commit --cov-report=html
```

### Local Testing

```bash
# Install package locally
pip install -e .

# Create test module
mkdir -p test_module
cat > test_module/__manifest__.py << 'EOF'
{
    "name": "Test Module",
    "version": "17.0.1.0.0",
    "depends": ["base"],
    "installable": True,
}
EOF

# Run validation
solt-check-odoo test_module
```

---

## 📄 License

LGPL-3.0-or-later

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch: `feature/ISSUE-123-description`
3. Ensure all checks pass: `pre-commit run --all-files`
4. Create a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/soltein-net/solt-pre-commit/issues)
- **Email**: soporte@soltein.mx

---

**Developed by [Soltein SA de CV](https://soltein.mx)**
