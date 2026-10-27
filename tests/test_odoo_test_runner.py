# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Tests for odoo_test_runner.py: env-root resolution, the missing-environment
skip path, self-healing dropdb, the coverage/FileNotFoundError guard, and
cancellation actually killing the Odoo child process."""

import argparse
import os
import signal
import subprocess
from unittest import mock

import pytest

from solt_pre_commit import odoo_test_runner as otr
from solt_pre_commit.config_loader import SoltConfig


@pytest.fixture
def config():
    return SoltConfig.__new__(SoltConfig)  # bypass file loading, set attrs below


@pytest.fixture
def real_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return SoltConfig()


class TestFindEnvRoot:
    def test_uses_superproject_when_a_submodule(self, tmp_path):
        with mock.patch(
            "subprocess.run",
            return_value=mock.Mock(stdout=str(tmp_path) + "\n", returncode=0),
        ):
            assert otr.find_env_root() == tmp_path

    def test_falls_back_to_toplevel_when_not_a_submodule(self, tmp_path):
        calls = {"n": 0}

        def fake_run(cmd, **kwargs):
            calls["n"] += 1
            if "--show-superproject-working-tree" in cmd:
                return mock.Mock(stdout="\n")  # empty: not a submodule
            return mock.Mock(stdout=str(tmp_path) + "\n")

        with mock.patch("subprocess.run", side_effect=fake_run):
            assert otr.find_env_root() == tmp_path

    def test_falls_back_to_cwd_when_git_unavailable(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            assert otr.find_env_root() == tmp_path


class TestResolveOdooConf:
    def test_explicit_override_wins(self, tmp_path, real_config):
        real_config.test_odoo_conf = "custom/odoo.conf"
        assert otr._resolve_odoo_conf(real_config, tmp_path) == tmp_path / "custom/odoo.conf"

    def test_derived_from_odoo_version(self, tmp_path, real_config):
        real_config.set_odoo_version("19.0")
        assert otr._resolve_odoo_conf(real_config, tmp_path) == tmp_path / ".devcontainer/dev_19/odoo.conf"


class TestRunSkipsWhenEnvironmentMissing:
    def test_missing_odoo_bin_skips_not_fails(self, tmp_path, real_config, capsys):
        rc = otr.run(["fake_module"], real_config, env_root=tmp_path)
        assert rc == 0
        captured = capsys.readouterr()
        assert "SKIPPED" in captured.err
        assert "no Odoo environment" in captured.err

    def test_missing_odoo_conf_skips_not_fails(self, tmp_path, real_config, capsys):
        (tmp_path / "odoo").mkdir()
        (tmp_path / "odoo" / "odoo-bin").touch()
        rc = otr.run(["fake_module"], real_config, env_root=tmp_path)
        assert rc == 0
        assert "SKIPPED" in capsys.readouterr().err


@pytest.fixture
def fake_env(tmp_path, real_config):
    """A tmp_path with odoo-bin/odoo.conf present, so run() proceeds past the
    environment-presence check into the actual subprocess calls (which the
    individual tests below mock)."""
    (tmp_path / "odoo").mkdir()
    (tmp_path / "odoo" / "odoo-bin").touch()
    (tmp_path / ".devcontainer" / "dev_17").mkdir(parents=True)
    (tmp_path / ".devcontainer" / "dev_17" / "odoo.conf").touch()
    return tmp_path, real_config


class TestRunDbLifecycle:
    def test_dropdb_called_before_and_after_createdb(self, fake_env):
        tmp_path, config = fake_env
        run_calls = []

        def fake_run(cmd, **kwargs):
            run_calls.append(cmd[0])
            return mock.Mock(returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run), mock.patch(
            "subprocess.Popen"
        ) as popen_mock:
            proc = mock.Mock()
            proc.stdout = iter(["0 failed, 0 error(s) of 3 tests\n"])
            proc.wait.return_value = 0
            popen_mock.return_value = proc

            rc = otr.run(["fake_module"], config, env_root=tmp_path)

        assert rc == 0
        # dropdb (self-heal) -> createdb -> dropdb (cleanup) - coverage
        # report/xml/html calls also go through subprocess.run and are of no
        # interest here, just confirm the db lifecycle ordering around them.
        dropdb_indexes = [i for i, c in enumerate(run_calls) if c == "dropdb"]
        createdb_indexes = [i for i, c in enumerate(run_calls) if c == "createdb"]
        assert len(dropdb_indexes) == 2
        assert len(createdb_indexes) == 1
        assert dropdb_indexes[0] < createdb_indexes[0] < dropdb_indexes[1]

    def test_createdb_failure_returns_its_code_without_running_tests(self, fake_env):
        tmp_path, config = fake_env

        def fake_run(cmd, **kwargs):
            if cmd[0] == "createdb":
                return mock.Mock(returncode=17)
            return mock.Mock(returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run), mock.patch(
            "subprocess.Popen"
        ) as popen_mock:
            rc = otr.run(["fake_module"], config, env_root=tmp_path)

        assert rc == 17
        popen_mock.assert_not_called()

    def test_dropdb_still_runs_when_tests_raise(self, fake_env):
        tmp_path, config = fake_env
        dropdb_calls = []

        def fake_run(cmd, **kwargs):
            if cmd[0] == "dropdb":
                dropdb_calls.append(1)
            return mock.Mock(returncode=0)

        with mock.patch("subprocess.run", side_effect=fake_run), mock.patch(
            "subprocess.Popen", side_effect=RuntimeError("boom")
        ):
            with pytest.raises(RuntimeError):
                otr.run(["fake_module"], config, env_root=tmp_path)

        # Pre-emptive self-heal dropdb + the finally-block cleanup dropdb.
        assert len(dropdb_calls) == 2

    def test_no_db_password_in_odoo_bin_argv(self, fake_env):
        """PGPASSWORD (env) is how odoo-bin gets the password now, not a CLI
        arg - a CLI arg would be visible to any user on the box via `ps aux`."""
        tmp_path, config = fake_env
        captured = {}

        def fake_popen(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["env"] = kwargs.get("env")
            proc = mock.Mock()
            proc.stdout = iter([])
            proc.wait.return_value = 0
            return proc

        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)), mock.patch(
            "subprocess.Popen", side_effect=fake_popen
        ):
            otr.run(["fake_module"], config, env_root=tmp_path)

        assert not any(arg.startswith("--db_password") for arg in captured["cmd"])
        # Still needs to reach odoo-bin's psycopg2/libpq connection somehow.
        assert captured["env"]["PGPASSWORD"] == config.test_db_password

    def test_module_loading_logger_is_reopened_to_info_for_per_module_timing(self, fake_env):
        """--log-handler=:WARNING silences the general INFO firehose, but
        odoo.modules.loading specifically must be re-opened to INFO -
        otherwise "Loading module X (n/N)" never appears in a run's log at
        all, and per-module timing (the gap between two consecutive such
        lines' CI timestamps) is unrecoverable after the fact."""
        tmp_path, config = fake_env
        captured = {}

        def fake_popen(cmd, **kwargs):
            captured["cmd"] = cmd
            proc = mock.Mock()
            proc.stdout = iter([])
            proc.wait.return_value = 0
            return proc

        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)), mock.patch(
            "subprocess.Popen", side_effect=fake_popen
        ):
            otr.run(["fake_module"], config, env_root=tmp_path)

        assert "--log-handler=:WARNING" in captured["cmd"]
        assert "--log-handler=odoo.modules.loading:INFO" in captured["cmd"]


