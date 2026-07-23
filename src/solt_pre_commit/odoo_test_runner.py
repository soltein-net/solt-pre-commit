# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Run Odoo tests for one or more modules against a disposable scratch database.

Centralized here (rather than a script duplicated per repo) so every solt-*
repo gets the same test-running behavior automatically as solt-pre-commit's
pin gets bumped, instead of each repo maintaining its own copy.

Works identically inside a devcontainer (Postgres reachable via DB_HOST=postgres,
already exported through .devcontainer/*/env_file) and against a bare-source
checkout (export DB_HOST/DB_PORT/DB_USER/DB_PASSWORD for your own local Postgres).
No separate ephemeral-Postgres container needed: the scratch DB is created and
dropped in whatever Postgres is already reachable.

Odoo's ThreadedServer spawns its HTTP thread whenever --test-enable is set, even
with --stop-after-init, because HttpCase tests need a live server to call
(server.py: `test_mode = config['test_enable'] or ...; if test_mode or (...):
self.http_spawn()`, unconditional on --stop-after-init). It binds
--http-port/--gevent-port from the conf, which is normally the same ports an
interactive dev server already holds - the spawn happens in a daemon thread, so
a bind conflict there doesn't crash the run (it fails silently in the
background instead), but any HttpCase test in the module then can't actually
reach a server and fails or hangs. Dedicated ports here remove the conflict
instead of requiring the dev server to be stopped first.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from .config_loader import SoltConfig


def find_env_root() -> Path:
    """The Odoo environment root: the git superproject working tree when this
    repo is a submodule of a checked-out super-repo (e.g. a solt-* addon repo
    under soltein), otherwise this repo's own top level.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-superproject-working-tree"],
            capture_output=True,
            text=True,
            check=True,
        )
        superproject = result.stdout.strip()
        if superproject:
            return Path(superproject)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def _resolve_odoo_conf(config: SoltConfig, env_root: Path) -> Path:
    if config.test_odoo_conf:
        return env_root / config.test_odoo_conf
    version = config.get_odoo_version()
    major = version.split(".")[0]
    return env_root / f".devcontainer/dev_{major}/odoo.conf"


def run(modules: list, config: SoltConfig, env_root: Path | None = None) -> int:
    """Run the given modules' own tests against a scratch DB. Returns the exit
    code to propagate (0 = pass, nonzero = fail or error).
    """
    env_root = env_root or find_env_root()
    odoo_bin = env_root / config.test_odoo_bin
    odoo_conf = _resolve_odoo_conf(config, env_root)

    if not odoo_bin.exists():
        print(f"[solt-test-module] No odoo-bin at {odoo_bin}, cannot run tests.", file=sys.stderr)
        return 1
    if not odoo_conf.exists():
        print(f"[solt-test-module] No odoo.conf at {odoo_conf}, cannot run tests.", file=sys.stderr)
        return 1

    test_tags = ",".join(f"/{m}" for m in modules)
    scratch_db = f"test_scratch_{os.getpid()}"

    env = os.environ.copy()
    env["PGPASSWORD"] = config.test_db_password

    def _dropdb():
        subprocess.run(
            [
                "dropdb",
                "-h", config.test_db_host,
                "-p", config.test_db_port,
                "-U", config.test_db_user,
                "--if-exists", scratch_db,
            ],
            env=env,
            capture_output=True,
        )

    print(f"Creating scratch database: {scratch_db}")
    createdb = subprocess.run(
        [
            "createdb",
            "-h", config.test_db_host,
            "-p", config.test_db_port,
            "-U", config.test_db_user,
            scratch_db,
        ],
        env=env,
    )
    if createdb.returncode != 0:
        return createdb.returncode

    modules_arg = ",".join(modules)
    print(f"Running tests for: {modules_arg} (test-tags: {test_tags})")

    result_log = tempfile.NamedTemporaryFile(mode="w+", delete=False)
    try:
        # --logfile= (empty) overrides the conf's `logfile` setting so output lands here,
        # not in a shared log file an interactive dev server might also be writing to.
        # --log-handler=:WARNING drops the INFO-level "Loading module X (n/N)" firehose -
        # per-test FAIL/ERROR lines and the final "N failed, M error(s) of K tests" summary
        # are already logged at WARNING/ERROR, so nothing evidentiary is lost, just the noise.
        proc = subprocess.Popen(
            [
                "coverage", "run", str(odoo_bin),
                "-c", str(odoo_conf),
                "-d", scratch_db,
                f"--db_host={config.test_db_host}",
                f"--db_port={config.test_db_port}",
                f"--db_user={config.test_db_user}",
                f"--db_password={config.test_db_password}",
                f"--http-port={config.test_http_port}",
                f"--gevent-port={config.test_gevent_port}",
                "--logfile=",
                "--log-handler=:WARNING",
                f"--test-tags={test_tags}",
                "--stop-after-init",
                "-i", modules_arg,
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        summary = ""
        for line in proc.stdout:
            print(line, end="")
            result_log.write(line)
            if "failed," in line and "error(s) of" in line and "tests" in line:
                summary = line.strip()
        result = proc.wait()
    finally:
        result_log.close()
        os.unlink(result_log.name)
        _dropdb()

    print("=" * 60)
    if result == 0:
        print(f"PASS -- safe to push ({modules_arg})")
        if summary:
            print(f"  {summary}")
    else:
        print(f"FAIL -- do NOT push ({modules_arg})")
        if summary:
            print(f"  {summary}")
        print(f"  (exit code {result} -- see output above for the failing test/traceback)")
    print("=" * 60)

    _report_coverage(modules, env_root)

    return result


def _report_coverage(modules: list, env_root: Path) -> None:
    """Surface what `coverage run` just collected: a terminal summary right away,
    plus coverage.xml/htmlcov so an editor extension (VS Code's Coverage Gutters
    reads coverage.xml automatically) or a browser can show it. `*/<module>/*`
    (not a bare `*<module>*`) because coverage's include/omit patterns follow
    gitignore semantics: a pattern with no `/` matches only the file's basename,
    not any substring of its path - a slash-free pattern here would silently
    match nothing. The leading `*/` also covers both the super-repo's nested
    addons/<repo>/<module> paths and a standalone addon repo checkout (module
    at the repo root), since this same runner executes in both contexts.
    Best-effort: a reporting hiccup here must never turn a passing test run red.
    """
    include = ",".join(f"*/{m}/*" for m in modules)
    print("\nCoverage:")
    try:
        subprocess.run(["coverage", "report", "-m", f"--include={include}"], cwd=str(env_root))
        subprocess.run(["coverage", "xml", f"--include={include}", "-o", "coverage.xml"], cwd=str(env_root), capture_output=True)
        subprocess.run(["coverage", "html", f"--include={include}", "-d", "htmlcov"], cwd=str(env_root), capture_output=True)
        print(f"HTML report: {env_root / 'htmlcov' / 'index.html'}")
        print("coverage.xml written -- VS Code's Coverage Gutters picks this up automatically.")
    except FileNotFoundError:
        print("[solt-test-module] `coverage` not on PATH, skipping report.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Run Odoo tests for one or more modules against a disposable scratch database.",
    )
    parser.add_argument("modules", help="Comma-separated module names, e.g. llm_crm or solt_hr,solt_hr_payroll")
    parser.add_argument("--config", default=None, help="Path to .solt-hooks.yaml")
    args = parser.parse_args()

    config = SoltConfig(args.config)
    modules = [m.strip() for m in args.modules.split(",") if m.strip()]
    if not modules:
        parser.error("no modules given")

    sys.exit(run(modules, config))


if __name__ == "__main__":
    main()
