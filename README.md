# Solt Pre-commit

[![Soltein Validations](https://github.com/soltein-net/solt-pre-commit/workflows/CI/badge.svg)](https://github.com/soltein-net/solt-pre-commit/actions)

---

[![Tests (3.11)](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/SolteinCorp/147d543a086f6735d1ffa02172766e86/raw/solt-pre-commit-py3.11-tests.json)](https://github.com/soltein-net/solt-pre-commit/actions/workflows/ci.yml)
[![Tests (3.12)](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/SolteinCorp/147d543a086f6735d1ffa02172766e86/raw/solt-pre-commit-py3.12-tests.json)](https://github.com/soltein-net/solt-pre-commit/actions/workflows/ci.yml)
[![Tests (3.13)](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/SolteinCorp/147d543a086f6735d1ffa02172766e86/raw/solt-pre-commit-py3.13-tests.json)](https://github.com/soltein-net/solt-pre-commit/actions/workflows/ci.yml)

[![Integration (17.0)](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/SolteinCorp/147d543a086f6735d1ffa02172766e86/raw/solt-pre-commit-odoo17.0-integration.json)](https://github.com/soltein-net/solt-pre-commit/actions/workflows/ci.yml)
[![Integration (18.0)](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/SolteinCorp/147d543a086f6735d1ffa02172766e86/raw/solt-pre-commit-odoo18.0-integration.json)](https://github.com/soltein-net/solt-pre-commit/actions/workflows/ci.yml)
[![Integration (19.0)](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/SolteinCorp/147d543a086f6735d1ffa02172766e86/raw/solt-pre-commit-odoo19.0-integration.json)](https://github.com/soltein-net/solt-pre-commit/actions/workflows/ci.yml)

---

[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/SolteinCorp/147d543a086f6735d1ffa02172766e86/raw/solt-pre-commit-core-coverage.json)](https://github.com/soltein-net/solt-pre-commit/actions/workflows/ci.yml)

---

Comprehensive pre-commit and CI/CD infrastructure for Odoo modules. **Catches errors and runtime warnings before they reach production.** Blocks non-test-passing code at the pre-push stage.

**Supports Odoo 17.0, 18.0, and 19.0** with automatic version detection and module-aware testing.

---

- [Solt Pre-commit](#solt-pre-commit)
  - [📋 Supported Versions](#-supported-versions)
  - [🚀 Quick Start](#-quick-start)
    - [Automatic Setup (Recommended)](#automatic-setup-recommended)
    - [Batch Setup](#batch-setup)
    - [Update Existing Repos](#update-existing-repos)
    - [Manual Setup (For Existing Repos)](#manual-setup-for-existing-repos)
    - [Local Development Setup](#local-development-setup)
  - [✨ Key Features](#-key-features)
    - [Pre-Commit Validation (Blocks Commits)](#pre-commit-validation-blocks-commits)
    - [Pre-Push Testing (Blocks Pushes)](#pre-push-testing-blocks-pushes)
    - [CI/CD Workflows (GitHub Actions)](#cicd-workflows-github-actions)
  - [🔧 How It Works](#-how-it-works)
    - [Automatic Module \& Dependency Detection](#automatic-module--dependency-detection)
    - [Keeping requirements.txt in Sync](#keeping-requirementstxt-in-sync)
    - [Branch Handling for Sibling Repos (Per-Module PR/Branch CI)](#branch-handling-for-sibling-repos-per-module-prbranch-ci)
    - [Generated Workflow Files](#generated-workflow-files)
    - [Test/Coverage Scope (many-module repos)](#testcoverage-scope-many-module-repos)
    - [Sharding a full-scope run (`shards`)](#sharding-a-full-scope-run-shards)
    - [Pre-Push Test Blocking](#pre-push-test-blocking)
  - [📚 Pre-Push Test Blocking Explained](#-pre-push-test-blocking-explained)
  - [🐛 Debugging Failed Pre-Push Tests](#-debugging-failed-pre-push-tests)
  - [🪝 Available Hooks](#-available-hooks)
  - [⚠️ Odoo Runtime Warnings Detected](#️-odoo-runtime-warnings-detected)
  - [📝 All Validation Checks](#-all-validation-checks)
    - [Runtime Errors (Block)](#runtime-errors-block)
    - [Parsing Errors (Block)](#parsing-errors-block)
    - [Documentation (Configurable)](#documentation-configurable)
    - [Other (Informational)](#other-informational)
    - [Errors (Block)](#errors-block)
    - [Warnings](#warnings)
    - [Info](#info)
  - [⚙️ Configuration](#️-configuration)
    - [Odoo Version](#odoo-version)
    - [Validation Scope](#validation-scope)
    - [Severity Customization](#severity-customization)
    - [Skip Lists](#skip-lists)
    - [Cross-Repo Testing](#cross-repo-testing)
    - [Branch Naming](#branch-naming)
  - [💻 CLI Usage](#-cli-usage)
  - [🛠️ Setup Script Commands](#️-setup-script-commands)
    - [`setup` - Full setup](#setup---full-setup)
    - [`regenerate` - Refresh an already-configured repo](#regenerate---refresh-an-already-configured-repo)
    - [`update-version` - Update only the version pin](#update-version---update-only-the-version-pin)
    - [`badges` - Inject/refresh README badges](#badges---injectrefresh-readme-badges)
    - [Pre-commit Maintenance](#pre-commit-maintenance)
    - [All Options](#all-options)
  - [🤝 Contributing](#-contributing)
  - [📞 Support](#-support)


## 📋 Supported Versions

<!-- This is what we actually generate/test against (get_python_version() in
     scripts/setup-repo.py), not Odoo's documented *minimum* - see that
     function's own docstring for why: below 3.12, Odoo's requirements.txt
     holds cryptography/pyOpenSSL to 2021-era pins nothing deploys against,
     and 3.13 costs nothing over 3.12 in dependency coverage. get_python_version()
     also maps 20.0 -> 3.13, but 20.0 isn't in this repo's own Integration Test
     matrix (ci.yml) yet - not listed below until it is. Keep this table in
     sync with that mapping by hand - there is no single source both read from. -->
| Odoo Version | Python | Status |
|--------------|--------|--------|
| 17.0 | 3.11 | ✅ Fully Supported |
| 18.0 | 3.11 | ✅ Fully Supported |
| 19.0 | 3.13 | ✅ Fully Supported |

---

## 🚀 Quick Start

### Automatic Setup (Recommended)

```bash
# Setup your Odoo repository (auto-detects modules, dependencies, Odoo version)
python solt-pre-commit/scripts/setup-repo.py setup /path/to/your-odoo-repo

# Generates:
# - .github/workflows/solt-validate.yml (auto-filled with detected modules)
# - README.md or injects badges into existing README
# - .pre-commit-config.yaml, .solt-hooks.yaml, pyproject.toml
# - Installs pre-commit hooks
```

### Batch Setup

```bash
# Create repos.txt with one repo per line
echo /path/to/solt-crm >> repos.txt
echo /path/to/solt-base >> repos.txt

# Setup all at once
python solt-pre-commit/scripts/setup-repo.py setup --batch repos.txt
```

### Update Existing Repos

```bash
# Update the version pin only, nothing else
python solt-pre-commit/scripts/setup-repo.py update-version --batch repos.txt

# Regenerate the CI workflow from current modules, sync any pre-commit hook
# the repo is missing, and stamp the current version - all three together
python solt-pre-commit/scripts/setup-repo.py regenerate /path/to/repo

# Inject badges into existing README
python solt-pre-commit/scripts/setup-repo.py badges /path/to/repo
```

### Manual Setup (For Existing Repos)

If you prefer to add solt-pre-commit to an existing `.pre-commit-config.yaml`:

```yaml
default_install_hook_types: [ pre-commit, pre-push ]  # so `pre-commit install` covers both stages

repos:
  - repo: https://github.com/soltein-net/solt-pre-commit
    rev: vX.Y.Z # replace with latest release
    hooks:
      - id: solt-check-odoo
      - id: solt-check-requirements
      - id: solt-test-changed-modules
```

`solt-check-branch` is deliberately not included here - see [Branch Naming](#branch-naming) below for why standalone repos enforce it at PR level instead.

### Local Development Setup

If your repo *also* has
`solt-pre-commit/` checked out as a submodule (so you can dev/test solt-pre-commit changes fast), use the
`--local` flag instead:

```bash
python solt-pre-commit/scripts/setup-repo.py setup /path/to/your-odoo-repo --local
```

This copies `templates/.pre-commit-config-local.yaml` instead of the default
`templates/.pre-commit-config.yaml`. The difference is the `repo:` key on the
solt-pre-commit hooks block:

```yaml
repos:
  - repo: local   # instead of: repo: https://github.com/soltein-net/solt-pre-commit + rev: <pin>
    hooks:
      - id: solt-check-branch
        entry: python -m solt_pre_commit.checks_branch_name
        # ...
```

`repo: local` calls straight into the editable-installed package instead of
a pinned GitHub commit/tag, so local edits to `solt-pre-commit/` take effect
on your very next commit - no cutting a release and re-pinning `rev:` first.
It also keeps `solt-check-branch` as a local commit-time gate (redundant
with, but faster feedback than, the PR-level auto-close check standalone
repos rely on alone).

**Note**: this monorepo's own root `.pre-commit-config.yaml` (the one
covering files outside any addon submodule) is hand-maintained, not
generated by `setup-repo.py` - running the script against the monorepo root
itself would `rglob` every submodule for manifests and rewrite the root
README/pyproject.toml, which isn't what you want there. Mirror the `repo:
local` block from `templates/.pre-commit-config-local.yaml` by hand instead.

---

## ✨ Key Features

### Pre-Commit Validation (Blocks Commits)

| Check | Description | Stage |
|-------|-------------|-------|
| **Branch Names** | Enforces naming conventions (must include Odoo version) | pre-commit |
| **Odoo Runtime Warnings** | Detects issues that cause Odoo warnings | pre-commit |
| **XML Validations** | Syntax, duplicate IDs, deprecated attributes | pre-commit |
| **Python Quality** | Docstrings, field attributes, decorators | pre-commit |
| **requirements.txt Sync** | Verifies root requirements.txt matches manifests' `external_dependencies` | pre-commit |

### Pre-Push Testing (Blocks Pushes)

| Check | Description | Stage |
|-------|-------------|-------|
| **Module Tests** | Runs tests for changed modules (blocks if tests fail) | pre-push |
| **Cross-Repo Deps** | Checkouts & tests sibling repos (auto-detected) | pre-push |
| **Coverage Report** | Generates code coverage metrics | pre-push |

### CI/CD Workflows (GitHub Actions)

| Job | Purpose | When |
|-----|---------|------|
| **Lint** | Code quality checks on PR | Every PR |
| **Test** | Runs Odoo tests with coverage | Every PR |
| **Badges** | Reports results to Gist badges | Every PR |
| **Docstrings** | Weekly docstring coverage update | Mondays |

---

## 🔧 How It Works

### Automatic Module & Dependency Detection

`setup-repo.py` scans your repository for `__manifest__.py` files and:
- Detects all Odoo modules
- Parses `depends:` to find external repos (e.g., `solt_base` → `soltein-net/solt-base@17.0`)
- Detects Odoo version from manifest or branch name
- Maps to correct Python version

### Keeping requirements.txt in Sync

`solt-check-requirements` uses [manifestoo](https://github.com/acsone/manifestoo) to read `external_dependencies["python"]` from every installable addon's manifest under the repo, then verifies the repo's root `requirements.txt` is an exact match (dedup'd by canonical package name, order-independent, comments ignored). It fails closed - the file is never rewritten automatically at commit time:

```bash
# After adding/editing a manifest's external_dependencies:
solt-check-requirements --fix
```

The manifest stays the single source of truth for a module's Python dependencies (it's what Odoo itself checks before allowing a module to install) - `requirements.txt` is only ever a generated aggregate of it, never edited by hand. If two addons in the repo declare different version constraints for the same package, the check fails with both constraints shown instead of silently picking one.

### Branch Handling for Sibling Repos (Per-Module PR/Branch CI)

**Scope**: this only applies to a module repo's own CI (e.g. `solt-crm`'s `solt-validate.yml`, triggered on a PR against `solt-crm`). It answers "does my branch work against sibling repos' version branch" — not "does this exact release work".

```bash
# Feature/hotfix branch (local to this repo)
git checkout feature/17.0-first-test  # solt-crm
# Sibling repos use: soltein-net/solt-base@17.0 (version extracted)

# Version branch
git checkout 17.0  # solt-crm
# Sibling repos use: soltein-net/solt-base@17.0
```

Sibling repos always use the **version branch** (the latest of `@17.0`, `@18.0`, etc.) — never a tag, never an attempt to reconstruct "what my feature branch was developed against". That's the industry-standard approach for cross-repo PR testing: test against the current target branch of your dependencies, because that's what's true after merge.

**This does NOT apply to release tags** (`17.0-2026.07.17-00`). Those are created only on the `soltein` super-repo (see `scripts/cut-release.sh`) and never exist in individual module repos, so a module's own CI never encounters one. Release tags also don't correspond to any one branch: a super-repo release pins each submodule to whatever commit SHA it had checked out at the time — which can be an **unmerged hotfix commit**, not anything reachable from that module's version branch. Substituting the version branch for a release tag would silently test different code than what was actually released.

**Testing "exactly what a release pins" is a separate, super-repo-level concern** — not something `sibling-repos` can solve. The correct mechanism: check out the super-repo at the release tag with `submodules: recursive` (or `git submodule update --init --recursive` after `git checkout <tag>`). That alone reproduces the exact pinned commit of every submodule — no branch/tag guessing required. See `docs/RELEASE-TAG-STRATEGY.md` for the proposed super-repo regression workflow.

### Generated Workflow Files

The `.github/workflows/solt-validate.yml` is **auto-generated** with:
```yaml
Test:
  uses: soltein-net/solt-pre-commit/.github/workflows/solt-coverage.yml@v1.1.0
  with:
    modules: 'solt_crm solt_crm_services solt_crm_project ...'  # auto-detected
    sibling-repos: 'soltein-net/solt-base@17.0:solt-base ...'   # auto-detected
    odoo-version: '17.0'
    python-version: '3.11'  # pinned to what's actually deployed - see note below
```

**Note on `python-version`**: this value is passed directly to `actions/setup-python@v5`, which **installs and pins that exact minor version** (latest patch of `3.11.x`). It is **not** a "minimum version" check — CI will not test on a newer minor unless a matrix is added. This comes from `get_python_version()` in `scripts/setup-repo.py`, mapped per Odoo version: `3.11` for 17.0-18.0, `3.13` for 19.0-20.0 - see that function's own docstring for the reasoning (it's not a straight "one bump per Odoo release" progression: below Python 3.12, Odoo's own `requirements.txt` holds `cryptography`/`pyOpenSSL` to 2021-era pins nothing here actually deploys against). These track what's actually deployed (devcontainers and production images), not Odoo's documented *minimum* supported Python (3.10 for 17.0-19.0) — pinning to the minimum instead reliably broke CI on an unrelated toolchain mismatch (Odoo's own `requirements.txt` pins a `gevent` build for Python 3.10 that no longer compiles on current GitHub-hosted runners) while catching nothing real, since nothing in this fleet actually runs that minimum. An odoo-version with no entry in the mapping raises immediately when `setup-repo.py` runs, rather than silently guessing a Python version that might be wrong for it.

### Test/Coverage Scope (many-module repos)

`solt-coverage.yml`'s `Test` job has a `scope` input, `'full'` (default) or `'changed'`. As of v1.6.0
this is generated automatically — `setup-repo.py setup`/`regenerate` render it as
`scope: ${{ github.event_name == 'push' && 'full' || 'changed' }}` (see "Recommended pattern" below),
no hand-added `with:` line needed.

`scope: 'full'` tests every module in `modules`, unconditionally — unchanged default behavior for
every caller. `scope: 'changed'` narrows that down to only the declared modules that actually have a
changed file in the current diff (same detection the local pre-push hook already uses for
`test_scope: changed` — self-healing shallow-clone base-ref fetch, `GITHUB_BASE_REF`-aware in CI). Two
distinct outcomes when nothing declared matches:
- the diff changed files, but none map to a declared module (e.g. a sibling-repo dependency bump) —
  falls back to testing the full `modules` list, a safety net for an ambiguous diff.
- the diff touched zero Odoo-module-shaped paths at all (docs, CI config, non-addon scripts) — the
  `Test` job is skipped entirely (not even the Postgres service/Odoo checkout run, via a cheap `Detect`
  job ahead of it), reported as a pass with no coverage data, since nothing declared could possibly
  have changed behavior.

Worth setting on a repo with many modules in one addon repo (e.g. 24) where most PRs only ever touch
1-3 of them — for a real, module-touching diff the job's own checkout/install overhead is fixed
regardless, so `'changed'` saves the minutes actually spent running every *other* module's tests for a
change that never touched them.

**Coverage reporting follows whatever was actually tested**, not the full declared list — the
`Coverage report` step reads the `Test` step's own `modules-tested` output rather than re-deriving
from `modules`, so a `scope: 'changed'` run's percentage reflects only the modules it exercised
(otherwise every untested module's untraced source would count as 0% and drag the number down for no
reason). It's also skipped outright (no percentage computed at all) when `Test` itself was skipped, for
the same reason.

**Recommended pattern for many-module repos**, generated automatically: run `scope: 'changed'` on
`pull_request` for fast per-PR feedback, and re-run the same jobs `scope: 'full'` on `push` to the
target branch (post-merge) so the coverage/lint badges get refreshed from one authoritative whole-repo
run per merge instead of tracking whatever subset the last merged PR happened to touch, non-blocking
(a full-scope run can surface pre-existing debt no single PR introduced - see
`soltein-net/solt-llm#110`). Since `Validation` is cheap (seconds), running it full-scope too on push
costs nothing meaningful and keeps `Badges`' other inputs
(`solt-check-errors`/`pylint-changed`/`ruff-changed`) genuinely computed rather than defaulted. Run
`setup-repo.py regenerate` against an already-configured repo to pick this up.

**Test runs regardless of `Validation`'s outcome on push, via a separate job, not a wider `if:`.**
`Validation`'s own `fail-on-warnings`/`pylint-blocking` are non-blocking on push, but `severity:
error` checks are always blocking regardless of that setting - a full-scope scan can surface
pre-existing *errors* just as easily as warnings (e.g. `python_tracking_without_mail_thread` on old
code no recent PR touched). A plain `needs: Validation` would silently skip `Test` outright whenever
that happens, discarding the one signal this whole pattern exists to produce post-merge - real,
full-scope coverage/test-pass data - over an unrelated lint issue.

The fix is **not** `Test`'s own `if:` referencing `needs.Validation.result` (tried first, and it does
not work reliably): a job's `needs` dependency on another job that itself calls a reusable workflow
(like `Validation` does) does not reliably expose that job's outcome to `needs.<job>.result` /
`success()` / `failure()` in a downstream job's `if:` - GitHub evaluates the reusable workflow's
*internal* jobs, not the calling job as one opaque unit, and that internal state can leak into an
unwanted skip regardless of `always()` (see
[community discussion #189172](https://github.com/orgs/community/discussions/189172) and
[#72708](https://github.com/orgs/community/discussions/72708) for other reports of the same class of
bug). Instead, the generated workflow has **two separate jobs**: `Test` (`pull_request` only, `needs:
Validation`, unchanged - Test only runs once Validation succeeds, the real per-PR merge gate) and
`TestPostMerge` (`push` only, no `needs:` at all - nothing about `Validation`'s internal job structure
can propagate into a job that was never made to depend on it). `Badges` reads whichever one actually
ran (`needs.Test.outputs.test-result || needs.TestPostMerge.outputs.test-result` - GitHub Actions
expressions treat an empty string as falsy, so this correctly falls through to whichever job produced
a real value).

### Sharding a full-scope run (`shards`)

`solt-coverage.yml` also takes a `shards` input (default `'1'` - no sharding, unchanged behavior for
every caller that doesn't set it). With `shards > 1`, `Coverage` becomes a matrix job over
`shard: [0, ..., shards-1]`, and `modules` is distributed **round-robin** across shards (module `i` ->
shard `i % shards`), not contiguous blocks - a contiguous split would put an entire large module
family (e.g. a ~40-module `l10n_*_edi` family) in one or two shards, creating a straggler that
dominates wall-clock regardless of shard count. Each shard still pays this job's own fixed
checkout/install overhead independently (more total billed minutes: N shards x ~4 min instead of one),
in exchange for wall-clock roughly divided by N (`solt-suite`'s own ~2.5h full-scope run split 8 ways
is a real cost of ~28 extra minutes for a ~20-minute wait instead of ~2.5 hours).

A new `Combine` job (always its own job, even at `shards: '1'` - one code path, not two) downloads
every shard's uploaded coverage data file and pass/fail result, runs `coverage combine` across all of
them, and produces the one `test-result`/`coverage-pct` this reusable workflow actually promises
callers. This has to be a separate job reading from uploaded artifacts, not `Coverage`'s own per-leg
`outputs:` - a *matrix* job's outputs at the job level are last-leg-wins (whichever shard happens to
finish last "wins", silently discarding every other shard's result), not reliable for aggregating
across shards.

Round-robin-by-count is a first approximation, not a real balance - it assumes every module costs
roughly the same, which isn't true. Once real per-module timing is available (see
`odoo_test_runner`'s `odoo.modules.loading:INFO` telemetry), shards should be rebalanced by actual
cost instead of module count.

### Pre-Push Test Blocking

When you push, the pre-push hook runs tests. **If tests fail, the push is blocked:**

```bash
$ git push
Running Odoo tests for changed modules...
FAIL: solt_crm
Error: AssertionError in test_lead_creation

❌ Pre-push hook failed - tests must pass
Push blocked. Fix tests and try again.
```

---

## 📚 Pre-Push Test Blocking Explained

The `solt-test-changed-modules` hook at the **pre-push stage**:

1. Detects which modules changed vs. base branch
2. Only runs if the current branch has an open PR (checked via `gh` CLI / `GITHUB_TOKEN`) — exempt on a branch's first, PR-less push; fails open (runs anyway) if PR state can't be determined
3. Creates a **scratch database** (temporary)
4. Installs the Odoo modules
5. **Runs tests** for those modules
6. If **any test fails** → **push is blocked** ❌
7. Drops the scratch database
8. Reports coverage metrics to badges

This ensures **only tested code reaches the repository.**

---

## 🐛 Debugging Failed Pre-Push Tests

If a push fails:

```bash
# See which modules changed
git diff --name-only origin/17.0...HEAD

# Run tests manually (same way pre-push does)
python scripts/setup-repo.py setup /path/to/repo  # setup if needed

# Run specific module tests
solt-test-module solt_crm

# Check test output in .git/hooks/pre-push logs
cat .git/hooks/pre-push
```

---

## 🪝 Available Hooks

| Hook ID | Purpose | Files |
|---------|---------|-------|
| `solt-check-branch` | Validate branch naming (pre-commit + pre-push stages) | (all) |
| `solt-check-odoo` | Full module validation | Python, XML, CSV, PO/POT |
| `solt-check-xml` | XML-only validation | XML |
| `solt-check-csv` | CSV-only validation | CSV |
| `solt-check-po` | PO/POT-only validation | PO, POT |
| `solt-check-python` | Python-only validation | Python |
| `solt-check-requirements` | Verify (or `--fix` regenerate) root requirements.txt from manifests | `__manifest__.py` |
| `solt-test-changed-modules` | Run Odoo tests for changed modules (pre-push stage only) | (all) |

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
- `python_tracking_without_mail_thread` - `tracking=True` on a field of a model that doesn't inherit a mail.thread mixin
- `python_selection_on_related` - Selection on related fields

### Parsing Errors (Block)
- `python_syntax_error` - Python file failed to parse
- `manifest_syntax_error` - `__manifest__.py` could not be loaded

### Documentation (Configurable)
- `python_field_missing_string` - Fields without string attribute
- `python_field_missing_help` - Fields without help text
- `python_method_missing_docstring` - Methods without docstring
- `python_docstring_too_short` - Docstrings < 10 chars
- `python_docstring_uninformative` - Generic docstrings

### Other (Informational)
- `missing_readme` - Module has no README.md/README.txt/README.rst

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
- `xml_deprecated_tree_attribute` - Deprecated tree attributes (string, colors, fonts)
- `xml_hardcoded_id` - Hardcoded IDs instead of ref()
- `xml_create_user_wo_reset_password` - User creation issue
- `xml_dangerous_filter_wo_user` - Filter without user_id
- `xml_duplicate_view_priority` - Views inheriting the same view with the same priority
- `xml_deprecated_data_node` - `<odoo><data>` wrapper used for a single child
- `xml_deprecated_openerp_xml_node` - `<openerp>` node instead of `<odoo>`
- `xml_deprecated_t_raw` - Deprecated `t-raw` QWeb directive (use `t-out`)
- `xml_deprecated_qweb_directive` - Other deprecated QWeb directives (`t-esc-options`, etc.)
- `xml_not_valid_char_link` - Invalid characters in a link/script resource path

### Info
- `xml_redundant_module_name` - Record ID redundantly prefixed with its own module name

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

### Cross-Repo Testing

If your modules depend on external repos, configure secrets:

```bash
# Set in GitHub repository settings
SOLT_CROSS_REPO_TOKEN  # PAT for accessing sibling repos
GIST_SECRET            # PAT for updating badges gist
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
    # ... see templates/.solt-hooks.yaml for the full default list
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

`setup-repo.py` is a subcommand CLI - each mode is its own subcommand with only
the options that apply to it, so an invalid combination is a parse error
instead of silently falling through to a different (and possibly more
destructive) mode.

### `setup` - Full setup

Copies templates, detects modules/dependencies, generates the CI workflow,
installs hooks. Force-overwrites files that already exist (pass
`--no-overwrite` to skip them instead) - this is the mode for a repo's
*first* setup; an already-configured repo should use `regenerate` below.

```bash
# Single repo
python setup-repo.py setup /path/to/repo

# Batch setup
python setup-repo.py setup --batch repos.txt

# With options
python setup-repo.py setup /path/to/repo --validation-scope full --odoo-version 18.0

# Monorepo submodule (repo: local instead of a pinned GitHub rev)
python setup-repo.py setup /path/to/repo --local
```

`--validation-scope` sets `.solt-hooks.yaml`'s local `validation_scope` -
unrelated to the generated CI workflow's own `Test`/`Validation` `scope`
input, despite the similar name.

### `regenerate` - Refresh an already-configured repo

Regenerates `.github/workflows/solt-validate.yml` from the repo's current
modules, adds any pre-commit hook the repo is missing (via
`sync_precommit_hooks()` - never touches hooks the repo already has), and
stamps the current version - all three together, safe to run repeatedly.
Never force-overwrites `.pre-commit-config.yaml` or `.solt-hooks.yaml`.

```bash
python setup-repo.py regenerate /path/to/repo
python setup-repo.py regenerate --batch repos.txt
python setup-repo.py regenerate /path/to/repo --version v1.6.0
```

### `update-version` - Update only the version pin

```bash
python setup-repo.py update-version /path/to/repo
python setup-repo.py update-version --batch repos.txt
python setup-repo.py update-version --batch repos.txt --version v1.0.2
```

### `badges` - Inject/refresh README badges

```bash
python setup-repo.py badges /path/to/repo
```

### Pre-commit Maintenance

```bash
# Clean global pre-commit cache
python setup-repo.py clean-cache

# Reinstall hooks in repos
python setup-repo.py reinstall-hooks /path/to/repo
python setup-repo.py reinstall-hooks --batch repos.txt

# Run autoupdate for solt-pre-commit
python setup-repo.py autoupdate /path/to/repo
python setup-repo.py autoupdate --batch repos.txt
```

### All Options

```bash
python setup-repo.py --help
python setup-repo.py <command> --help   # e.g. setup-repo.py regenerate --help
```

---

## 🤝 Contributing

Want to add a new check, run the test suite, or understand the internal
source layout (`src/solt_pre_commit/`, `scripts/`, `templates/`)? See
[CONTRIBUTING.md](CONTRIBUTING.md) - this README only covers using
solt-pre-commit in a client repo.

---

## 📞 Support

- **Email**: soporte@soltein.mx

---

**Developed by [Soltein SA de CV](https://soltein.mx)**