class TestScratchDbWithoutAutovacuum:
    """Autovacuum must never touch the scratch DB's tables. A test runs in one
    transaction that is rolled back; when autovacuum reaches a table while an
    open test transaction holds its only rows, it records pages but zero rows,
    the planner then believes the table empty, and a join over it runs nested
    loops that take seconds per query for the rest of the run."""

    def _run_recording_calls(self, tmp_path, config, psql_outcome=0):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(("run", cmd))
            if cmd[0] != "psql":
                return mock.Mock(returncode=0)
            if isinstance(psql_outcome, BaseException):
                raise psql_outcome
            return mock.Mock(returncode=psql_outcome, stderr="ERROR:  permission denied to create event trigger")

        def fake_popen(cmd, **kwargs):
            calls.append(("popen", cmd))
            proc = mock.Mock()
            proc.stdout = iter(["0 failed, 0 error(s) of 3 tests\n"])
            proc.wait.return_value = 0
            return proc

        with mock.patch("subprocess.run", side_effect=fake_run), mock.patch(
            "subprocess.Popen", side_effect=fake_popen
        ):
            returncode = otr.run(["fake_module"], config, env_root=tmp_path)
        return returncode, calls

    def test_autovacuum_is_switched_off_in_the_scratch_db_before_odoo_creates_its_tables(self, fake_env):
        tmp_path, config = fake_env
        returncode, calls = self._run_recording_calls(tmp_path, config)

        assert returncode == 0
        commands = [cmd[0] if kind == "run" else "odoo-bin" for kind, cmd in calls]
        createdb_cmd = next(cmd for kind, cmd in calls if kind == "run" and cmd[0] == "createdb")
        scratch_db = createdb_cmd[-1]
        psql_cmds = [cmd for kind, cmd in calls if kind == "run" and cmd[0] == "psql"]
        assert len(psql_cmds) == 1
        psql_cmd = psql_cmds[0]
        assert psql_cmd[psql_cmd.index("-d") + 1] == scratch_db
        assert "ON_ERROR_STOP=1" in psql_cmd
        sql = psql_cmd[psql_cmd.index("-c") + 1]
        assert "CREATE EVENT TRIGGER" in sql
        assert "autovacuum_enabled = false" in sql
        assert commands.index("createdb") < commands.index("psql") < commands.index("odoo-bin")

    @pytest.mark.parametrize("psql_outcome", [1, FileNotFoundError()], ids=["not-a-superuser", "no-psql"])
    def test_tests_still_run_when_autovacuum_cannot_be_switched_off(self, fake_env, capsys, psql_outcome):
        tmp_path, config = fake_env
        returncode, calls = self._run_recording_calls(tmp_path, config, psql_outcome=psql_outcome)

        assert returncode == 0
        assert any(kind == "popen" for kind, cmd in calls)
        assert "autovacuum" in capsys.readouterr().err


