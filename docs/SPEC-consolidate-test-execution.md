# Spec: Consolidate Odoo test-execution logic (local vs. CI)

## Objective

`odoo_test_runner.py` (local/pre-push, via `solt-test-module`) and
`.github/workflows/solt-coverage.yml` (CI's `Test` job) both run "an Odoo
module's own tests against a scratch DB, with coverage" — but as two
independently hand-written implementations of the same idea. They've
already drifted: CI passes `--db_password=odoo` as a plain CLI argument
(visible to anything on that box via `ps aux`), while the local runner
deliberately uses a `PGPASSWORD` env var specifically to avoid that
exposure. Nothing catches this kind of divergence today.

Goal: one shared implementation of the actual test-invocation sequence
(`createdb → coverage run odoo-bin --test-tags ... --stop-after-init →
report → dropdb`), called by both the local pre-push path and CI, so a
fix or improvement made in one place is never silently absent from the
other.

**Non-goal:** unifying CI's environment-provisioning steps (installing
Odoo from `requirements.txt`, installing system/apt build deps, cloning
sibling repos via `CHECKOUT_TOKEN`, building the dynamic `--addons-path`
from those clones). Those are legitimately CI-only concerns — the local
runner assumes Odoo + addons-path already exist (devcontainer or a
developer's own setup) and has no reason to grow install/clone logic.

## Current State (for reference)

| | Local (`odoo_test_runner.py`) | CI (`solt-coverage.yml`) |
|---|---|---|
| DB name | `test_scratch_<pid>` (created + dropped per run) | fixed `ci_coverage` |
| DB password | `PGPASSWORD` env var | `--db_password=` CLI arg (exposed via `ps aux`) |
| Ports | dedicated `18069`/`18072` (avoid dev-server collision) | Odoo defaults `8069`/`8072` (fine - nothing else running) |
| `--addons-path` | not passed - relies on the resolved `.conf` file | built dynamically from sibling-repo clones |
| Coverage output | terminal summary + `coverage.xml` + `htmlcov/` | terminal + `coverage_report.txt` appended to the job summary |
| Log handling | `--logfile=` (empty) + `--log-handler=:WARNING` | `--log-handler=:WARNING` only |

## Tech Stack

Python 3.10-3.12 (existing `solt_pre_commit` package), GitHub Actions
YAML (`solt-coverage.yml`). No new frameworks or dependencies.

## Commands

- Local (unchanged): `solt-test-module <modules>`
- CI (new step added before the existing "Run tests with coverage" step):
  `pip install solt-pre-commit==<pinned version>` (version already pinned
  elsewhere in the generated workflow, e.g. `@v1.1.1`)
- CI's test step becomes a call into the same package, e.g.:
  `solt-test-module "$MODULES" --addons-path "$ADDONS_PATH"`
  (exact flag name TBD in Plan phase)

## Project Structure

No new files/directories expected; changes land in:
- `src/solt_pre_commit/odoo_test_runner.py` (add addons-path override)
- `src/solt_pre_commit/config_loader.py` (if the override becomes a
  `SoltConfig`/CLI-parsed value rather than a pure function parameter)
- `.github/workflows/solt-coverage.yml` (replace the inline
  `coverage run odoo-bin ...` step with the shared CLI call)
- `tests/test_odoo_test_runner.py` (extend for the new parameter)

## Code Style

Match existing conventions in `odoo_test_runner.py`: subprocess-based,
explicit env dict copies for secrets (never a password as a bare CLI
arg), docstring comments explaining *why* a flag exists where it's
non-obvious (see the existing `--logfile=`/`--log-handler` comment as the
model to follow for any new flag added).

## Testing Strategy

- Unit tests in `tests/test_odoo_test_runner.py` (pytest, existing
  pattern: mock `subprocess.run`/`Popen`, assert on the constructed
  command) - extend for the addons-path override, both present and
  absent.
- No live Odoo/DB execution possible in this sandbox (confirmed: no
  Postgres, no `odoo` package installed here) - final verification of
  the actual CI behavior change happens by observing a real PR's
  `Integration Test`/`Test` check runs after this ships, not by local
  execution here.
- `scripts/lint.sh` + full existing suite must stay green throughout.

## Boundaries

- **Always:** preserve the local runner's current behavior for existing
  devcontainer users unless a task explicitly changes it (dedicated
  ports, `.conf`-file resolution, `test_odoo_bin`/`test_odoo_conf`
  override keys); run `scripts/lint.sh` + full test suite before any
  commit.
- **Ask first:** any change to `.solt-hooks.yaml`'s schema (new keys),
  any change to what CI installs/pins, any behavior change to
  `solt-coverage.yml` itself (it's a *reusable* workflow other repos
  call at a pinned tag - safe for already-pinned consumers per
  assumption 6, but still a shared-file change worth a look before
  landing).
- **Never:** reintroduce a password as a plain CLI argument anywhere in
  either path - that's the specific bug this consolidation exists to
  prevent from recurring.

## Success Criteria

1. There is exactly one place in the codebase that constructs the
   `coverage run odoo-bin ... --test-tags ... --stop-after-init` command
   and its flags.
2. No `--db_password=`-style CLI exposure anywhere (CI included).
3. CI's existing sibling-repo checkout + dynamic addons-path behavior is
   unchanged from a consumer repo's point of view.
4. `tests/test_odoo_test_runner.py` covers the new override; full suite
   (`pytest tests/`) and `scripts/lint.sh` pass.
5. `CHANGELOG.md` documents the change under `[Unreleased]`; version
   bumped as a minor release (new CLI surface) per assumption 5.
6. Already-pinned consumer repos (e.g. anything still on `@v1.1.1` or
   earlier) are unaffected until they bump their pin - verified by
   reasoning (rulesets/tags are immutable, established earlier this
   session), not by testing every consumer repo.

## Resolved (was "Open Questions")

All three original questions were resolved during planning, and shipped
exactly as decided:

1. **Addons-path override shape** → a new `--addons-path` CLI flag on
   `solt-test-module`, threaded to `run(..., addons_path=None)`. Omitted
   by default; appended to the odoo-bin invocation only when provided.
2. **DB naming** → CI dropped its fixed `ci_coverage` name entirely;
   the shared function's own `test_scratch_<pid>` create/drop cycle
   handles it now. Confirmed nothing else in the workflow referenced
   `ci_coverage` by name before removing it.
3. **Coverage job-summary reporting** → stayed CI-only, unchanged. It
   still reads the same `.coverage` data file afterward; only *what
   produced it* changed.

## Findings During Implementation (not anticipated in the plan)

Two real blockers surfaced only once the CI YAML was actually being
wired up - worth recording here since they change what Task 4 needed to
do beyond "swap one command for another":

1. **`solt-pre-commit` is not published to PyPI** (confirmed: no
   `twine upload` step anywhere in `ci.yml`). `pip install
   solt-pre-commit==1.2.0` would simply fail. CI installs it via
   `pip install git+https://github.com/soltein-net/solt-pre-commit.git@v1.2.0`
   instead - installing straight from the tagged commit, no PyPI needed.
2. **`odoo_test_runner.run()` requires a conf file to exist** before it
   runs anything - it silently exits 0 (treated as an unconfigured local
   environment, not a failure) if the resolved `.devoncontainer/dev_<major>/odoo.conf`
   is missing. CI never used a conf file before (everything was passed
   via explicit flags), so naively calling `solt-test-module` would have
   silently reported "passed" without running a single test. Fixed by
   having CI write a minimal `[options]`-only conf file at the expected
   path, and exporting `SOLT_ODOO_VERSION` so the derived path
   deterministically matches `inputs.odoo-version` rather than relying
   on manifest auto-detection.
