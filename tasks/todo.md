# Tasks: Consolidate Odoo test-execution logic (local vs. CI)

Plan: `tasks/plan.md` · Spec: `docs/SPEC-consolidate-test-execution.md`

## [DONE] Task 1: Add `--addons-path` override to `odoo_test_runner.py`

**Description:** Add an optional `addons_path` parameter to `run()`,
threaded from a new `--addons-path` CLI flag in `main()`'s argparse.
When provided, append `--addons-path=<value>` to the `coverage run
odoo-bin ...` subprocess argument list. When omitted (the default),
behavior must be byte-for-byte identical to today - no flag passed at
all, no change for any existing caller.

**Acceptance criteria:**
- [ ] `run(modules, config, env_root=None, addons_path=None)` passes
      `--addons-path=<value>` to odoo-bin only when `addons_path` is not
      `None`
- [ ] `solt-test-module --addons-path /some/path modA,modB` parses and
      forwards the value correctly
- [ ] Omitting `--addons-path` reproduces the exact current subprocess
      argument list (regression check)

**Verification:**
- [ ] `pytest tests/test_odoo_test_runner.py -v`
- [ ] `scripts/lint.sh`

**Dependencies:** None

**Files likely touched:**
- `src/solt_pre_commit/odoo_test_runner.py`

**Estimated scope:** Small (1 file)

---

## [DONE] Task 2: Unit tests for the addons-path override

**Description:** Extend `tests/test_odoo_test_runner.py` with cases for
both presence and absence of the override, following the file's existing
mock-`subprocess` pattern (matches how the rest of this file already
tests constructed command arguments).

**Acceptance criteria:**
- [ ] Test asserts `--addons-path=<value>` appears in the constructed
      command when provided
- [ ] Test asserts no `--addons-path` arg appears when omitted
- [ ] Test confirms the CLI flag reaches `run()` correctly

**Verification:**
- [ ] `pytest tests/test_odoo_test_runner.py -v`
- [ ] `pytest tests/` (full suite still green)

**Dependencies:** Task 1

**Files likely touched:**
- `tests/test_odoo_test_runner.py`

**Estimated scope:** Small (1 file)

---

## Checkpoint: After Tasks 1-2 (end of Phase 1)
- [ ] All tests pass, `scripts/lint.sh` clean
- [ ] Confirmed no behavior change for existing callers when the flag is
      omitted
- [ ] **Review with human before proceeding** - this slice is
      independently mergeable and should ship as its own PR + release
      before Task 4 can begin

---

## [DONE] Task 5: CHANGELOG + version bump

**Description:** Document the new override under `[Unreleased]` in
`CHANGELOG.md`; bump `pyproject.toml`/`__init__.py` to the next minor
version (new CLI surface, not a patch, per spec assumption 5).

**Acceptance criteria:**
- [ ] `CHANGELOG.md` `[Unreleased]` section describes the `--addons-path`
      addition
- [ ] Version bumped consistently in `pyproject.toml` and `__init__.py`

**Verification:**
- [ ] `pytest tests/` and `scripts/lint.sh` still green
- [ ] Matches this project's established release-prep convention (see
      CONTRIBUTING.md "Releasing")

**Dependencies:** Tasks 1-2

**Files likely touched:**
- `CHANGELOG.md`
- `pyproject.toml`
- `src/solt_pre_commit/__init__.py`

**Estimated scope:** XS (3 files, no logic changes)

---

## REVISED: single release, not two

Original plan required a hard stop here (Task 4 needing a *published*
tag before it could start). Revisited with the user: solt-pre-commit's
own `ci.yml` never exercises `solt-coverage.yml` at all, so nothing
breaks by having Task 4 sit on the same branch/PR as Tasks 1-2 - no
consumer repo is affected until a tag exists that bundles *both* pieces
together, which is exactly what happens when everything ships as one
release. Proceeding with Tasks 1, 2, 4, 5, 6 all in one PR/tag (`v1.2.0`).

<!-- Original hard-stop text, kept for the record:
- [ ] PR for Tasks 1, 2, 5 merged
- [ ] A real version tag pushed (e.g. `v1.2.0`) containing the
      `--addons-path` flag
- [ ] **Do not start Task 4 before this tag exists** - CI's
      `pip install solt-pre-commit==<version>` step needs a real,
      published version to install
- [ ] Confirm with human before proceeding to Phase 3
-->

---

## [DONE] Task 4: `solt-coverage.yml` calls `solt-test-module`

(Required two additions beyond the original plan - see spec's "Findings
During Implementation": installing from git, not PyPI; writing a minimal
conf file + exporting `SOLT_ODOO_VERSION` so `odoo_test_runner.run()`
doesn't silently skip with exit 0.)

**Description:** Add a `pip install solt-pre-commit==<pinned version>`
step to the `Test` job; replace the inline `createdb` +
`coverage run odoo-bin ...` block with a call to
`solt-test-module "$MODULES" --addons-path "$ADDONS_PATH"`. The shared
function now owns scratch-DB creation/cleanup, so CI's own `createdb -d
ci_coverage` line is removed, not just left dormant.

**Acceptance criteria:**
- [ ] "Run tests with coverage" step shells out to `solt-test-module`,
      no inline `coverage run odoo-bin` invocation remains
- [ ] No CI-only `createdb`/`dropdb` remains
- [ ] No `--db_password` (or any secret) appears as a plain CLI argument
      anywhere in the file - the specific bug this whole effort exists to
      fix
- [ ] Existing "Coverage report" step (unchanged) still finds `.coverage`
      data to report on afterward
- [ ] `grep -r ci_coverage .github/workflows/` confirms no other step
      references the old fixed DB name before it's removed

**Verification:**
- [ ] `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/solt-coverage.yml'))"`
- [ ] **Cannot be executed locally** (no Postgres, no `odoo` package in
      this sandbox - confirmed earlier) - real verification is watching
      an actual PR's `Test`/`Integration Test` checks after this ships.
      Do not report this task done on a clean diff alone.

**Dependencies:** Task 1 (specifically: a *released* version containing
it - see the Hard Stop checkpoint above)

**Files likely touched:**
- `.github/workflows/solt-coverage.yml`

**Estimated scope:** Medium (1 file, but unverifiable locally + shared
reusable-workflow blast radius raises real risk despite the small diff)

---

## [DONE] Task 6: CHANGELOG + spec update

**Description:** Document the CI migration under a fresh `[Unreleased]`
in `CHANGELOG.md`. Update `docs/SPEC-consolidate-test-execution.md`'s
"Open Questions" section to record the three resolutions made during
planning (DB naming, job-summary handling, flag shape) instead of
leaving them as open - per "keeping the spec alive."

**Acceptance criteria:**
- [ ] CHANGELOG documents the CI-side change
- [ ] Spec's Open Questions section reflects final decisions, not
      pending questions

**Verification:**
- [ ] Spec accurately describes what was actually implemented, not just
      what was planned

**Dependencies:** Task 4

**Files likely touched:**
- `CHANGELOG.md`
- `docs/SPEC-consolidate-test-execution.md`

**Estimated scope:** XS (2 files, docs only)

---

## Checkpoint: Complete
- [ ] All Success Criteria in the spec are met
- [ ] Full suite + lint green on both Slice A and Slice B PRs
- [ ] Human has reviewed real CI check results for Slice B specifically
      (not just the diff)