class TestAddonsPathOverride:
    def _run_capturing_popen(self, tmp_path, config, **run_kwargs):
        captured = {}

        def fake_popen(cmd, **kwargs):
            captured["cmd"] = cmd
            proc = mock.Mock()
            proc.stdout = iter([])
            proc.wait.return_value = 0
            return proc

        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)), mock.patch(
            "subprocess.Popen", side_effect=fake_popen
        ):
            otr.run(["fake_module"], config, env_root=tmp_path, **run_kwargs)

        return captured["cmd"]

    def test_without_demo_is_spelled_as_a_boolean(self, fake_env):
        """`all` was the pre-19.0 spelling. Odoo 19 warns "invalid boolean
        value: 'all', assume True" on every run - it still does the right
        thing, so the only symptom is a warning nobody reads until the
        spelling stops being accepted."""
        tmp_path, config = fake_env
        cmd = self._run_capturing_popen(tmp_path, config)

        assert "--without-demo=True" in cmd
        assert "--without-demo=all" not in cmd


    def test_appends_the_flag_when_provided(self, fake_env):
        tmp_path, config = fake_env
        cmd = self._run_capturing_popen(tmp_path, config, addons_path="/custom/addons")
        assert "--addons-path=/custom/addons" in cmd

    def test_omitting_it_adds_no_flag_at_all(self, fake_env):
        # Regression guard: CI-facing callers pass addons_path, but existing
        # local/pre-push callers don't - they must see byte-for-byte the same
        # command as before this override existed.
        tmp_path, config = fake_env
        cmd = self._run_capturing_popen(tmp_path, config)
        assert not any(arg.startswith("--addons-path") for arg in cmd)

    def test_explicit_none_is_the_same_as_omitting_it(self, fake_env):
        tmp_path, config = fake_env
        cmd = self._run_capturing_popen(tmp_path, config, addons_path=None)
        assert not any(arg.startswith("--addons-path") for arg in cmd)


class TestMainCliAddonsPath:
    def test_addons_path_flag_reaches_run(self, monkeypatch):
        captured = {}

        def fake_run(modules, config, **kwargs):
            captured["addons_path"] = kwargs.get("addons_path")
            return 0

        monkeypatch.setattr(otr, "run", fake_run)
        monkeypatch.setattr(
            "sys.argv", ["solt-test-module", "--addons-path", "/ci/addons", "fake_module"]
        )
        with pytest.raises(SystemExit) as exc_info:
            otr.main()

        assert exc_info.value.code == 0
        assert captured["addons_path"] == "/ci/addons"

    def test_omitting_the_flag_passes_none(self, monkeypatch):
        captured = {}

        def fake_run(modules, config, **kwargs):
            captured["addons_path"] = kwargs.get("addons_path")
            return 0

        monkeypatch.setattr(otr, "run", fake_run)
        monkeypatch.setattr("sys.argv", ["solt-test-module", "fake_module"])
        with pytest.raises(SystemExit):
            otr.main()

        assert captured["addons_path"] is None


