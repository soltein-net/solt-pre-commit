notice in solt-suit repo, pr 786, github ci run, Changed-module detection found: website_solt_sale_offer but then it endup making a full test run, somewhere at logs i read it was caused by website_solt_sale_offer not being in the modules list.

i have see this several times now, developers forget to update the modules list when adding new modules, which causes the changed-module detection to behave unexpectedly.

so, why do we need to keep the modules list updated? why dont we just autodetect all the modules present in the repository?

if the argument is: there may be modules that are not meant to be included in the test run, we could add a mechanism to exclude them explicitly rather than relying on a manually maintained list.

Investigation result
-------------------
First pass (incomplete): the detection code itself (`_detect_modules_from_paths()` in
`checks_odoo_module.py`, and the manifest-scanning full-scope runner in
`checks_test_changed_modules.py`) doesn't rely on a hand-maintained allowlist - it
correctly resolves modules from git-diff paths / `__manifest__.py` discovery. That's
true, but it's not the whole picture: it describes the *local pre-commit tool*, not
what actually ran in PR 786's CI. The declared `modules:` list is not inert there.

What actually happens in `solt-coverage.yml` (the workflow PR 786's CI ran):
- The `Detect`/`Coverage` jobs receive `inputs.modules`, a space-separated string that
  `setup-repo.py regenerate` bakes into this repo's own `.github/workflows/solt-validate.yml`
  as `modules: '...'` (see that file's `modules:` line, and `solt-validate.yml`'s own
  "Check committed module list for drift" step, which already warns when this drifts
  from disk).
- For `scope: changed`, both the `Detect` job and the `Coverage` job's "Run tests with
  coverage" step independently run `_detect_modules_from_paths()` against the PR diff -
  this is where `"Changed-module detection found: website_solt_sale_offer"` comes from,
  and detection did work correctly here.
- That detected set is then **intersected against `inputs.modules`** (`DECLARED=",$MODULES_CSV,"`
  in both jobs). `website_solt_sale_offer` wasn't in the committed `modules:` string (nobody
  had re-run `setup-repo.py regenerate` since it was added), so the intersection came up
  empty, and the code hit its documented fallback: "no declared module matched - falling
  back to the full list". That's the full test run seen in the logs - not a bug in
  detection, but the declared list gating what detection is allowed to act on.

Why the intersection exists at all (not just noise-filtering):
`inputs.modules` is more than a name list - `setup-repo.py` also derives
`sibling-repos`, `postgres-image`, `python-version`, etc. from the same declared set,
so it represents the universe of modules this specific CI job is actually *configured*
to install and run, not merely "every module that happens to exist on disk". The
intersection is a deliberate safety allowlist: if a changed path maps to a module name
the job doesn't recognize, that's treated as ambiguous (possibly a module this job
was never wired up to install/test) and it conservatively falls back to the full
declared run instead of either silently skipping it or trying to test an unconfigured
module directly. That fallback logic is sound - the problem is that its input
(`inputs.modules`) is a manually-regenerated snapshot with no enforcement, so it goes
stale exactly when a repo adds a module and forgets to run the regeneration script,
which is the recurring pattern from this issue.

Refinement: once both sides of the intersection are live-computed, its job shrinks.
`_detect_modules_from_paths()` only ever returns a name for which it found a manifest,
so a changed module is already structurally a subset of "every manifest currently on
disk" - the "does the job even recognize this module" concern the intersection covers
today goes away once the declared side stops being a stale snapshot and becomes that
same live scan. What's actually left for the intersection to do, once the full list is
`find`-based and an explicit `exclude_modules` exists:
1. Subtract `exclude_modules` - a diff can still touch a module someone deliberately
   excluded from testing; something has to filter it out of the changed set. This is
   the one thing an exclude list doesn't do by itself.
2. Nothing else. Correction to an earlier pass of this investigation: it was assumed
   `_detect_modules_from_paths()` could still name a module whose `__manifest__.py` was
   removed in the same diff, requiring the intersection to filter it out separately.
   Verified against the actual implementation (`checks_odoo_module.py`) - it isn't true.
   `_find_module_from_file()` walks up from the changed path checking
   `(path / manifest_name).exists()` against the *current* checkout, so a module whose
   manifest no longer exists there can never be returned as "changed" in the first
   place. There is no deleted-module case for the intersection to guard against.
