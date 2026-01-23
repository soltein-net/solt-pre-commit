# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2025-01-23

### Added
- Multi-version Odoo support (17.0, 18.0, 19.0+)
- Automatic Odoo version detection from branch names
- Python version auto-selection based on Odoo version
- Advanced XML validation checks
- Ruff levels documentation (RUFF_LEVELS.md)

### Changed
- Migrated to flat project structure
- Improved GitHub Actions workflow with better error handling
- Enhanced PR comments with detailed validation reports
- Centralized `pyproject.toml` configuration for client repos (replaces separate `ruff.toml`)
- `--no-force` flag in `setup-repo.py` to skip existing files
- Automatic cleanup of old `ruff.toml` files when syncing
- `fail-on-warnings` option in GitHub Actions workflow
- `show-info` option to display info-level issues
- **BREAKING**: `ruff.toml` replaced by `pyproject.toml` in client repos
- `setup-repo.py` now overwrites existing files by default (use `--no-force` to skip)
- Ruff hooks now use `pyproject.toml` automatically (removed `--config ruff.toml` args)
- Simplified GitHub workflow template (corrected reusable workflow path)

### Fixed
- Version detection from manifest files
- Branch name patterns for feature/hotfix prefixes

### Removed
- `configs/ruff.toml` (consolidated into `pyproject-base.toml`)

## [1.0.0] - 2024-12-15

### Added
- Initial release
- Branch naming validation (`solt-check-branch`)
- Full Odoo module validation (`solt-check-odoo`)
- Individual checks: XML, CSV, PO, Python
- Severity system: error, warning, info
- Configurable validation scope: changed/full
- `.solt-hooks.yaml` configuration support
- Skip lists for fields and methods
- Ruff linter configuration for Odoo modules
- Setup script (`setup-repo.py`) to initialize hooks in client repos
- GitHub Actions workflow template for CI validation
- Path exclusions for migrations, tests, static, and node_modules
- Odoo runtime warning detection:
  - Duplicate field labels
  - Inconsistent compute_sudo
  - Tracking without mail.thread
  - Selection on related fields
  - Deprecated active_id usage
  - Alert elements missing role

### Changed
- Replaced Black/isort/flake8 with Ruff in pre-commit config template

### Fixed
- Version sync between `pyproject.toml`, `setup.py`, and `__init__.py`
