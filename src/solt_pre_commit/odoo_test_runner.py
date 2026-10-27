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
import ast
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from .config_loader import SoltConfig


class _CancelledError(Exception):
    """Raised from the SIGTERM handler installed in run() below."""


def _handle_sigterm(signum, frame):
    raise _CancelledError()


def _terminate(proc: subprocess.Popen, grace_seconds: float = 10) -> None:
    """Best-effort kill of a still-running Odoo test process.

    A CI job cancellation (or a local Ctrl-C) has to reach this specific
    child - Python's default SIGTERM handling terminates the *wrapper*
    process immediately, without running any `finally` block, which leaves
    `proc` (odoo-bin, still holding the scratch DB connection and burning
    CPU) as an orphan that GitHub Actions' own cancellation never reliably
    reaps on its own. `run()` installs a SIGTERM handler that turns it into
    a normal Python exception specifically so this function gets a chance
    to run before the wrapper actually exits.
    """
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


# Exit code when the idle watchdog stops a hung run (same as coreutils `timeout`).
EXIT_IDLE_TIMEOUT = 124


def _idle_watchdog(
    proc: subprocess.Popen,
    last_output: list,
    idle_seconds: float,
    fired: threading.Event,
    done: threading.Event,
    poll_seconds: float = 15,
) -> None:
    """Stop `proc` if it prints nothing for `idle_seconds`.

    A test stuck on something that never returns (a live network call, a DB
    lock) leaves odoo-bin alive but silent, and without this the run - a CI
    shard, the release gate, a pre-push hook - waits on it forever. Idle-based
    on purpose, not a total cap: a long run that keeps logging is never
    stopped. `last_output[0]` is a time.monotonic() stamp the reader loop
    refreshes on every line. Runs in a daemon thread; `done` ends it.
    """
    while not done.wait(poll_seconds):
        if proc.poll() is not None:
            return
        idle = time.monotonic() - last_output[0]
        if idle > idle_seconds:
            fired.set()
            print(
                f"\n[solt-test-module] No output for {int(idle // 60)} min (limit {int(idle_seconds // 60)} min) "
                "- treating the run as hung and stopping it.",
                file=sys.stderr,
            )
            _terminate(proc)
            return


# Run in the scratch DB before Odoo creates anything in it: every ordinary table created there from then on (its
# TOAST table too) is left out of autovacuum. Temporary tables are never autovacuumed and partitioned parents hold no
# rows, so both are skipped rather than altered.
SCRATCH_DB_WITHOUT_AUTOVACUUM_SQL = """
CREATE FUNCTION solt_test_disable_autovacuum() RETURNS event_trigger LANGUAGE plpgsql AS $$
DECLARE
    created_table record;
BEGIN
    FOR created_table IN
        SELECT command.objid::regclass AS table_name
        FROM pg_event_trigger_ddl_commands() AS command
        JOIN pg_class ON pg_class.oid = command.objid
        WHERE command.object_type = 'table' AND pg_class.relkind = 'r' AND pg_class.relpersistence <> 't'
    LOOP
        EXECUTE format(
            'ALTER TABLE %s SET (autovacuum_enabled = false, toast.autovacuum_enabled = false)',
            created_table.table_name
        );
    END LOOP;
END
$$;
CREATE EVENT TRIGGER solt_test_disable_autovacuum ON ddl_command_end
    WHEN TAG IN ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
    EXECUTE FUNCTION solt_test_disable_autovacuum();
"""