class TestRunCoverageMissing:
    def test_missing_coverage_binary_returns_1_not_traceback(self, fake_env):
        tmp_path, config = fake_env
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)), mock.patch(
            "subprocess.Popen", side_effect=FileNotFoundError
        ):
            rc = otr.run(["fake_module"], config, env_root=tmp_path)
        assert rc == 1


class TestReportCoverage:
    def test_missing_coverage_binary_does_not_raise(self, tmp_path, capsys):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            otr._report_coverage(["fake_module"], tmp_path)  # must not raise
        assert "not on PATH" in capsys.readouterr().err


class TestTerminate:
    """_terminate() is the actual fix: a cancelled job's SIGTERM used to kill
    only the Python wrapper, orphaning the still-running odoo-bin child
    forever (see the real incident this closes - a job stayed "in progress"
    for 90+ minutes after being cancelled from the GitHub UI, repeatedly)."""

    def test_already_exited_process_is_left_alone(self):
        proc = mock.Mock()
        proc.poll.return_value = 0  # already exited
        otr._terminate(proc)
        proc.terminate.assert_not_called()

    def test_running_process_is_terminated(self):
        proc = mock.Mock()
        proc.poll.return_value = None
        proc.wait.return_value = 0
        otr._terminate(proc)
        proc.terminate.assert_called_once()
        proc.kill.assert_not_called()

    def test_escalates_to_kill_when_terminate_does_not_stop_it_in_time(self):
        proc = mock.Mock()
        proc.poll.return_value = None
        # First wait() (post-terminate) times out; second (post-kill) succeeds.
        proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="odoo-bin", timeout=10), 0]
        otr._terminate(proc)
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()


class TestCancellation:
    """run() must actually stop the Odoo child on cancellation, not just let
    the wrapper die and orphan it - reproduces the exact failure mode found
    live: TestPostMerge's 'Run tests with coverage' step stayed in_progress
    for 90+ minutes after being cancelled from the GitHub UI, repeatedly,
    because nothing ever told the odoo-bin child to stop."""

    def test_sigterm_during_test_run_kills_child_and_still_drops_db(self, fake_env):
        tmp_path, config = fake_env
        dropdb_calls = []

        def fake_run(cmd, **kwargs):
            if cmd[0] == "dropdb":
                dropdb_calls.append(1)
            return mock.Mock(returncode=0)

        proc = mock.Mock()
        proc.poll.return_value = None  # still running when _terminate() checks
        proc.wait.return_value = 0

        def fake_stdout():
            # Simulates the SIGTERM handler firing mid-read, exactly like a
            # real signal arriving while blocked on the pipe.
            raise otr._CancelledError()
            yield  # pragma: no cover - unreachable, makes this a generator

        proc.stdout = fake_stdout()

        with mock.patch("subprocess.run", side_effect=fake_run), mock.patch(
            "subprocess.Popen", return_value=proc
        ):
            rc = otr.run(["fake_module"], config, env_root=tmp_path)

        assert rc == 143  # conventional 128+SIGTERM, not an unhandled traceback
        proc.terminate.assert_called_once()
        assert len(dropdb_calls) == 2  # pre-emptive self-heal + the finally-block cleanup

    def test_sigterm_handler_is_installed_and_restored(self, fake_env):
        tmp_path, config = fake_env
        original = signal.getsignal(signal.SIGTERM)

        proc = mock.Mock()
        proc.poll.return_value = None
        proc.wait.return_value = 0
        proc.stdout = iter(["0 failed, 0 error(s) of 1 tests\n"])

        installed_handler = {}

        real_signal = signal.signal

        def spy_signal(signum, handler):
            if signum == signal.SIGTERM and handler is not original:
                installed_handler["handler"] = handler
            return real_signal(signum, handler)

        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)), mock.patch(
            "subprocess.Popen", return_value=proc
        ), mock.patch("signal.signal", side_effect=spy_signal):
            otr.run(["fake_module"], config, env_root=tmp_path)

        assert installed_handler.get("handler") is otr._handle_sigterm
        # Restored afterwards - a long-lived caller (e.g. a test suite runner
        # invoking run() more than once) must not keep a stale handler installed.
        assert signal.getsignal(signal.SIGTERM) == original


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def _module(root, name, manifest="{'name': 'x'}"):
    (root / name).mkdir(parents=True)
    (root / name / "__manifest__.py").write_text(manifest)


