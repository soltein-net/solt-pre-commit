# Tasks: Stop distributing agent-skills; distribute a CONTRIBUTING.md instead

Plan: `tasks/plan.md`

## [DONE] Task 1: Remove `skills-lock.json` from distribution

**Description:** Remove the `templates/skills-lock.json` entry from
`FILES_TO_COPY` in `scripts/setup-repo.py`, and delete the file itself -
it's an unused artifact (a lockfile manifest with no installer behind it
anywhere in this repo or the super-repo's own scripts).

**Acceptance criteria:**
- [ ] `FILES_TO_COPY` no longer references `skills-lock.json`
- [ ] `templates/skills-lock.json` deleted
- [ ] `grep -rn skills-lock` across the repo returns nothing

**Verification:**
- [ ] `pytest tests/` full suite
- [ ] `scripts/lint.sh`
- [ ] `grep -rn "skills-lock" .` (from repo root) - empty

**Dependencies:** None

**Files likely touched:**
- `scripts/setup-repo.py`
- `templates/skills-lock.json` (deleted)

**Estimated scope:** XS (2 files, one a deletion)

---

## [DONE] Task 2: Write `templates/CONTRIBUTING-template.md`

**Description:** A CONTRIBUTING.md template for consumer Odoo repos -
distinct from solt-pre-commit's *own* CONTRIBUTING.md (that one's about
contributing to the tool; this one's about contributing to a module that
*uses* the tool). Covers: dev setup (clone, `pre-commit install`),
branch naming (references `solt-check-branch`'s enforced convention),
running tests locally (`solt-test-module`), what pre-commit/pre-push
checks run automatically, and a new "AI Agent Tooling (Optional)"
section stating plainly that solt-pre-commit does not bundle or
distribute this, with the canonical install commands for
`addyosmani/agent-skills`.

**Acceptance criteria:**
- [ ] Covers dev setup, branch naming, local testing, automatic checks
- [ ] "AI Agent Tooling (Optional)" section has the exact
      `/plugin marketplace add` + `/plugin install` commands
- [ ] States explicitly that this is optional and not something
      solt-pre-commit provides itself
- [ ] Uses the same `{PLACEHOLDER}`-style tokens as `README-template.md`
      for anything repo-specific (if anything ends up needing one)

**Verification:**
- [ ] Manual read-through - does this read like a real, useful
      CONTRIBUTING.md, not boilerplate padding?

**Dependencies:** None (can be written in parallel with Task 1)

**Files likely touched:**
- `templates/CONTRIBUTING-template.md` (new)

**Estimated scope:** S (1 new file, no code)

---

## [DONE] Task 3: Wire the template into `FILES_TO_COPY`

**Description:** Add `(TEMPLATES_DIR / "CONTRIBUTING-template.md", "CONTRIBUTING.md", "Contributor guide (dev setup, branch naming, optional AI tooling)")`
to `FILES_TO_COPY`, following the exact tuple shape already used by the
other four entries.

**Acceptance criteria:**
- [ ] New entry present in `FILES_TO_COPY` with the same tuple shape as
      existing entries
- [ ] Destination filename is `CONTRIBUTING.md` (not the template's own
      filename)

**Verification:**
- [ ] `pytest tests/`
- [ ] Manual: run `setup-repo.py` against a scratch temp directory,
      confirm `CONTRIBUTING.md` is written with the template's content

**Dependencies:** Task 2

**Files likely touched:**
- `scripts/setup-repo.py`

**Estimated scope:** XS (1 file, one line)

---

## [DONE] Task 4: Regression test for `FILES_TO_COPY`

**Description:** Extend `tests/test_setup_repo.py` with an assertion on
`FILES_TO_COPY`'s contents directly - guards against this exact kind of
drift recurring (a file that's copied but shouldn't be, or should be but
isn't).

**Acceptance criteria:**
- [ ] Test asserts no entry's destination is `skills-lock.json`
- [ ] Test asserts an entry exists mapping `CONTRIBUTING-template.md` →
      `CONTRIBUTING.md`

**Verification:**
- [ ] `pytest tests/test_setup_repo.py -v`
- [ ] Full suite still green

**Dependencies:** Tasks 1, 3

**Files likely touched:**
- `tests/test_setup_repo.py`

**Estimated scope:** XS (1 file)

---

## Checkpoint: After Tasks 1-4
- [ ] Full suite + lint green
- [ ] Manual scratch-repo run confirms both the removal and the addition
      behave as expected
- [ ] Review with human before proceeding to docs/polish

---

## [DONE] Task 5: Update stale references

**Description:** `README.md`'s file-tree diagram lists `skills-lock.json`
under `templates/` - remove it, add the new `CONTRIBUTING-template.md`
entry in its place. Check for any other stale mentions.

**Acceptance criteria:**
- [ ] README.md's directory tree reflects the actual `templates/`
      contents post-change
- [ ] `grep -rn skills-lock` (repeated from Task 1, now covering docs
      prose too) is empty

**Verification:**
- [ ] Visual diff of the file-tree block

**Dependencies:** Tasks 1-3

**Files likely touched:**
- `README.md`

**Estimated scope:** XS (1 file)

---

## [DONE] Task 6: CHANGELOG + version bump

**Description:** Document both halves (removal + addition) under a fresh
`[Unreleased]` section; bump version. Given this removes a
previously-distributed file, treat as a minor bump at minimum (same
reasoning as the addons-path override - new/changed distributed surface).

**Acceptance criteria:**
- [ ] CHANGELOG documents the `skills-lock.json` removal and the
      `CONTRIBUTING.md` addition as separate, clear entries
- [ ] Version bumped in `pyproject.toml` and `__init__.py`

**Verification:**
- [ ] `pytest tests/` and `scripts/lint.sh` green

**Dependencies:** Tasks 1-5

**Files likely touched:**
- `CHANGELOG.md`
- `pyproject.toml`
- `src/solt_pre_commit/__init__.py`

**Estimated scope:** XS (3 files, no logic changes)

---

## Checkpoint: Complete
- [ ] All acceptance criteria across all 6 tasks met
- [ ] Full suite + lint green
- [ ] Ready to commit/PR
