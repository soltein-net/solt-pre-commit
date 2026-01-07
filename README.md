# Solt Pre-commit

[![CI](https://github.com/soltein-net/solt-pre-commit/workflows/CI/badge.svg)](https://github.com/soltein-net/solt-pre-commit/actions)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL%20v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![PyPI version](https://badge.fury.io/py/solt-pre-commit.svg)](https://badge.fury.io/py/solt-pre-commit)

Custom pre-commit hooks for Odoo module validation with comprehensive documentation coverage analysis. Catches errors and runtime warnings **before** starting the server.

<!-- BADGES:START -->
![Docstrings](https://img.shields.io/badge/docstrings-79.8%25-green?logo=python&logoColor=white)
![Documentation Standards](https://img.shields.io/badge/Documentation%20Standards-passing-brightgreen?logo=github&logoColor=white)
<!-- BADGES:END -->

---

## 🚀 Quick Start

### For New Repositories

```bash
# Clone solt-pre-commit
git clone https://github.com/soltein-net/solt-pre-commit.git

# Setup your Odoo repository
python solt-pre-commit/scripts/setup-repo.py /path/to/your-odoo-repo

# Done! The script creates all necessary files
```

### For Existing Repositories

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/soltein-net/solt-pre-commit
    rev: v1.0.0
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

### 🔍 Comprehensive Validation

| Check Type | Description | Blocks PR |
|------------|-------------|-----------|
| **Branch Names** | Enforces naming conventions | ✅ |
| **Odoo Runtime Warnings** | Detects issues before server start | ✅ |
| **XML Validations** | Syntax, duplicates, deprecations | ✅ |
| **Python Quality** | Docstrings, field attributes | Configurable |
| **CSV/PO Files** | Duplicate IDs, translation errors | ✅ |
| **Documentation Coverage** | Detailed reports with trends | ℹ️ Informative |

### 📊 Documentation Analysis

Unique feature: detailed documentation coverage reports showing:

- **Docstring coverage** per module and model
- **Field attribute coverage** (string, help)
- **Coverage trends** across PRs
- **Actionable recommendations** prioritized by impact

### ⚙️ Flexible Configuration

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
    uses: soltein-net/solt-pre-commit/.github/workflows/solt-validate.yml@v1.0.0
    with:
      validation-scope: 'changed'
      run-coverage: true
      fail-on-warnings: false
```

---

## 📦 Available Hooks

| Hook ID | Description | Use Case |
|---------|-------------|----------|
| `solt-check-branch` | Branch naming validation | All repos |
| `solt-check-odoo` | Full module validation | Primary hook |
| `solt-check-xml` | XML files only | Targeted checks |
| `solt-check-csv` | CSV files only | Data validation |
| `solt-check-po` | Translation files only | i18n checks |
| `solt-check-python` | Python files only | Code quality |

---

## 🛡️ Odoo Runtime Warnings Detected

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

## 📋 All Validation Checks

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
<summary><strong>🗂️ XML Checks</strong></summary>

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
<summary><strong>🌍 PO/POT Checks</strong></summary>

- `po_syntax_error` - Translation file errors
- `po_duplicate_message_definition` - Duplicate translations
- `po_requires_module` - Missing module comment
- `po_python_parse_printf` - Printf variable errors
- `po_python_parse_format` - Format string errors

</details>

---

## ⚙️ Configuration

### Validation Scope

Control what gets validated:

```yaml
# .solt-hooks.yaml
validation_scope: changed  # Only validate modified files (recommended for legacy)
# validation_scope: full   # Validate entire repository (for clean repos)
```

### Severity Levels

Customize what blocks your PR:

```yaml
severity:
  # error = always blocks
  python_duplicate_field_label: error
  
  # warning = reportable, blocks if 'blocking_severities' includes 'warning'
  python_field_missing_string: warning
  
  # info = only shown with --show-info
  python_docstring_too_short: info

blocking_severities:
  - error
  # - warning  # Uncomment to also block on warnings
```

### Skip Lists

Exclude specific fields/methods:

```yaml
skip_string_fields:
  - active
  - name
  - sequence

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

## 📊 Documentation Coverage Reports

### In Pull Requests

Every PR automatically includes:

```
📊 Análisis de Documentación (Informativo)

ℹ️ Este análisis es solo informativo, no bloquea el PR.

┌─────────────────────────┬────────┬────────┬────────┐
│ Métrica                 │ Valor  │ Meta   │ Estado │
├─────────────────────────┼────────┼────────┼────────┤
│ 📚 Cobertura Docstrings │ 79.8%  │ ≥10%   │   ✅   │
│ 🏷️ Campos con string    │ 87.0%  │ ≥80%   │   ✅   │
│ 💡 Campos con help      │ 28.0%  │ ≥30%   │   ⚠️   │
└─────────────────────────┴────────┴────────┴────────┘

📈 Cobertura por Módulo

┌────────────────────┬─────────┬─────────┬─────────┬───────┐
│ Módulo             │ Modelos │ Métodos │ Campos  │ Score │
├────────────────────┼─────────┼─────────┼─────────┼───────┤
│ solt_budget        │    4    │   23    │   45    │  63%  │
│ solt_budget_report │    2    │    8    │   15    │  71%  │
└────────────────────┴─────────┴─────────┴─────────┴───────┘

📊 Tendencia de Cobertura
Últimos 5 PRs: ↑ +13%
```

### Generate Badges

```bash
# After validation
python scripts/generate-badges.py reports/doc-coverage.json --readme README.md
```

Generates badges like:

![Docstrings](https://img.shields.io/badge/docstrings-79.8%25-green?logo=python&logoColor=white)
![Documentation Standards](https://img.shields.io/badge/Documentation%20Standards-passing-brightgreen?logo=github&logoColor=white)

---

## 🔧 CLI Usage

```bash
# Validate module
solt-check-odoo /path/to/module

# Force full validation (ignore scope config)
solt-check-odoo /path/to/module --scope full

# Show info-level issues
solt-check-odoo /path/to/module --show-info

# Validate branch name
solt-check-branch feature/SOLT-123-my-feature

# Generate documentation report
solt-check-odoo /path/to/module --generate-doc-report
```

---

## 📁 Repository Structure

```
solt-pre-commit/
├── .github/workflows/
│   ├── ci.yml                        # Internal CI
│   └── solt-validate.yml             # Reusable workflow for clients
│
├── src/solt_pre_commit/
│   ├── checks_branch_name.py         # Branch validation
│   ├── checks_odoo_module.py         # Main orchestrator
│   ├── checks_odoo_module_python.py  # Python checks
│   ├── checks_odoo_module_xml.py     # XML checks
│   ├── doc_coverage.py               # Documentation analysis
│   └── config_loader.py              # Configuration management
│
├── configs/                          # Config files for clients
│   ├── .pylintrc
│   ├── ruff.toml
│   └── .solt-hooks-defaults.yaml
│
├── scripts/
│   ├── setup-repo.py                 # Initialize client repos
│   ├── sync-configs.py               # Bulk update
│   └── generate-badges.py            # Badge generation
│
└── templates/                        # Templates for clients
    ├── .solt-hooks.yaml
    ├── .pre-commit-config.yaml
    └── github-workflows/validate.yml
```

---

## 🚀 Setup New Repository

### Automatic Setup

```bash
# From solt-pre-commit directory
python scripts/setup-repo.py ../your-repo

# With options
python scripts/setup-repo.py ../your-repo --scope full --dry-run
```

This creates:
- `.pre-commit-config.yaml` - Hook configuration
- `.solt-hooks.yaml` - Validation settings
- `.pylintrc` - Pylint rules
- `ruff.toml` - Ruff linter config
- `.github/workflows/validate.yml` - CI workflow

### For Monorepo (soltein-4.0)

```bash
python scripts/setup-repo.py ../solt-addons --local
```

Uses local Python paths instead of GitHub URLs.

---

## 🔄 Sync Multiple Repositories

```bash
# Create repos list
cat > repos.txt << EOF
/path/to/solt-budget
/path/to/solt-inventory
/path/to/solt-sales
EOF

# Sync configurations
python scripts/sync-configs.py repos.txt

# Preview changes
python scripts/sync-configs.py repos.txt --dry-run

# Create PRs automatically
python scripts/sync-configs.py repos.txt --create-pr
```

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

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/soltein-net/solt-pre-commit/issues)
- **Documentation**: [Full Docs](https://soltein-net.github.io/solt-pre-commit)
- **Email**: soporte@soltein.mx

---

**Developed with ❤️ by [Soltein SA de CV](https://soltein.mx)**