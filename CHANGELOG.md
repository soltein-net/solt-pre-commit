# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

<!--
  Everything below stays under [Unreleased] - no dated version heading - until
  a v*.*.* tag/GitHub Release actually exists for it. A version number here
  before that point describes work in progress, not something anyone can
  actually install; the release step (bump pyproject.toml, rename this heading
  to "## [x.y.z] - <real date>", tag) should be its own small, separate action
  at cut time, not backdated inside the feature PR that adds the work.
-->

### Added
- `github_pr.py`: checks whether the current branch has an open GitHub PR
  (via `gh` CLI, falling back to `GITHUB_TOKEN`/`GH_TOKEN` + the REST API).
- `solt-test-changed-modules` now only runs when the current branch has an
  open PR - a push to a branch with no PR yet is exempt, per
  soltein/docs/pipeline-strategy.md's "Pipeline at a glance" (the Test tier
  fires on "PR opened/updated", not every push, including this local-Docker
  instantiation of it). If PR state can't be determined at all, it fails open
  and runs the tests rather than silently skipping. New `.solt-hooks.yaml`
  key: `test_require_open_pr` (default `true`; set `false` for the old
  unconditional-on-push behavior).
- `solt-test-changed-modules` hook (pre-push stage): runs Odoo tests for the
  modules changed vs. the base branch, so a push is gated on real test
  results, not just naming/lint.
- `odoo_test_runner.py` (`solt-test-module` console script): the actual test
  execution — scratch DB create/drop, `coverage run odoo-bin ... --test-tags`,
  dedicated HTTP/gevent ports (so it doesn't conflict with a running
  interactive dev server), filtered `--log-handler=:WARNING` output, and a
  pass/fail banner. Centralized here instead of duplicated per consuming repo.
  Paths resolve relative to the git superproject working tree when the
  consuming repo is a submodule (e.g. a solt-* addon repo under a
  soltein-suite super-repo).
- New `.solt-hooks.yaml` keys: `test_odoo_bin`, `test_odoo_conf`,
  `test_db_host`/`test_db_port`/`test_db_user`/`test_db_password`,
  `test_http_port`/`test_gevent_port`, `test_harness_script` (escape hatch to
  use a repo-provided script instead of the built-in runner), and
  `test_require_open_pr`.
- `_detect_base_branch()` now also recognizes an Odoo version embedded in the
  current branch name (e.g. `feature/17.0-x` -> `origin/17.0`), ahead of the
  main/master/develop fallback - the actual convention for repos on a
  branch-per-version model rather than a single trunk.

### Added
- `tests/test_checks_branch_name.py`: characterization tests for
  `BranchNameValidator` (protected-branch detection, Odoo-version
  extraction, flexible/strict validation, config loading, and the
  `solt-check-branch` CLI) - coverage for this module went from 16% to 94%.
- `tests/test_checks_odoo_module_csv.py`: characterization tests for
  `ChecksOdooModuleCSV` (duplicate record-id detection scoped per
  `data_section`, missing-file handling) - coverage for this module went
  from 22% to 100%.

### Fixed
- `checks_branch_name.py`: a misleading comment on
  `DEFAULT_PROTECTED_PATTERNS` claimed `17.0-stable` was an example of a
  protected branch; the pattern actually only matches `<version>.<digit>...`
  (e.g. `17.0.1`), not `<version>-word`, so `17.0-stable` was never
  protected. Corrected the comment to state the real match rule.
- `checks_branch_name.py`: the `github-revert` pattern
  (`^revert-\d+-.+$`) accepted any GitHub-generated revert branch
  unconditionally, bypassing the "Odoo version is REQUIRED" policy every
  other pattern in this module enforces. Tightened it to
  `^revert-\d+-.*<odoo-version>.*$` so a version-less revert branch is
  rejected too, consistent with the rest of the policy.

### Fixed
- `ODOO_PYTHON_REQUIREMENTS` (`config_loader.py`) had 18.0 pinned to Python
  3.11, and the README's "Supported Versions" table repeated the same number.
  Odoo's own docs (`administration/on_premise/source.html`) confirm the
  minimum jumped 3.7->3.10 once, at 17.0, and held at 3.10 through 18.0 - it
  does not bump every version. Corrected both to 3.10; 19.0/20.0 (3.12) were
  left as-is since Odoo's 19.0 docs weren't confirmable at fix time.
- `github_pr.py`: reformatted to satisfy `ruff format --check` (the `gh pr
  list` arg list and the REST API URL string were failing CI's format gate).
- CI's lint job and local dev now run the exact same `scripts/lint.sh`
  instead of two hand-maintained copies of the same `ruff check`/`ruff
  format` invocations - previously `ci.yml` was ahead of what `CONTRIBUTING.md`
  told contributors to run.
- Removed the dead `[tool.isort]` section from `pyproject.toml` (isort was
  replaced by ruff's `I` rule; nothing invoked isort). Its `known_first_party`
  setting moved to the ruff-native `[tool.ruff.lint.isort]`.
- `checks_odoo_module`: when no staged files match an Odoo module (e.g.
  `pre-commit run --all-files` with nothing staged), skip cleanly instead of
  falling back to validating the repo root itself as a module (which always
  failed with a confusing "could not be loaded" error).
- `OdooVersionDetector.normalize_version`: coerce non-string input (e.g. a
  bare `17.0` in YAML, which parses as a float, not a string) instead of
  crashing on `.lower()`.

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