def _keep_autovacuum_out(config: SoltConfig, scratch_db: str, env: dict) -> None:
    """Keep autovacuum away from every table Odoo is about to create in ``scratch_db``.

    Each test runs in one transaction that is rolled back. When autovacuum reaches a table while an open test
    transaction holds its only rows, it records the table's pages with zero rows; the planner then estimates the
    table as empty and a join over it degenerates into nested loops, seconds per query, for as long as the run
    lasts. The rolled-back rows of the earlier tests are what send autovacuum there in the first place.

    Must run before odoo-bin starts. Creating the event trigger takes a superuser: for any other role the run goes
    on with autovacuum on, and a warning says so.
    """
    try:
        switched_off = subprocess.run(
            [
                "psql",
                "-h",
                config.test_db_host,
                "-p",
                config.test_db_port,
                "-U",
                config.test_db_user,
                "-d",
                scratch_db,
                "-q",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                SCRATCH_DB_WITHOUT_AUTOVACUUM_SQL,
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        reason = (switched_off.stderr or "").strip() if switched_off.returncode != 0 else ""
    except FileNotFoundError:
        reason = "`psql` not on PATH"
    if reason:
        print(
            f"[solt-test-module] WARNING - autovacuum stays on in {scratch_db} ({reason}). A test that autovacuum "
            "reaches mid-run can get planner estimates of empty tables and run orders of magnitude slower.",
            file=sys.stderr,
        )


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


def _is_installable(manifest: Path) -> bool:
    """Whether this manifest declares the module installable (Odoo's own
    default is True). A manifest that can't be parsed counts as installable:
    better a visible install failure in the test run than a module silently
    dropped from it.
    """
    try:
        data = ast.literal_eval(manifest.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return True
    return bool(data.get("installable", True)) if isinstance(data, dict) else True


def installable_module_dirs(repo_root: Path) -> list:
    """Every installable Odoo module directory under repo_root - the universe
    CI's full-scope Test job installs. `installable: False` modules are left
    out: Odoo can't install them, so testing them can only ever fail or no-op.
    Does not apply exclude_modules; see eligible_modules() for that.
    """
    return sorted({manifest.parent for manifest in repo_root.rglob("__manifest__.py") if _is_installable(manifest)})


def eligible_modules(repo_root: Path, config: SoltConfig) -> list:
    """Names of the modules to test for a full-scope run: installable modules
    minus `exclude_modules` from .solt-hooks.yaml. The single definition shared
    by `solt-test-module --all`, the pre-push hook's test_scope: full, and CI's
    Detect/Coverage jobs, so none of them can drift from the others.
    """
    excluded = set(config.exclude_modules)
    return sorted({d.name for d in installable_module_dirs(repo_root)} - excluded)


def _resolve_odoo_conf(config: SoltConfig, env_root: Path) -> Path:
    if config.test_odoo_conf:
        return env_root / config.test_odoo_conf
    version = config.get_odoo_version()
    major = version.split(".")[0]
    return env_root / f".devcontainer/dev_{major}/odoo.conf"


def resolve_ports(config: SoltConfig, http_port: int | None, gevent_port: int | None) -> tuple[str, str]:
    """The ``(http, gevent)`` ports Odoo's test server binds.

    Default: the config's (``test_http_port`` / ``test_gevent_port``). ``http_port`` alone moves the gevent port
    with it, keeping the gap the config has between the two, so one option is enough to run beside another run.
    ``gevent_port`` alone replaces only the gevent port.
    """
    if http_port is None and gevent_port is None:
        return str(config.test_http_port), str(config.test_gevent_port)
    http = str(http_port) if http_port is not None else str(config.test_http_port)
    if gevent_port is not None:
        return http, str(gevent_port)
    gap = int(config.test_gevent_port) - int(config.test_http_port)
    return http, str(http_port + gap)


def run(
    modules: list,
    config: SoltConfig,
    env_root: Path | None = None,
    addons_path: str | None = None,
    strict: bool = False,
    http_port: int | None = None,
    gevent_port: int | None = None,
    install_modules: list | None = None,
    coverage_file: str | None = None,
) -> int:
    """Run the given modules' own tests against a scratch DB. Returns the exit
    code to propagate (0 = pass, nonzero = fail or error).

    install_modules: modules to install (``-i``) when that is more than the ones being tested; omitted,
    exactly ``modules`` are installed. A shard of a full run passes every eligible module here and only its
    own share as ``modules``, so each shard runs against the same installed registry as an unsharded run
    (installing only a shard's modules would let a test pass for want of a module that is there in the real
    suite). Tests are selected by ``modules`` alone.

    coverage_file: write this run's coverage data to its own file instead of the shared ``.coverage``, and
    leave the shared ``coverage.xml``/``htmlcov`` alone: shards run side by side and would otherwise append
    to, and overwrite, each other's.

    addons_path: optional --addons-path override for odoo-bin. Omitted by
    default (None) - local/devcontainer callers rely on the resolved
    odoo.conf's own addons_path setting. CI passes this explicitly since its
    addons-path is assembled fresh each run from cloned sibling repos, not a
    static conf file.

    strict: fail (return 1) instead of skipping when the Odoo environment is
    missing. Off for the pre-push hook, where a missing local environment
    shouldn't block a push; on for `--all`, where "nothing ran" must never
    read as a pass.

    http_port, gevent_port: override the config's test ports (see ``resolve_ports``), so two runs
    can be active at once: a run whose port is taken by another dies at startup.
    """
    env_root = env_root or find_env_root()
    odoo_bin = env_root / config.test_odoo_bin
    odoo_conf = _resolve_odoo_conf(config, env_root)

    if not odoo_bin.exists() or not odoo_conf.exists():
        # A missing local Odoo environment is a setup problem, not a test
        # failure - it shouldn't block the push the way a real failure does.
        # `SKIP=solt-test-changed-modules git push` (pre-commit's own
        # built-in mechanism) bypasses this hook entirely if that's what's
        # actually wanted instead.
        missing = odoo_bin if not odoo_bin.exists() else odoo_conf
        if strict:
            print(f"[solt-test-module] FAIL - no Odoo environment found ({missing} doesn't exist).", file=sys.stderr)
            return 1
        print(
            f"[solt-test-module] SKIPPED - no Odoo environment found ({missing} doesn't exist). "
            "Not a test failure - set test_odoo_bin/test_odoo_conf in .solt-hooks.yaml if this "
            "path is wrong for your setup.",
            file=sys.stderr,
        )
        return 0

    http, gevent = resolve_ports(config, http_port, gevent_port)
    test_tags = ",".join(f"/{m}" for m in modules)
    scratch_db = f"test_scratch_{os.getpid()}"

    env = os.environ.copy()
    env["PGPASSWORD"] = config.test_db_password
    if coverage_file:
        env["COVERAGE_FILE"] = coverage_file
    if config.test_modules_auto_install_disabled:
        # Read directly by module_change_auto_install's post_load patch (see its
        # own README) - only takes effect if that module is also server-wide
        # (test_server_wide_modules below), since it needs to run before Odoo
        # decides what to auto-install, not after.
        env["ODOO_MODULES_AUTO_INSTALL_DISABLED"] = ",".join(config.test_modules_auto_install_disabled)

    def _dropdb():
        subprocess.run(
            [
                "dropdb",
                "-h",
                config.test_db_host,
                "-p",
                config.test_db_port,
                "-U",
                config.test_db_user,
                "--if-exists",
                scratch_db,
            ],
            env=env,
            capture_output=True,
        )

    # Drop first too: self-heals from a prior run that got killed before its
    # own cleanup ran and left a same-named scratch DB behind.
    _dropdb()

    print(f"Creating scratch database: {scratch_db}")
    createdb = subprocess.run(
        [
            "createdb",
            "-h",
            config.test_db_host,
            "-p",
            config.test_db_port,
            "-U",
            config.test_db_user,
            scratch_db,
        ],
        env=env,
    )
    if createdb.returncode != 0:
        return createdb.returncode
    _keep_autovacuum_out(config, scratch_db, env)

    modules_arg = ",".join(modules)
    install_arg = ",".join(install_modules) if install_modules else modules_arg
    print(f"Running tests for: {modules_arg} (test-tags: {test_tags})")
    if install_arg != modules_arg:
        print(f"Installing {len(install_modules)} module(s), testing {len(modules)} of them")

    proc = None
    previous_sigterm_handler = signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        try:
            # --logfile= (empty) overrides the conf's `logfile` setting so output lands here,
            # not in a shared log file an interactive dev server might also be writing to.
            # --log-handler=:WARNING drops the INFO-level firehose in general - per-test
            # FAIL/ERROR lines and the final "N failed, M error(s) of K tests" summary are
            # already logged at WARNING/ERROR, so nothing evidentiary is lost, just the noise.
            #
            # --log-handler=odoo.modules.loading:INFO re-opens exactly one logger back up to
            # INFO on top of that: "Loading module X (n/N)" - Odoo doesn't attach a duration to
            # that line itself, but every CI log line already carries a timestamp, so the gap
            # between two consecutive "Loading module" lines is that module's own install+test
            # wall-clock cost. Without this, per-module timing simply isn't recoverable from a
            # run's log at all - the exact gap this closes: a repo can *see* that its full suite
            # took N hours but never *which* module(s) actually spent it (see solt-suite's own
            # 2h40m run, investigated purely from FAIL/ERROR line gaps for lack of anything
            # better). 146 extra lines on a 146-module repo is not the firehose the WARNING
            # default exists to avoid - it's the one thing worth re-enabling in isolation.
            # No --db_password here: PGPASSWORD is already set in env above, and psycopg2
            # (via libpq) picks it up the same way createdb/dropdb do - passing the password
            # as a plain CLI arg would otherwise make it visible to anyone on the box via
            # `ps aux`.
            odoo_bin_args = [
                "coverage",
                "run",
                # --append: without it, `coverage run` truncates the data file
                # at the start of every run, so pushing module B would erase
                # module A's data from a push five minutes earlier. Appending
                # lets the data file accumulate across pushes/modules so
                # coverage.xml (see _report_coverage) keeps reflecting every
                # module tested so far, not just the most recent one.
                "--append",
                str(odoo_bin),
                "-c",
                str(odoo_conf),
                "-d",
                scratch_db,
                f"--db_host={config.test_db_host}",
                f"--db_port={config.test_db_port}",
                f"--db_user={config.test_db_user}",
                f"--http-port={http}",
                f"--gevent-port={gevent}",
                "--logfile=",
                "--log-handler=:WARNING",
                "--log-handler=odoo.modules.loading:INFO",
                # The run's own verdict line ("0 failed, 0 error(s) of N tests") is logged at INFO when
                # nothing failed, so without this a passing run reports no test count at all: nothing can
                # tell "ran 3,000 tests" from "ran none". A caller that splits a run (see --shard) needs the
                # count to check that the pieces add up.
                "--log-handler=odoo.tests.result:INFO",
                f"--test-tags={test_tags}",
                "--stop-after-init",
            ]
            if config.test_without_demo:
                # `all` was the pre-19.0 spelling; 19.0 types this as a
                # boolean and warns on it. `True` works below 19.0 too, but by
                # accident: there the option is untyped and only tested for
                # truthiness, so any non-empty string disables demo data. Branch
                # on the version if one ever honours its "comma-separated module
                # list" help text.
                odoo_bin_args.append("--without-demo=True")
            if addons_path is not None:
                odoo_bin_args.append(f"--addons-path={addons_path}")
            if config.test_server_wide_modules:
                # dict.fromkeys: dedupes while preserving order, in case a caller
                # also lists base/web explicitly. Odoo's own --load default is
                # base,web - overriding it entirely (rather than appending) means
                # we must keep those two or lose functionality they provide.
                server_wide = dict.fromkeys(["base", "web", *config.test_server_wide_modules])
                odoo_bin_args.append(f"--load={','.join(server_wide)}")
            odoo_bin_args += ["-i", install_arg]

            proc = subprocess.Popen(
                odoo_bin_args,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except FileNotFoundError:
            print("[solt-test-module] `coverage` not on PATH, cannot run tests.", file=sys.stderr)
            return 1

        try:
            summary = ""
            last_output = [time.monotonic()]
            hung, reader_done = threading.Event(), threading.Event()
            idle_seconds = config.test_idle_timeout_minutes * 60
            threading.Thread(
                target=_idle_watchdog,
                args=(proc, last_output, idle_seconds, hung, reader_done, min(15, idle_seconds / 4)),
                daemon=True,
            ).start()
            try:
                for line in proc.stdout:
                    last_output[0] = time.monotonic()
                    print(line, end="")
                    if "failed," in line and "error(s) of" in line and "tests" in line:
                        summary = line.strip()
                result = proc.wait()
            finally:
                reader_done.set()
            if hung.is_set():
                result = EXIT_IDLE_TIMEOUT
        except (_CancelledError, KeyboardInterrupt) as exc:
            print("\n[solt-test-module] Cancelled - stopping the Odoo test process...", file=sys.stderr)
            # _terminate(proc) + _dropdb() below (the outer finally) still run
            # before this return takes effect. Conventional 128+signal exit
            # code (143 for SIGTERM, 130 for SIGINT), not a raw traceback -
            # main() just does sys.exit(run(...)), and an escaped exception
            # here would otherwise print a scary stack trace for what is, from
            # the CI job's perspective, a completely ordinary cancellation.
            return 143 if isinstance(exc, _CancelledError) else 130
    finally:
        # Runs on every exit path (normal completion, cancellation, or any
        # other exception) - proc, if still alive, must die *before* _dropdb()
        # tries to drop a DB it might still hold a connection to.
        if proc is not None:
            _terminate(proc)
        signal.signal(signal.SIGTERM, previous_sigterm_handler)
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
        if result == EXIT_IDLE_TIMEOUT:
            print(f"  (hung: no output for {config.test_idle_timeout_minutes} min -- see the last lines above)")
        else:
            print(f"  (exit code {result} -- see output above for the failing test/traceback)")
    print("=" * 60)

    _report_coverage(modules, env_root, env=env if coverage_file else None, write_files=not coverage_file)

    return result


def _report_coverage(modules: list, env_root: Path, env: dict | None = None, write_files: bool = True) -> None:
    """Surface what `coverage run` just collected: a terminal summary right away,
    plus coverage.xml/htmlcov so an editor extension (VS Code's Coverage Gutters
    reads coverage.xml automatically) or a browser can show it. `*/<module>/*`
    (not a bare `*<module>*`) because coverage's include/omit patterns follow
    gitignore semantics: a pattern with no `/` matches only the file's basename,
    not any substring of its path - a slash-free pattern here would silently
    match nothing. The leading `*/` also covers both the super-repo's nested
    addons/<repo>/<module> paths and a standalone addon repo checkout (module
    at the repo root), since this same runner executes in both contexts.

    The terminal report stays scoped to `modules` (--include) - that's what
    you just pushed, so that's what belongs in your terminal. coverage.xml/
    htmlcov are written WITHOUT that filter: `coverage run --append` (see
    call site) keeps every module's data in the same .coverage file across
    pushes, so an unfiltered xml/html export reflects everything tested so
    far, not just this push's modules - otherwise Coverage Gutters would show
    a blank gutter for any file outside whatever you pushed last.
    Best-effort: a reporting hiccup here must never turn a passing test run red.
    """
    include = ",".join(f"*/{m}/*" for m in modules)
    print("\nCoverage:")
    try:
        subprocess.run(["coverage", "report", "-m", f"--include={include}"], cwd=str(env_root), env=env)
        if write_files:
            subprocess.run(["coverage", "xml", "-o", "coverage.xml"], cwd=str(env_root), capture_output=True)
            subprocess.run(["coverage", "html", "-d", "htmlcov"], cwd=str(env_root), capture_output=True)
            print(f"HTML report: {env_root / 'htmlcov' / 'index.html'}")
            print(
                "coverage.xml written (cumulative across all modules tested so far) -- VS Code's Coverage Gutters picks this up automatically."
            )
    except FileNotFoundError:
        print("[solt-test-module] `coverage` not on PATH, skipping report.", file=sys.stderr)


def parse_shard(value: str) -> tuple[int, int]:
    """argparse type: ``I/N`` (1-based), the I-th of N shards, as ``(index, count)`` with a 0-based index."""
    try:
        position, count = (int(part) for part in value.split("/"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not I/N, e.g. 2/4") from None
    if count < 1 or not 1 <= position <= count:
        raise argparse.ArgumentTypeError(f"{value!r}: I must be between 1 and N, and N at least 1")
    return position - 1, count


def shard_modules(modules: list, index: int, count: int) -> list:
    """The share of ``modules`` that shard ``index`` of ``count`` tests.

    Taken from the sorted list in turns (module i goes to shard i % count), so the shards partition the list:
    every module is in exactly one, whatever ``count`` is, and the same inputs always give the same split.
    Turns, not contiguous blocks, so a family of similarly named (and similarly slow) modules is spread.
    """
    return sorted(modules)[index::count]


def _port(value: str) -> int:
    """argparse type: a TCP port, 1 to 65535."""
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a port number") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"{port} is not a port (1 to 65535)")
    return port


def main():
    parser = argparse.ArgumentParser(
        description="Run Odoo tests for one or more modules against a disposable scratch database.",
    )
    parser.add_argument(
        "modules",
        nargs="?",
        default=None,
        help="Comma-separated module names, e.g. llm_crm or solt_hr,solt_hr_payroll",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Test every installable module in this repo except those listed under "
            "exclude_modules in .solt-hooks.yaml (the same set CI's full-scope run tests). "
            "Fails, instead of skipping, if the Odoo environment is missing."
        ),
    )
    parser.add_argument("--config", default=None, help="Path to .solt-hooks.yaml")
    parser.add_argument(
        "--addons-path",
        default=None,
        help="Override --addons-path for odoo-bin (default: use the resolved odoo.conf's own setting)",
    )
    parser.add_argument(
        "--http-port",
        type=_port,
        default=None,
        help=(
            "Port of Odoo's test HTTP server (default: test_http_port of .solt-hooks.yaml, 18069). "
            "Give each run its own when two are active at once; the gevent port follows, at the gap the config has."
        ),
    )
    parser.add_argument(
        "--gevent-port",
        type=_port,
        default=None,
        help="Port of Odoo's test gevent (longpolling) server (default: follows --http-port, else test_gevent_port).",
    )
    parser.add_argument(
        "--shard",
        type=parse_shard,
        default=None,
        metavar="I/N",
        help=(
            "With --all: test only the I-th of N shares of the eligible modules (e.g. 2/4), but install ALL of "
            "them, so the registry is the one an unsharded run has. Run the N shards side by side, each with "
            "its own --http-port, and require every one of them to pass. Each writes its own coverage data."
        ),
    )
    args = parser.parse_args()

    config = SoltConfig(args.config)
    if args.shard and not args.all:
        parser.error("--shard needs --all")

    if args.all:
        if args.modules:
            parser.error("--all cannot be combined with an explicit module list")
        # This repo's own top level, not find_env_root(): as a submodule that resolves to
        # the superproject, and scanning it would pull in every sibling repo's modules.
        try:
            result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
            repo_root = Path(result.stdout.strip())
        except (subprocess.CalledProcessError, FileNotFoundError):
            repo_root = Path.cwd()
        modules = eligible_modules(repo_root, config)
        if not modules:
            parser.error(f"--all found no installable modules under {repo_root}")
        if config.exclude_modules:
            print(f"[solt-test-module] EXCLUDED (not tested): {', '.join(sorted(config.exclude_modules))}")
        print(f"[solt-test-module] --all: {len(modules)} module(s) under {repo_root}")
        install_modules = None
        coverage_file = None
        if args.shard:
            index, count = args.shard
            install_modules = sorted(modules)
            modules = shard_modules(modules, index, count)
            coverage_file = str(find_env_root() / f".coverage.shard-{index + 1}-{count}")
            if not modules:
                parser.error(f"shard {index + 1}/{count} has no module: there are only {len(install_modules)}")
            print(f"[solt-test-module] shard {index + 1}/{count}: testing {len(modules)} of {len(install_modules)}")
    else:
        install_modules = None
        coverage_file = None
        if not args.modules:
            parser.error("give a comma-separated module list, or --all")
        modules = [m.strip() for m in args.modules.split(",") if m.strip()]
        if not modules:
            parser.error("no modules given")

    sys.exit(
        run(
            modules,
            config,
            addons_path=args.addons_path,
            strict=args.all,
            http_port=args.http_port,
            gevent_port=args.gevent_port,
            install_modules=install_modules,
            coverage_file=coverage_file,
        )
    )


if __name__ == "__main__":
    main()
