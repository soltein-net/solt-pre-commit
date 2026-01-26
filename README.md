# Solt Pre-commit

[![CI](https://github.com/soltein-net/solt-pre-commit/workflows/CI/badge.svg)](https://github.com/soltein-net/solt-pre-commit/actions)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Odoo 17.0-19.0](https://img.shields.io/badge/odoo-17.0--19.0-purple.svg)](https://www.odoo.com/)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL%20v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)

Custom pre-commit hooks for Odoo module validation with comprehensive documentation coverage analysis. Catches errors and runtime warnings **before** starting the server.

**Supports Odoo 17.0, 18.0, and 19.0** with automatic version detection.

---

## 📋 Supported Versions

| Odoo Version | Python | Status |
|--------------|--------|--------|
| 17.0 | 3.10+ | ✅ Fully Supported |
| 18.0 | 3.10+ | ✅ Fully Supported |
| 19.0 | 3.11+ | ✅ Fully Supported |

---

## 🚀 Quick Start

### For New Repositories

```bash
# Clone solt-pre-commit
git clone https://github.com/soltein-net/solt-pre-commit.git

# Setup your Odoo repository (auto-detects version)
python solt-pre-commit/setup-repo.py /path/to/your-odoo-repo

# Or specify version explicitly
python solt-pre-commit/setup-repo.py /path/to/your-odoo-repo --odoo-version 18.0

# Batch setup multiple repos
python solt-pre-commit/setup-repo.py --batch repos.txt

# Done! The script creates all necessary files
```

### For Existing Repositories

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/soltein-net/solt-pre-commit
    rev: v1.0.4  # Supports Odoo 17.0, 18.0, 19.0
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

## ✨ Features

### Comprehensive Validation

| Check Type | Description | Blocks PR |
|------------|-------------|-----------|
| **Branch Names** | Enforces naming conventions | ✅ |
| **Odoo Runtime Warnings** | Detects issues before server start | ✅ |
| **XML Validations** | Syntax, duplicates, deprecations | ✅ |
| **Python Quality** | Docstrings, field attributes | Configurable |
| **CSV/PO Files** | Duplicate IDs, translation errors | ✅ |
| **Documentation Coverage** | Detailed reports with trends | ℹ️ Informative |

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

### 🔄 Centralized Workflows

Use our reusable GitHub Actions workflow:

```yaml
# .github/workflows/validate.yml
jobs:
  validate:
    uses: soltein-net/solt-pre-commit/.github/workflows/solt-validate.yml@v1.0.4
    with:
      validation-scope: 'changed'
      fail-on-warnings: false
```

---

## 🪝 Available Hooks

| Hook ID | Description | Use Case |
|---------|-------------|----------|
| `solt-check-branch` | Branch naming validation | All repos |
| `solt-check-odoo` | Full module validation | Primary hook |
| `solt-check-xml` | XML files only | Targeted checks |
| `solt-check-csv` | CSV files only | Data validation |
| `solt-check-po` | Translation files only | i18n checks |
| `solt-check-python` | Python files only | Code quality |

---

## ⚠️ Odoo Runtime Warnings Detected

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

## 📝 All Validation Checks

<details>
<summary><strong>🐍 Python Checks</strong></summary>

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
<summary><strong>📄 XML Checks</strong></summary>

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
<summary><strong>📊 CSV Checks</strong></summary>

- `csv_syntax_error` - CSV parse errors
- `csv_duplicate_record_id` - Duplicate XML IDs

</details>

<details>
<summary><strong>🌐 PO/POT Checks</strong></summary>

- `po_syntax_error` - Translation file errors
- `po_duplicate_message_definition` - Duplicate translations
- `po_requires_module` - Missing module comment
- `po_python_parse_printf` - Printf variable errors
- `po_python_parse_format` - Format string errors

</details>

---

## ⚙️ Configuration

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

**Odoo version prefix is REQUIRED** in all branch names:

```yaml
branch_naming:
  strict: true  # Requires version + ticket: feature/17.0-SOLT-123-description
  # strict: false  # Requires version: feature/17.0-description

  ticket_prefixes:
    - SOLT
    - PROJ

  allowed_types:
    - feature
    - fix
    - hotfix
    - bugfix
    - release
    - refactor
    - docs
    - test
    - chore
    - imp
    - perf
    - ci
    - deps
    - security
```

**Valid examples:**
- `feature/17.0-SOLT-123-add-invoice` ✅ (recommended)
- `fix/18.0-PROJ-456-fix-bug` ✅
- `feature/17.0-add-new-feature` ✅ (flexible mode)
- `hotfix/18.0-urgent-fix` ✅
- `release/17.0.1.0` ✅

**Invalid (missing version):**
- `feature/add-something` ❌
- `feature/SOLT-123-something` ❌

---

## 💻 CLI Usage

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

## 🛠️ Setup Script Commands

The `setup-repo.py` script provides multiple operation modes:

### Full Setup (default)

```bash
# Single repo
python setup-repo.py /path/to/repo

# Batch setup
python setup-repo.py --batch repos.txt

# With options
python setup-repo.py /path/to/repo --scope full --odoo-version 18.0
```

### Update Version Only

```bash
# Update solt-pre-commit version in .pre-commit-config.yaml
python setup-repo.py --update-only /path/to/repo
python setup-repo.py --update-only --batch repos.txt
python setup-repo.py --update-only --batch repos.txt --version v1.0.5
```

### Pre-commit Maintenance

```bash
# Clean global pre-commit cache
python setup-repo.py --clean

# Reinstall hooks in repos
python setup-repo.py --reinstall-hooks /path/to/repo
python setup-repo.py --reinstall-hooks --batch repos.txt

# Run autoupdate for solt-pre-commit
python setup-repo.py --autoupdate /path/to/repo
python setup-repo.py --autoupdate --batch repos.txt
```

### All Options

```bash
python setup-repo.py --help
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
├── setup-repo.py                     # Initialize/maintain client repos
├── _pylintrc                         # Pylint configuration for Odoo
├── _solt-hooks.yaml                  # Default hook settings
├── _pre-commit-config.yaml           # Pre-commit template (GitHub)
├── _pre-commit-config-local.yaml     # Pre-commit template (local/monorepo)
├── .pre-commit-hooks.yaml            # Hook definitions for consumers
├── pyproject.toml                    # Package configuration
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
python setup-repo.py ../your-repo

# With options
python setup-repo.py ../your-repo --scope full --dry-run

# Batch setup multiple repos
python setup-repo.py --batch repos.txt
```

This creates:
- `.pre-commit-config.yaml` - Hook configuration
- `.solt-hooks.yaml` - Validation settings
- `.pylintrc` - Pylint rules
- `pyproject.toml` - Python tools config (Ruff, etc.)
- `.github/workflows/solt-validate.yml` - CI workflow

### For Monorepo

```bash
python setup-repo.py ../solt-addons --local
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
2. Create a feature branch: `feature/17.0-ISSUE-123-description` (version + ticket recommended)
3. Ensure all checks pass: `pre-commit run --all-files`
4. Create a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/soltein-net/solt-pre-commit/issues)
- **Email**: soporte@soltein.mx

---

**Developed by [Soltein SA de CV](https://soltein.mx)**