3. The old "no match -> fall back to full run" behavior should be dropped, not kept.
   That fallback only made sense when "unmatched" was ambiguous (genuinely excluded, or
   just a forgotten regeneration). Once the eligible set is
   `manifests_on_disk - exclude_modules`, "unmatched" means exactly "excluded" (per
   point 2, it can no longer mean "deleted") - there's nothing left to hedge against by
   re-running everything. The correct behavior is to drop that module from the run (or
   skip the run entirely if that empties the changed set), not silently re-include the
   thing someone excluded.

This means the real design should be:
1. Stop sourcing the declared/eligible set from a manually-regenerated string. Compute
   it live the same way `find-modules` in `solt-validate.yml` already does: scan for
   `__manifest__.py` at run time, same as the full-scope runner.
2. Provide an explicit exclusion mechanism (`exclude_modules` in `.solt-hooks.yaml`,
   read via `SoltConfig` - shared automatically by the local pre-push hook and CI,
   rather than a CI-only workflow input) for modules that are intentionally out of
   scope for a given repo/test job, instead of relying on omission from a
   hand-maintained list.
3. Keep a narrow intersection step - changed ∩ (live-manifest-scan − exclude_modules) -
   purely to enforce exclusions, with no full-run fallback.
4. Promote `solt-validate.yml`'s existing drift-check from a warning to something that
   either blocks the PR or auto-regenerates `sibling-repos`/`postgres-image`/etc. for
   any caller still keying that config off a generated snapshot, so staleness there
   can't silently change CI behavior the way the `modules:` list did in PR 786.

Yes, `inputs.modules` (the caller-supplied, `setup-repo.py`-generated `modules: '...'`
string) goes away as the authoritative "what to test" source. Both `full` and `changed`
scope stop reading it and instead scan the already-checked-out `repo/` for
`__manifest__.py`, same as `solt-validate.yml`'s own `find-modules` step and the local
pre-push hook's `_detect_all_modules()` already do. The only caller-supplied,
hand-maintained setting that remains is `exclude_modules` in `.solt-hooks.yaml`.

This does *not* remove `sibling-repos`, `postgres-image`, or `python-version` from the
generated workflow - confirmed in `setup-repo.py`: `detect_sibling_repos()` and
`detect_postgres_image()` already take their own independent `detect_modules()` scan
result as input, not the generated `modules:` string, so they're unaffected by dropping
it. Those still need `setup-repo.py regenerate` to stay current (e.g. a new module
declaring a Postgres extension), so the drift-check in point 4 above still has a job -
just no longer for `modules:` itself, only for the config that can't be derived at CI
run time.

Resolved
--------
Implemented as designed above:
- `.solt-hooks.yaml` gained `exclude_modules` (`config_loader.py`'s `SoltConfig`), the
  only hand-maintained setting left in this design.
- The local pre-push hook (`checks_test_changed_modules.py`) now filters both its
  full-scope and changed-scope module lists through `exclude_modules`.
- `solt-coverage.yml` no longer takes a `modules` input at all. Its `Detect` and
  `Coverage` jobs now live-scan the checked-out repo for `__manifest__.py` (minus
  `exclude_modules`) wherever they previously read `inputs.modules`, and the
  "no declared module matched -> fall back to full" branches were removed - an
  unmatched changed module now just means "excluded", so it's dropped (or the whole
  run is skipped if that empties the changed set), never used to trigger a full run.
- `setup-repo.py` and the generated `templates/github-workflows/solt-validate.yml` no
  longer emit a `modules:` line on the `solt-coverage.yml` calls, and
  `solt-validate.yml`'s own now-obsolete "Check committed module list for drift" step
  (which grepped for that line) was removed.
- `sibling-repos`, `postgres-image`, `python-version` are unaffected, still generated
  by `setup-repo.py regenerate` from its own independent manifest scan.

Existing consumer repos are unaffected until they bump the `@vX.Y.Z` ref they pin -
each reusable-workflow tag is self-contained, so this is not a breaking change for
anyone who hasn't upgraded yet, only for new tags going forward.

The root cause is therefore not that we need a static `declared_modules` registry, nor
that the intersection logic is dead code - it's that the intersection's *inputs* were
wrong: a manually-regenerated snapshot standing in for what should be a live manifest
scan, plus a fallback that only existed to paper over that snapshot's staleness. The
fix is to make the eligible set self-updating and let `exclude_modules` be the only
thing developers maintain by hand.