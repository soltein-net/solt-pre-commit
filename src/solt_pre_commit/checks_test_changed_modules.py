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

from . import odoo_test_runner
from .checks_odoo_module import _detect_modules_from_paths
from .config_loader import SoltConfig


def main():
    parser = argparse.ArgumentParser(
        description="Run tests for Odoo modules changed vs. the base branch.",
    )
    parser.add_argument("--config", default=None, help="Path to .solt-hooks.yaml")
    parser.add_argument("--harness", default=None, help="Override test_harness_script for this run")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress skip/info messages")
    args = parser.parse_args()

    config = SoltConfig(args.config)
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
    print(f"[solt-test-changed-modules] Testing changed module(s): {', '.join(module_names)}")

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