class TestEligibleModules:
    def test_skips_installable_false(self, tmp_path, real_config):
        _module(tmp_path, "good")
        _module(tmp_path, "explicit_true", "{'name': 'x', 'installable': True}")
        _module(tmp_path, "disabled", "{'name': 'x', 'installable': False}")
        assert otr.eligible_modules(tmp_path, real_config) == ["explicit_true", "good"]

    def test_unparseable_manifest_still_counts_as_installable(self, tmp_path, real_config):
        _module(tmp_path, "broken", "this is not python {")
        assert otr.eligible_modules(tmp_path, real_config) == ["broken"]

    def test_applies_exclude_modules(self, tmp_path, real_config):
        _module(tmp_path, "keep")
        _module(tmp_path, "skip_me")
        real_config.exclude_modules = ["skip_me"]
        assert otr.eligible_modules(tmp_path, real_config) == ["keep"]


class TestStrictMissingEnvironment:
    def test_strict_fails_instead_of_skipping(self, tmp_path, real_config, capsys):
        rc = otr.run(["fake_module"], real_config, env_root=tmp_path, strict=True)
        assert rc == 1
        assert "FAIL" in capsys.readouterr().err


class TestMainCliAll:
    def _run_main(self, monkeypatch, tmp_path, argv, real_config):
        captured = {}

        def fake_run(modules, config, **kwargs):
            captured.update(modules=modules, strict=kwargs.get("strict"))
            return 0

        monkeypatch.setattr(otr, "run", fake_run)
        monkeypatch.setattr(otr, "SoltConfig", lambda *_a, **_k: real_config)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.argv", ["solt-test-module", *argv])
        return captured

    def test_all_runs_every_eligible_module_strictly(self, monkeypatch, tmp_path, real_config):
        _module(tmp_path, "a")
        _module(tmp_path, "b", "{'installable': False}")
        real_config.exclude_modules = []
        captured = self._run_main(monkeypatch, tmp_path, ["--all"], real_config)
        with pytest.raises(SystemExit) as exc_info:
            otr.main()
        assert exc_info.value.code == 0
        assert captured == {"modules": ["a"], "strict": True}

    def test_all_prints_excluded_modules(self, monkeypatch, tmp_path, real_config, capsys):
        _module(tmp_path, "a")
        _module(tmp_path, "skipped")
        real_config.exclude_modules = ["skipped"]
        self._run_main(monkeypatch, tmp_path, ["--all"], real_config)
        with pytest.raises(SystemExit):
            otr.main()
        assert "EXCLUDED (not tested): skipped" in capsys.readouterr().out

    def test_all_with_module_list_is_an_error(self, monkeypatch, tmp_path, real_config):
        self._run_main(monkeypatch, tmp_path, ["--all", "a"], real_config)
        with pytest.raises(SystemExit) as exc_info:
            otr.main()
        assert exc_info.value.code == 2

    def test_neither_all_nor_modules_is_an_error(self, monkeypatch, tmp_path, real_config):
        self._run_main(monkeypatch, tmp_path, [], real_config)
        with pytest.raises(SystemExit) as exc_info:
            otr.main()
        assert exc_info.value.code == 2

    def test_explicit_list_is_not_strict(self, monkeypatch, tmp_path, real_config):
        captured = self._run_main(monkeypatch, tmp_path, ["a,b"], real_config)
        with pytest.raises(SystemExit):
            otr.main()
        assert captured == {"modules": ["a", "b"], "strict": False}


