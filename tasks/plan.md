# Implementation Plan: Stop distributing agent-skills; distribute a CONTRIBUTING.md instead

## Overview

Remove `templates/skills-lock.json` from what `setup-repo.py` copies into
consumer repos - it's a half-built artifact from PR #9 (a lockfile with
no installer behind it, and no `commands/` coverage even if one existed).
In its place, add `templates/CONTRIBUTING-template.md` to the same
`FILES_TO_COPY` mechanism, covering basic consumer-repo contribution
practices plus a section on optionally installing `addyosmani/agent-skills`
via its own canonical path - explicitly *not* solt-pre-commit distributing
or vendoring that tooling itself.

## Architecture Decisions

- **Use the existing `FILES_TO_COPY` mechanism, not a new injection
  function.** `copy_file()` already has `force=True` default (overwrite)
  with `--no-force` as the existing, uniform escape hatch - the same
  pattern `.pylintrc`/`pyproject.toml`/`.solt-hooks.yaml` already use.
  README's badge injection is a *bespoke* function specifically because
  READMEs have repo-specific prose to preserve around a shared badge
  block; CONTRIBUTING.md doesn't need that - it's fine to be a fully
  solt-pre-commit-managed file like the others, with `--no-force`
  covering repos that want to keep a heavily customized one.
- **Delete `templates/skills-lock.json` outright**, not just stop copying
  it - it's unused dead weight (confirmed: no installer reads it anywhere
  in either this repo or the super-repo's own scripts).
- **Don't touch already-onboarded consumer repos.** Same precedent as
  every other template change this session: repos get the new/removed
  file the next time they run `setup-repo.py --update-only`, not
  retroactively. `solt-llm` (confirmed to already have `skills-lock.json`
  from an earlier run) keeps it until it's re-run.

## Task List

### Phase 1: Remove the unfinished distribution

- [ ] Task 1: Remove `skills-lock.json` from `FILES_TO_COPY`, delete the file

### Checkpoint: Phase 1
- [ ] `pytest tests/` green, `scripts/lint.sh` clean
- [ ] Confirmed no other code/docs reference the file before it's gone

### Phase 2: Add the CONTRIBUTING.md distribution

- [ ] Task 2: Write `templates/CONTRIBUTING-template.md`
- [ ] Task 3: Add it to `FILES_TO_COPY`
- [ ] Task 4: Regression test for `FILES_TO_COPY`'s contents

### Checkpoint: Phase 2
- [ ] `pytest tests/` green, `scripts/lint.sh` clean
- [ ] Manually verify: running `setup-repo.py` against a scratch temp repo
      produces a `CONTRIBUTING.md` with the expected content

### Phase 3: Docs + polish

- [ ] Task 5: Update README.md's file-tree diagram and any other stale
      references to `skills-lock.json`
- [ ] Task 6: CHANGELOG + version bump

### Checkpoint: Complete
- [ ] All acceptance criteria met
- [ ] Ready for review

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Deleting `skills-lock.json` breaks something unseen | Low | Already grepped this repo + super-repo scripts for readers - none found. Re-check once more right before deleting. |
| `CONTRIBUTING-template.md` content scope-creeps into a large writing task | Medium | Keep it to what's actually enforced/true for every solt-pre-commit consumer repo (branch naming, `solt-test-module`, pre-commit hooks) + the one new AI-tooling section - not a generic exhaustive contributor guide. |
| Overwriting an existing consumer `CONTRIBUTING.md` by default surprises someone | Low | Same `--no-force` escape hatch every other templated file already has - not a new risk, an existing documented convention. |

## Open Questions

- None - the mechanism choice (reuse `FILES_TO_COPY`) resolves the only
  real design decision.
