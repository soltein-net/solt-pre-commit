# Solt Pre-commit

[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL-3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Custom pre-commit hooks for Odoo module validation. Catches errors and runtime warnings **before** starting the server.

## 🚀 Quick Start

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/soltein-net/solt-pre-commit
    rev: v1.0.0
    hooks:
      # Branch naming validation
      - id: solt-check-branch
        stages: [pre-commit, pre-push]

      # Odoo module validation
      - id: solt-check-odoo
```

Then install:

```bash
pre-commit install
```

## 📦 Available Hooks

| Hook | Description |
|------|-------------|
| `solt-check-branch` | Branch naming policy validation |
| `solt-check-odoo` | Full validation (XML, CSV, PO, Python, Manifest) |
| `solt-check-xml` | XML validations only |
| `solt-check-csv` | CSV validations only |
| `solt-check-po` | PO/POT validations only |
| `solt-check-python` | Python validations only |

## 🌿 Branch Naming Validation

### Modes

Configure in `.solt-hooks.yaml`:

```yaml
branch_naming:
  # strict: true  → Requires ticket (feature/SOLT-123-description)
  # strict: false → Type/description only (feature/my-change)
  strict: false

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
```

### Examples

**Flexible mode** (`strict: false`):
```
✔ feature/add-budget-validation
✔ fix/correct-calculation
✔ feature/SOLT-123-with-ticket  (also valid)
✗ my-branch                      (missing type prefix)
✗ Feature/something              (wrong case)
```

**Strict mode** (`strict: true`):
```
✔ feature/SOLT-123-add-new-feature
✔ fix/PROJ-456-correct-bug
✗ feature/add-something          (missing ticket)
```

### Protected Branches

These branches skip validation:
- `main`, `master`, `develop`, `staging`, `production`
- Odoo versions: `12.0`, `13.0`, `14.0`, `15.0`, `16.0`, `17.0`, `18.0`

## 🛡️ Odoo Runtime Warnings Detected

These warnings normally only appear when starting the Odoo server. This tool catches them at commit time:

| Odoo Warning | Check |
|--------------|-------|
| `Two fields (field1, field2) have the same label` | `python_duplicate_field_label` |
| `inconsistent 'compute_sudo' for computed fields` | `python_inconsistent_compute_sudo` |
| `tracking value will be ignored` | `python_tracking_without_mail_thread` |
| `selection attribute will be ignored as field is related` | `python_selection_on_related` |
| `Using active_id, active_ids and active_model is deprecated` | `xml_deprecated_active_id_usage` |
| `An alert must have an alert, alertdialog or status role` | `xml_alert_missing_role` |

## 📝 All Checks

### XML Checks

| Check | Description |
|-------|-------------|
| `xml_syntax_error` | XML syntax errors |
| `xml_duplicate_record_id` | Duplicate record IDs |
| `xml_duplicate_fields` | Duplicate fields in same record |
| `xml_redundant_module_name` | Redundant module name in xmlid |
| `xml_deprecated_tree_attribute` | Deprecated `colors`, `fonts`, `string` in tree |
| `xml_deprecated_data_node` | Unnecessary `<odoo><data>` |
| `xml_deprecated_openerp_xml_node` | Use of `<openerp>` instead of `<odoo>` |
| `xml_view_dangerous_replace_low_priority` | `position="replace"` with priority < 99 |
| `xml_create_user_wo_reset_password` | res.users without `no_reset_password` |
| `xml_dangerous_filter_wo_user` | ir.filters without explicit user_id |
| `xml_deprecated_active_id_usage` | Deprecated active_id/active_ids/active_model |
| `xml_alert_missing_role` | Alert elements without proper role |
| `xml_button_without_type` | Buttons without type attribute |
| `xml_deprecated_t_raw` | Deprecated t-raw (use t-out) |
| `xml_hardcoded_id` | Hardcoded numeric IDs |
| `xml_duplicate_view_priority` | Views with same priority inheriting same view |

### CSV Checks

| Check | Description |
|-------|-------------|
| `csv_syntax_error` | CSV syntax errors |
| `csv_duplicate_record_id` | Duplicate external IDs |

### PO/POT Checks

| Check | Description |
|-------|-------------|
| `po_syntax_error` | PO file syntax errors |
| `po_duplicate_message_definition` | Duplicate message definitions |
| `po_requires_module` | Missing `#. module: MODULE` comment |
| `po_python_parse_printf` | Printf variable mismatches (`%s`, `%d`) |
| `po_python_parse_format` | Format variable mismatches (`{}`, `{name}`) |

### Python Checks

| Check | Description |
|-------|-------------|
| `python_syntax_error` | Python syntax errors |
| `python_duplicate_field_label` | Fields with same string/label |
| `python_inconsistent_compute_sudo` | Inconsistent compute_sudo |
| `python_tracking_without_mail_thread` | tracking=True without mail.thread |
| `python_selection_on_related` | selection on related fields |
| `python_field_missing_string` | Fields without string attribute |
| `python_field_missing_help` | Fields without help attribute |
| `python_method_missing_docstring` | Public methods without docstring |
| `python_docstring_too_short` | Docstrings < 10 characters |
| `python_docstring_uninformative` | Docstrings that just repeat method name |

### Manifest Checks

| Check | Description |
|-------|-------------|
| `manifest_syntax_error` | `__manifest__.py` syntax errors |
| `missing_readme` | Missing README file |

## ⚙️ Configuration

Create `.solt-hooks.yaml` in your repository root:

```yaml
# ═══════════════════════════════════════════════════════════════
# BRANCH NAMING POLICY
# ═══════════════════════════════════════════════════════════════
branch_naming:
  strict: false
  ticket_prefixes:
    - SOLT
    - PROJ
  allowed_types:
    - feature
    - fix
    - hotfix
    - release
    - refactor
    - docs
    - chore

# ═══════════════════════════════════════════════════════════════
# DISABLED CHECKS
# ═══════════════════════════════════════════════════════════════
disabled_checks:
  - python_field_missing_help
  - python_method_missing_docstring

# ═══════════════════════════════════════════════════════════════
# SKIP LISTS
# ═══════════════════════════════════════════════════════════════
skip_string_fields:
  - display_name
  - state
  - color
  - active
  - sequence
  - name

skip_help_fields:
  - active
  - name
  - sequence

skip_docstring_methods:
  - default_get
  - create
  - write
  - unlink

# ═══════════════════════════════════════════════════════════════
# SEVERITY CONFIGURATION
# ═══════════════════════════════════════════════════════════════
# Levels: error, warning, info
#   - error:   Blocks commit
#   - warning: Shows message, blocks if in blocking_severities
#   - info:    Only shown with --show-info flag

blocking_severities:
  - error
  # - warning  # Uncomment to also block on warnings

severity:
  # Syntax errors - always error
  xml_syntax_error: error
  csv_syntax_error: error
  python_syntax_error: error
  manifest_syntax_error: error
  po_syntax_error: error

  # Duplicates - error
  xml_duplicate_record_id: error
  csv_duplicate_record_id: error

  # Odoo runtime warnings - error
  python_duplicate_field_label: error
  python_inconsistent_compute_sudo: error
  python_tracking_without_mail_thread: error
  python_selection_on_related: error
  xml_deprecated_active_id_usage: error

  # Code quality - warning/info
  python_field_missing_string: warning
  python_field_missing_help: info
  python_method_missing_docstring: info
  python_docstring_too_short: info
```

## 💡 Examples

### tracking without mail.thread

```python
# ❌ Generates Odoo warning
class MyModel(models.Model):
    _name = 'my.model'

    name = fields.Char(tracking=True)  # No mail.thread inheritance

# ✅ Correct
class MyModel(models.Model):
    _name = 'my.model'
    _inherit = ['mail.thread']

    name = fields.Char(tracking=True)
```

### Inconsistent compute_sudo

```python
# ❌ Generates Odoo warning
total = fields.Float(compute='_compute_totals', compute_sudo=True)
subtotal = fields.Float(compute='_compute_totals')  # Missing compute_sudo

# ✅ Correct
total = fields.Float(compute='_compute_totals', compute_sudo=True)
subtotal = fields.Float(compute='_compute_totals', compute_sudo=True)
```

### Deprecated active_id

```xml
<!-- ❌ Deprecated -->
<field name="context">{'default_partner_id': active_id}</field>

<!-- ✅ Use alternatives -->
<field name="context">{'default_partner_id': id}</field>
```

## 🔧 CLI Usage

```bash
# Install
pip install git+https://github.com/soltein-net/solt-pre-commit.git@v1.0.0

# Validate Odoo module
solt-check-odoo /path/to/module

# Validate with info-level issues
solt-check-odoo /path/to/module --show-info

# Validate specific file types
solt-check-odoo /path/to/module --check-python-only
solt-check-odoo /path/to/module --check-xml-only

# Validate branch name
solt-check-branch feature/my-feature
solt-check-branch --strict feature/SOLT-123-description
```

## 📄 License

GPL-3.0-or-later

---

Developed by **Soltein**