class TestIdleWatchdog:
    """A run that goes silent is stopped and fails (124); one that keeps logging is not."""

    def _watch(self, script, idle_seconds, wait):
        import sys
        import threading
        import time

        proc = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True)
        last, fired, done = [time.monotonic()], threading.Event(), threading.Event()
        t = threading.Thread(target=otr._idle_watchdog, args=(proc, last, idle_seconds, fired, done, 0.1), daemon=True)
        t.start()
        try:
            proc.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            pass
        done.set()
        stopped = proc.poll() is not None
        if not stopped:
            proc.kill()
            proc.wait()
        return fired.is_set(), stopped

    def test_silent_process_is_stopped(self):
        fired, stopped = self._watch("import time; time.sleep(60)", idle_seconds=0.5, wait=15)
        assert fired and stopped

    def test_process_that_finishes_is_left_alone(self):
        fired, stopped = self._watch("print('done')", idle_seconds=5, wait=15)
        assert stopped and not fired

    def test_run_returns_124_and_reports_hung(self, fake_env, capsys):
        import threading

        tmp_path, config = fake_env
        config.test_idle_timeout_minutes = 0.01  # 0.6s; bypasses the >=1 clamp on purpose

        class HungProc:
            def __init__(self):
                self._dead = threading.Event()
                self.stdout = self._lines()

            def _lines(self):
                yield "starting\n"
                self._dead.wait(30)  # silent until the watchdog terminates us

            def poll(self):
                return 0 if self._dead.is_set() else None

            def terminate(self):
                self._dead.set()

            def kill(self):
                self._dead.set()

            def wait(self, timeout=None):
                self._dead.wait(timeout)
                return -15

        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)), mock.patch(
            "subprocess.Popen", return_value=HungProc()
        ):
            rc = otr.run(["fake_module"], config, env_root=tmp_path)

        assert rc == otr.EXIT_IDLE_TIMEOUT == 124
        captured = capsys.readouterr()
        assert "hung" in captured.err.lower() or "hung" in captured.out.lower()
        assert "FAIL" in captured.out


class TestIdleTimeoutConfig:
    @pytest.mark.parametrize(
        "raw,expected",
        [(None, 30), (45, 45), ("20", 20), (0, 30), (-5, 30), ("abc", 30), (1, 1)],
    )
    def test_as_positive_int(self, raw, expected):
        assert SoltConfig._as_positive_int(raw, 30) == expected

    def test_default_is_30_minutes(self, real_config):
        assert real_config.test_idle_timeout_minutes == 30


class TestPortOptions:
    """``--http-port`` / ``--gevent-port``: two runs at once need their own ports; the config's are the default."""

    @pytest.fixture
    def ported(self, real_config):
        real_config.test_http_port = "18069"
        real_config.test_gevent_port = "18072"
        return real_config

    def test_the_config_ports_are_the_default(self, ported):
        assert otr.resolve_ports(ported, None, None) == ("18069", "18072")

    def test_an_http_port_alone_keeps_the_configured_gap_to_the_gevent_port(self, ported):
        assert otr.resolve_ports(ported, 18269, None) == ("18269", "18272")

    def test_both_ports_given_are_used_as_they_are(self, ported):
        assert otr.resolve_ports(ported, 18269, 18999) == ("18269", "18999")

    def test_a_gevent_port_alone_leaves_the_http_port_to_the_config(self, ported):
        assert otr.resolve_ports(ported, None, 18999) == ("18069", "18999")

    def test_run_gives_odoo_the_ports_it_was_asked_for(self, fake_env):
        tmp_path, config = fake_env
        config.test_http_port, config.test_gevent_port = "18069", "18072"
        launched = []

        def fake_popen(cmd, **kwargs):
            launched.append(cmd)
            proc = mock.Mock()
            proc.stdout = iter(["0 failed, 0 error(s) of 3 tests\n"])
            proc.wait.return_value = 0
            return proc

        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)), mock.patch(
            "subprocess.Popen", side_effect=fake_popen
        ):
            otr.run(["fake_module"], config, env_root=tmp_path, http_port=18369)

        assert "--http-port=18369" in launched[0]
        assert "--gevent-port=18372" in launched[0]

    def test_run_without_the_options_still_uses_the_config_ports(self, fake_env):
        tmp_path, config = fake_env
        config.test_http_port, config.test_gevent_port = "18069", "18072"
        launched = []

        def fake_popen(cmd, **kwargs):
            launched.append(cmd)
            proc = mock.Mock()
            proc.stdout = iter(["0 failed, 0 error(s) of 3 tests\n"])
            proc.wait.return_value = 0
            return proc

        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)), mock.patch(
            "subprocess.Popen", side_effect=fake_popen
        ):
            otr.run(["fake_module"], config, env_root=tmp_path)

        assert "--http-port=18069" in launched[0]
        assert "--gevent-port=18072" in launched[0]

    @pytest.mark.parametrize("bad", ["0", "70000", "-1", "abc", ""])
    def test_a_port_that_is_not_a_port_is_a_usage_error(self, bad, monkeypatch, tmp_path, real_config, capsys):
        monkeypatch.setattr(otr, "SoltConfig", lambda *_a, **_k: real_config)
        monkeypatch.setattr("sys.argv", ["solt-test-module", "a", "--http-port", bad])
        with pytest.raises(SystemExit) as exc_info:
            otr.main()
        assert exc_info.value.code == 2

    def test_main_hands_the_ports_to_run(self, monkeypatch, tmp_path, real_config):
        seen = {}

        def fake_run(modules, config, **kwargs):
            seen.update(kwargs)
            return 0

        monkeypatch.setattr(otr, "run", fake_run)
        monkeypatch.setattr(otr, "SoltConfig", lambda *_a, **_k: real_config)
        monkeypatch.setattr("sys.argv", ["solt-test-module", "a", "--http-port", "18269", "--gevent-port", "18999"])
        with pytest.raises(SystemExit):
            otr.main()
        assert (seen["http_port"], seen["gevent_port"]) == (18269, 18999)


