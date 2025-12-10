# Solt Pre-commit Hooks for Odoo

A comprehensive suite of pre-commit hooks specifically designed for Odoo module development at Soltein. These hooks implement static code analysis that catches common errors and Odoo runtime warnings before starting the server, improving code quality and reducing debugging time.

## Features

- **Manifest Validation**: Ensures `__manifest__.py` files have all required fields and correct structure
- **Init File Checks**: Validates `__init__.py` files for proper import structure
- **XML Validation**: Checks XML files for syntax errors and Odoo-specific issues
- **Model Validation**: Analyzes Python model files for common Odoo patterns and issues
- **Deprecated API Detection**: Identifies usage of deprecated Odoo APIs and suggests modern alternatives
- **SQL Injection Prevention**: Detects potential SQL injection vulnerabilities in custom queries

## Installation

### Using pre-commit (Recommended)

1. Install [pre-commit](https://pre-commit.com/):
   ```bash
   pip install pre-commit
   ```

2. Add to your `.pre-commit-config.yaml`:
   ```yaml
   repos:
     - repo: https://github.com/soltein-net/solt-pre-commit
       rev: v1.0.0  # Use the latest version
       hooks:
         - id: check-odoo-manifest
         - id: check-odoo-init
         - id: check-odoo-xml
         - id: check-odoo-models
         - id: check-odoo-deprecated
   ```

3. Install the git hooks:
   ```bash
   pre-commit install
   ```

### Manual Installation

Install directly from the repository:
```bash
pip install git+https://github.com/soltein-net/solt-pre-commit.git
```

## Available Hooks

### check-odoo-manifest

Validates `__manifest__.py` files for:
- Required fields: `name`, `version`, `category`, `author`, `depends`
- Valid field names (detects typos)
- Proper version format (e.g., `16.0.1.0.0`)
- Correct data types for fields

**Example Error:**
```
__manifest__.py:
  ❌ Missing required keys: author, version
  ❌ Unknown keys (possible typo): licence (did you mean 'license'?)
  ❌ Invalid version format '1.0'. Expected format: X.Y.Z.W.X (e.g., 16.0.1.0.0)
```

### check-odoo-init

Validates `__init__.py` files for:
- Proper import structure
- Warnings about non-import code in `__init__.py` files

**Note:** This hook provides warnings but won't block commits.

### check-odoo-xml

Validates XML files for:
- Valid XML syntax
- Proper Odoo root elements (`<odoo>`, `<data>`)
- Records with missing `id` or `model` attributes
- Templates without `id` attributes
- Menu items with missing required attributes
- Duplicate IDs within the same file
- Records without fields

**Example Error:**
```
views/partner_view.xml:
  ❌ Record without 'id' attribute (model: res.partner)
  ❌ Duplicate ID in file: 'view_partner_form'
```

### check-odoo-models

Validates Python model files for:
- Models with `_name` should have `_description`
- Models must have either `_name` or `_inherit`
- Potential SQL injection risks in custom queries
- Proper use of parameterized queries

**Example Error:**
```
models/partner.py:
  ❌ Class 'Partner': Model with '_name' should have '_description' for better UX
  ❌ Class 'Partner': Line 45: Potential SQL injection risk. Use parameterized queries with execute(query, params)
```

### check-odoo-deprecated

Detects usage of deprecated Odoo APIs:
- Old API decorators (`@api.one`, `@api.v7`, `@api.v8`)
- Old API methods (old-style `browse`, `search`, `create`, etc.)
- Deprecated field types (`fields.related`, `fields.function`)
- Deprecated imports (`from openerp import`)
- Deprecated OSV usage
- Other deprecated patterns

**Example Error:**
```
models/sale.py:
  ❌ Line 15: @api.one is deprecated, use other decorators or remove
  ❌ Line 23: Import from "openerp" is deprecated, use "odoo" instead
  ❌ Line 45: .sudo(user_id) is deprecated, use .with_user(user_id)
```

## Usage Examples

### Running Manually

You can run any hook manually:

```bash
# Check a specific manifest file
check-odoo-manifest path/to/__manifest__.py

# Check all XML files
find . -name "*.xml" | xargs check-odoo-xml

# Check all model files
find . -path "*/models/*.py" | xargs check-odoo-models

# Check for deprecated APIs in all Python files
find . -name "*.py" | xargs check-odoo-deprecated
```

### Running with pre-commit

```bash
# Run all hooks on staged files
pre-commit run

# Run all hooks on all files
pre-commit run --all-files

# Run a specific hook
pre-commit run check-odoo-manifest --all-files
```

## Configuration

### Selective Hook Usage

You can choose which hooks to use in your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/soltein-net/solt-pre-commit
    rev: v1.0.0
    hooks:
      # Only use manifest and XML checks
      - id: check-odoo-manifest
      - id: check-odoo-xml
```

### Excluding Files

You can exclude specific files or patterns:

```yaml
repos:
  - repo: https://github.com/soltein-net/solt-pre-commit
    rev: v1.0.0
    hooks:
      - id: check-odoo-models
        exclude: ^legacy/
```

## Development

### Setting Up Development Environment

```bash
git clone https://github.com/soltein-net/solt-pre-commit.git
cd solt-pre-commit
pip install -e .
```

### Running Tests

```bash
# Install test dependencies
pip install pytest

# Run tests
pytest tests/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## About Soltein

This tool is developed and maintained by [Soltein](https://github.com/soltein-net) for internal use and the broader Odoo community.

## Common Issues Caught

These hooks help catch issues like:

1. **Missing manifest fields** - Prevents installation errors
2. **Invalid XML syntax** - Catches errors before Odoo tries to load views
3. **Deprecated API usage** - Helps maintain compatibility with newer Odoo versions
4. **SQL injection risks** - Improves security of custom queries
5. **Missing model descriptions** - Improves user experience and code documentation
6. **Duplicate XML IDs** - Prevents module loading errors
7. **Invalid version formats** - Ensures proper module versioning

## Support

For issues, questions, or contributions, please use the [GitHub issue tracker](https://github.com/soltein-net/solt-pre-commit/issues).
