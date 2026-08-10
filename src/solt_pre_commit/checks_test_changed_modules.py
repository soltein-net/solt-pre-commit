# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Run tests against the Odoo modules changed in this push.

Wired at the `pre-push` stage. By the time a push happens there is normally
nothing staged (everything's already committed), so SoltConfig's changed-files
detection falls through its UNKNOWN-context path: try staged files (empty),
then fall back to the CI-style base-branch diff. That fallback is exactly the
"everything introduced by this push" diff we want, so this hook needs no
git pre-push stdin parsing of its own - it just asks SoltConfig for the
changed files the same way solt-check-odoo does for staged files.

Runs only when the current branch has an open PR (github_pr.py), per
docs/pipeline-strategy.md's "Pipeline at a glance": the Test tier fires on
"PR opened/updated", not on every push, and that includes this local-Docker
instantiation of the tier, not just CI. The first, PR-less push of a branch
is exempt; every push after a PR exists runs the suite before it even leaves
the machine. If PR state can't be determined at all (no `gh` session, no
GITHUB_TOKEN, remote isn't GitHub), this fails open and runs the tests rather
than silently skipping on an answer it doesn't actually have. Set
`test_require_open_pr: false` in .solt-hooks.yaml to always run regardless of
PR state (the old, unconditional behavior).

Test execution itself lives in odoo_test_runner.py (creates a scratch DB,
runs `coverage run odoo-bin ... --test-tags=/<module>,...`, drops the DB),
called in-process here rather than shelling out to a script - every repo
consuming solt-pre-commit gets the same behavior automatically as the pin
gets bumped, instead of each repo needing its own copy. `test_harness_script`
in .solt-hooks.yaml is an escape hatch for repos whose setup doesn't fit the
built-in runner's assumptions (odoo-bin + odoo.conf at conventional paths).
"""

import argparse
import subprocess
import sys
from pathlib import Path

from . import github_pr, odoo_test_runner
from .checks_odoo_module import _detect_modules_from_paths
from .config_loader import SoltConfig


def _detect_all_modules(repo_root: Path) -> list:
    """Every Odoo module this repo itself ships, regardless of what changed -
    the same universe CI's Test job installs together (setup-repo.py's
    detect_modules(), which is what populates solt-validate.yml's `modules:`
    input). Used by test_scope: full so a local pre-push run can catch a
    conflict that only surfaces once installed alongside a sibling module the
    current diff didn't touch (see test_scope's own docstring in
    config_loader.py for why "changed" alone can miss that class of bug).
    """
    return sorted({manifest.parent for manifest in repo_root.rglob("__manifest__.py")})


def main():
    parser = argparse.ArgumentParser(
        description="Run tests for Odoo modules changed vs. the base branch.",
    )
    parser.add_argument("--config", default=None, help="Path to .solt-hooks.yaml")
    parser.add_argument("--harness", default=None, help="Override test_harness_script for this run")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress skip/info messages")
    args = parser.parse_args()

    config = SoltConfig(args.config)

    if config.test_require_open_pr:
        pr_open = github_pr.has_open_pull_request()
        if pr_open is False:
            if not args.quiet:
                print(
                    "[solt-test-changed-modules] No open PR for this branch yet - "
                    "skipping the test run (it'll run once a PR is open and you push again)."
                )
            sys.exit(0)
        if pr_open is None and not args.quiet:
            print(
                "[solt-test-changed-modules] Could not determine PR state "
                "(no authenticated `gh` session or GITHUB_TOKEN) - running tests to be safe."
            )

    if config.test_scope == "full":
        # This repo's OWN top-level, not find_env_root(): that resolves to the
        # monorepo superproject when this repo is a checked-out submodule, and
        # scanning THAT would pull in every sibling repo's modules too, not
        # just this repo's own - CI's Test job only ever installs the one
        # repo's modules plus whatever `sibling-repos` supplies as already-
        # separate clones alongside it.
        repo_root = Path.cwd()
        try:
            result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
            repo_root = Path(result.stdout.strip())
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        modules = _detect_all_modules(repo_root)
        if not modules:
            if not args.quiet:
                print("[solt-test-changed-modules] test_scope: full, but no Odoo modules found in this repo, skipping.")
            sys.exit(0)
    else:
        changed_files = config.changed_detector.get_changed_files()

        if not changed_files:
            if not args.quiet:
                print("[solt-test-changed-modules] No changed files detected, skipping.")
            sys.exit(0)

        modules = _detect_modules_from_paths(sorted(changed_files))
        if not modules:
            if not args.quiet:
                print("[solt-test-changed-modules] No Odoo modules among changed files, skipping.")
            sys.exit(0)

    module_names = [Path(m).name for m in modules]
    scope_label = "all module(s) in this repo" if config.test_scope == "full" else "changed module(s)"
    print(f"[solt-test-changed-modules] Testing {scope_label}: {', '.join(module_names)}")

    harness_rel = args.harness or config.test_harness_script
    if harness_rel:
        env_root = odoo_test_runner.find_env_root()
        harness_path = env_root / harness_rel
        if not harness_path.exists():
            if not args.quiet:
                print(
                    f"[solt-test-changed-modules] test_harness_script set to {harness_rel}, but it doesn't exist there."
                )
            sys.exit(1)
        result = subprocess.run([str(harness_path), ",".join(module_names)], cwd=str(env_root))
        sys.exit(result.returncode)

    sys.exit(odoo_test_runner.run(module_names, config))


if __name__ == "__main__":
    main()