class TestTestCountIsLogged:
    def test_the_result_logger_is_reopened_to_info_so_a_passing_run_reports_how_many_tests_ran(self, fake_env):
        tmp_path, config = fake_env
        captured = {}

        def fake_popen(cmd, **kwargs):
            captured["cmd"] = cmd
            proc = mock.Mock()
            proc.stdout = iter([])
            proc.wait.return_value = 0
            return proc

        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)), mock.patch(
            "subprocess.Popen", side_effect=fake_popen
        ):
            otr.run(["fake_module"], config, env_root=tmp_path)

        assert "--log-handler=odoo.tests.result:INFO" in captured["cmd"]


class TestShardModules:
    NAMES = [f"mod_{i:02d}" for i in range(23)]

    @pytest.mark.parametrize("count", [1, 2, 3, 4, 7, 23])
    def test_the_shards_partition_the_modules(self, count):
        shares = [otr.shard_modules(self.NAMES, index, count) for index in range(count)]
        flat = [name for share in shares for name in share]
        assert sorted(flat) == sorted(self.NAMES), "every module is tested"
        assert len(flat) == len(set(flat)), "no module is tested twice"

    def test_the_split_does_not_depend_on_the_order_the_modules_come_in(self):
        assert otr.shard_modules(list(reversed(self.NAMES)), 1, 4) == otr.shard_modules(self.NAMES, 1, 4)

    def test_modules_are_dealt_in_turns_not_in_blocks(self):
        assert otr.shard_modules(["a", "b", "c", "d", "e"], 0, 2) == ["a", "c", "e"]
        assert otr.shard_modules(["a", "b", "c", "d", "e"], 1, 2) == ["b", "d"]

    @pytest.mark.parametrize("raw,expected", [("1/4", (0, 4)), ("4/4", (3, 4)), ("1/1", (0, 1))])
    def test_parse_shard(self, raw, expected):
        assert otr.parse_shard(raw) == expected

    @pytest.mark.parametrize("raw", ["0/4", "5/4", "2", "a/b", "1/0", "-1/4", "1/2/3"])
    def test_parse_shard_rejects(self, raw):
        with pytest.raises(argparse.ArgumentTypeError):
            otr.parse_shard(raw)


