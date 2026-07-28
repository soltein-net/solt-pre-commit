# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Tests for odoo_test_runner.py: env-root resolution, the missing-environment
skip path, self-healing dropdb, and the coverage/FileNotFoundError guard."""

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
