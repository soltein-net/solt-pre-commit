# Implementation Plan: Consolidate Odoo test-execution logic (local vs. CI)

Spec: `docs/SPEC-consolidate-test-execution.md`

## Overview

Give `odoo_test_runner.py` an addons-path override, then migrate CI's
`Test` job (`solt-coverage.yml`) to call the shared `solt-test-module`
CLI instead of its own hand-written `coverage run odoo-bin ...`
invocation - eliminating the drift already found (CI's password exposed
as a plain CLI arg vs. the local runner's `PGPASSWORD` env var).

## Architecture Decisions

- **Addons-path override shape:** a new `--addons-path` CLI flag on
  `solt-test-module`, threaded to `run(modules, config, addons_path=None)`.
  Appends `--addons-path=<value>` to the odoo-bin invocation only when
  provided; omitted entirely otherwise (byte-for-byte current behavior
  preserved). Rationale: CI's addons-path is computed fresh per run from
  a dynamic sibling-repo list - a CLI flag fits that better than a static
  `.solt-hooks.yaml` key would.
- **DB naming (resolves spec Open Question 2):** CI switches to the
  shared function's own `test_scratch_<pid>` create/drop cycle, dropping
  its separate `createdb -d ci_coverage` line entirely. Nothing else in
  the workflow references the `ci_coverage` name (coverage `--include=`
  filtering is by module path, not DB name), so this is a safe
  simplification, not just a compatibility shim.
- **Coverage job-summary reporting (resolves spec Open Question 3):**
  stays CI-only. `odoo_test_runner.py`'s own coverage output
  (terminal + `coverage.xml` + `htmlcov/`) is unchanged; CI's existing
  separate "Coverage report" step keeps reading the same `.coverage` data
  file afterward (`coverage` persists it in the working directory
  regardless of which command invoked `coverage run`) and keeps writing
  the GitHub job-summary markdown exactly as it does today - it just runs
  after the new shared call instead of after the old inline block.
- **Rollout is two releases, not one** (see Risks) - this is the single
  most important scheduling fact from this plan, surfaced here so it
  isn't missed during implementation.

## Dependency Graph

```
Task 1: odoo_test_runner.py --addons-path override
    │
    ├── Task 2: unit tests for the override
    │       │
    │       └── Task 5: CHANGELOG + version bump (Slice A release)
    │               │
    │               ▼
    │         [ v1.2.0 tagged - Task 4 cannot start before this exists ]
    │               │
    └───────────────┴── Task 4: solt-coverage.yml calls solt-test-module
                            │
                            └── Task 6: CHANGELOG + spec update (Slice B)
```

## Task List

### Phase 1: Local runner gains the override (Slice A - independently mergeable)

- [ ] Task 1: Add `--addons-path` override to `odoo_test_runner.py`
- [ ] Task 2: Unit tests for the override

### Checkpoint: Phase 1
- [ ] `pytest tests/` full suite green
- [ ] `scripts/lint.sh` clean
- [ ] Confirmed: omitting `--addons-path` reproduces the exact current
      subprocess command (no regression for existing callers/consumers)
- [ ] Review with human before proceeding

### Phase 2: Ship Slice A as its own release

- [ ] Task 5: CHANGELOG + version bump for the override

### Checkpoint: Phase 2 - HARD STOP
- [ ] PR merged, tag pushed (e.g. `v1.2.0`) - **Task 4 cannot begin
      before this tag exists**, since CI needs to `pip install
      solt-pre-commit==<that version>`
- [ ] Confirm with human before starting Phase 3

### Phase 3: Migrate CI to the shared runner (Slice B)

- [ ] Task 4: `solt-coverage.yml` calls `solt-test-module` instead of its
      own inline `coverage run odoo-bin ...`

### Checkpoint: Phase 3
- [ ] YAML parses (`yaml.safe_load`)
- [ ] No `--db_password` (or any secret) appears as a plain CLI arg
      anywhere in the file
- [ ] **Cannot be verified by local execution** (no Postgres/Odoo in this
      sandbox, confirmed) - explicit human sign-off required on a real
      PR's `Test`/`Integration Test` check runs before merging, not
      assumed from a clean diff alone

### Phase 4: Polish

- [ ] Task 6: CHANGELOG for Slice B + update spec's Open Questions with
      the resolutions recorded above

### Checkpoint: Complete
- [ ] All Success Criteria in the spec are met
- [ ] Spec's Open Questions section reflects final decisions, not
      pending questions

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Task 4 needs a *published* solt-pre-commit version containing Task 1's flag - can't land in the same PR | High (blocks Phase 3 entirely if missed) | Explicit hard-stop checkpoint after Phase 2; Task 4 is not started until the tag exists |
| Zero ability to execute/verify CI's Odoo test run locally (no Postgres, no `odoo` package in this sandbox) | High (Phase 3 changes are effectively unverified until a real PR runs) | Human reviews real CI check results on the actual PR before merging Phase 3 - not treated as done on diff-review alone |
| `solt-coverage.yml` is a *reusable* workflow other repos call at a pinned tag | Low (per spec assumption 6, already-pinned consumers are unaffected until they bump their pin) | No special mitigation needed beyond normal review; called out so it isn't mistaken for an urgent/breaking change |
| Removing CI's own `createdb -d ci_coverage` might miss a hidden reference elsewhere (e.g. a follow-up step, a badge, a log parser) | Medium | Grep `ci_coverage` across `.github/workflows/` before removing, as part of Task 4's own verification, not assumed safe from this plan alone |

## Open Questions

None remaining from the spec - all three were resolved during planning
(see Architecture Decisions). Task 6 records these resolutions back into
the spec document itself, per "keeping the spec alive."