class TestRunShard:
    def _run(self, fake_env, **kwargs):
        tmp_path, config = fake_env
        captured = {"run": []}

        def fake_run(cmd, **kw):
            captured["run"].append(cmd)
            return mock.Mock(returncode=0)

        def fake_popen(cmd, **kw):
            captured["cmd"], captured["env"] = cmd, kw.get("env")
            proc = mock.Mock()
            proc.stdout = iter(["0 failed, 0 error(s) of 3 tests\n"])
            proc.wait.return_value = 0
            return proc

        with mock.patch("subprocess.run", side_effect=fake_run), mock.patch("subprocess.Popen", side_effect=fake_popen):
            rc = otr.run(["b", "d"], config, env_root=tmp_path, **kwargs)
        return rc, captured

    def test_every_module_is_installed_but_only_the_shards_are_tested(self, fake_env):
        rc, captured = self._run(fake_env, install_modules=["a", "b", "c", "d"])
        cmd = captured["cmd"]
        assert rc == 0
        assert cmd[cmd.index("-i") + 1] == "a,b,c,d"
        assert "--test-tags=/b,/d" in cmd

    def test_without_install_modules_the_tested_modules_are_the_installed_ones(self, fake_env):
        _rc, captured = self._run(fake_env)
        cmd = captured["cmd"]
        assert cmd[cmd.index("-i") + 1] == "b,d"

    def test_a_shard_has_its_own_coverage_data_and_leaves_the_shared_reports_alone(self, fake_env):
        _rc, captured = self._run(fake_env, install_modules=["a", "b", "c", "d"], coverage_file="/x/.coverage.shard-1-2")
        assert captured["env"]["COVERAGE_FILE"] == "/x/.coverage.shard-1-2"
        coverage_calls = [c[1] for c in captured["run"] if c and c[0] == "coverage"]
        assert coverage_calls == ["report"], "no coverage.xml / htmlcov: shards would overwrite each other's"

    def test_an_unsharded_run_still_writes_the_shared_reports(self, fake_env):
        _rc, captured = self._run(fake_env)
        coverage_calls = [c[1] for c in captured["run"] if c and c[0] == "coverage"]
        assert coverage_calls == ["report", "xml", "html"]
        assert "COVERAGE_FILE" not in (captured["env"] or {}) or captured["env"]["COVERAGE_FILE"] == os.environ.get("COVERAGE_FILE")


class TestMainShard:
    def _main(self, monkeypatch, tmp_path, argv, real_config, names):
        for name in names:
            _module(tmp_path, name)
        real_config.exclude_modules = []
        captured = {}

        def fake_run(modules, config, **kwargs):
            captured.update(modules=modules, **kwargs)
            return 0

        monkeypatch.setattr(otr, "run", fake_run)
        monkeypatch.setattr(otr, "SoltConfig", lambda *_a, **_k: real_config)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys.argv", ["solt-test-module", *argv])
        return captured

    def test_a_shard_tests_its_share_and_installs_everything(self, monkeypatch, tmp_path, real_config):
        captured = self._main(monkeypatch, tmp_path, ["--all", "--shard", "2/3"], real_config, list("abcdefg"))
        with pytest.raises(SystemExit) as exc_info:
            otr.main()
        assert exc_info.value.code == 0
        assert captured["modules"] == ["b", "e"]
        assert captured["install_modules"] == list("abcdefg")
        assert captured["coverage_file"].endswith(".coverage.shard-2-3")

    def test_the_shards_together_test_every_module_once(self, monkeypatch, tmp_path, real_config):
        names = list("abcdefghij")
        tested = []
        for position in (1, 2, 3):
            captured = self._main(monkeypatch, tmp_path, ["--all", "--shard", f"{position}/3"], real_config, [])
            for name in names:
                if not (tmp_path / name).exists():
                    _module(tmp_path, name)
            with pytest.raises(SystemExit):
                otr.main()
            tested += captured["modules"]
        assert sorted(tested) == names

    def test_shard_needs_all(self, monkeypatch, tmp_path, real_config):
        self._main(monkeypatch, tmp_path, ["a,b", "--shard", "1/2"], real_config, ["a", "b"])
        with pytest.raises(SystemExit) as exc_info:
            otr.main()
        assert exc_info.value.code == 2

    def test_more_shards_than_modules_is_an_error_not_an_empty_pass(self, monkeypatch, tmp_path, real_config):
        self._main(monkeypatch, tmp_path, ["--all", "--shard", "3/3"], real_config, ["a", "b"])
        with pytest.raises(SystemExit) as exc_info:
            otr.main()
        assert exc_info.value.code == 2

    def test_without_shard_nothing_changes(self, monkeypatch, tmp_path, real_config):
        captured = self._main(monkeypatch, tmp_path, ["--all"], real_config, ["a", "b"])
        with pytest.raises(SystemExit):
            otr.main()
        assert captured["modules"] == ["a", "b"]
        assert captured["install_modules"] is None and captured["coverage_file"] is None
