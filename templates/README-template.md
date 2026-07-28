# {MODULE_NAME}

[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Odoo 17.0](https://img.shields.io/badge/Odoo-17.0-blue.svg)](https://www.odoo.com)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL%20v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)

## Description

{DESCRIPTION}

## Features

- Feature 1: Brief description of the feature
- Feature 2: Brief description of the feature
- Feature 3: Brief description of the feature

## Requirements

- Odoo 17.0
- Python 3.10+
- Dependencies:
  - `base`
  - `mail` (optional, for tracking)
  - {OTHER_DEPENDENCIES}

## Installation

### Standard Installation

1. Clone this repository into your Odoo addons path:
   ```bash
   git clone {REPO_URL} /path/to/odoo/addons/{MODULE_NAME}
   ```

2. Update the addons path in your Odoo configuration:
   ```ini
   [options]
   addons_path = /path/to/odoo/addons,/path/to/custom/addons
   ```

3. Restart Odoo and update the app list:
   ```bash
   ./odoo-bin -u base -d your_database
   ```

4. Install the module from the Apps menu (activate developer mode first)

### Docker Installation

```bash
# Add to your docker-compose.yml volumes
volumes:
  - ./addons/{MODULE_NAME}:/mnt/extra-addons/{MODULE_NAME}
```

## Configuration

### Basic Configuration

{CONFIGURATION_NOTES}

1. Go to **Settings** > **{MODULE_NAME}**
2. Configure the required parameters:
   - **Parameter 1**: Description and purpose
   - **Parameter 2**: Description and purpose

### Advanced Configuration

For advanced use cases, you can configure:

```python
# Example configuration in code
self.env['ir.config_parameter'].sudo().set_param(
    '{module_name}.config_key', 'value'
)
```

## Usage

### Basic Usage

{USAGE_NOTES}

1. Navigate to the module menu
2. Create a new record
3. Fill in the required fields
4. Save and process

### API Usage

```python
# Create a record
record = self.env['{model.name}'].create({
    'name': 'Example',
    'field1': 'value1',
})

# Search records
records = self.env['{model.name}'].search([
    ('field1', '=', 'value1'),
])

# Call a method
result = record.action_method()
```

### Scheduled Actions

The module includes the following automated actions:

| Cron Job | Frequency | Description |
|----------|-----------|-------------|
| {cron_name} | Daily | {description} |

## Development

This repository uses [solt-pre-commit](https://github.com/soltein-net/solt-pre-commit) for code quality validation.

### Setup Development Environment

```bash
# Clone the repository
git clone {REPO_URL}
cd {MODULE_NAME}

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install pre-commit

# Install pre-commit hooks
pre-commit install
pre-commit install --hook-type pre-push
```

### Running Checks Locally

```bash
# Run all checks
pre-commit run --all-files

# Run specific hook
pre-commit run solt-check-odoo --all-files

# Validate specific module
solt-check-odoo /path/to/module

# Show detailed info
solt-check-odoo /path/to/module --show-info
```

### Validation Modes

By default, only files changed in PRs are validated. Configure in `.solt-hooks.yaml`:

```yaml
# Validate only changed files (default)
validation_scope: changed

# Validate entire repository
validation_scope: full
```

### Branch Naming Convention

Follow this pattern for branch names:

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/TICKET-123-description` | `feature/SOLT-456-add-export` |
| Bugfix | `fix/TICKET-123-description` | `fix/SOLT-789-correct-calc` |
| Hotfix | `hotfix/TICKET-123-description` | `hotfix/SOLT-001-urgent-fix` |
| Release | `release/X.Y.Z` | `release/17.0.1.0` |


## Documentation

- Update README if adding new features
- Document new configuration options
- Add inline comments for complex logic

## Changelog

### [17.0.1.0.0] - {DATE}

#### Added
- Initial release
- Feature 1
- Feature 2

#### Changed
- N/A

#### Fixed
- N/A

## Roadmap

- [ ] Feature planned for next release
- [ ] Another upcoming feature
- [ ] Long-term improvement

## Support

For questions or issues:

- **Issue Tracker**: {REPO_URL}/issues
- **Email**: {SUPPORT_EMAIL}
- **Documentation**: {DOCS_URL}

## License

This module is licensed under the [LGPL-3.0-or-later](https://www.gnu.org/licenses/lgpl-3.0).

## Credits

### Authors

- **Soltein** - [soltein.mx](https://soltein.mx)

### Contributors

- {CONTRIBUTOR_NAME} - {CONTRIBUTION}

### Acknowledgments

- Odoo S.A. for the amazing framework
- OCA for community standards and tools

---

**Developed with ❤️ by Soltein**
