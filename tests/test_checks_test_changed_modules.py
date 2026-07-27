# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Tests for checks_test_changed_modules.py's PR-gating logic: the pre-push
hook must skip on a branch with no open PR yet, run when one exists, and
fail open (run anyway) when PR state can't be determined at all."""

from unittest import mock

import pytest

from solt_pre_commit import checks_test_changed_modules as mod


def _run_main(argv=None):
    with mock.patch("sys.argv", ["solt-test-changed-modules"] + (argv or [])):
        try:
            mod.main()
        except SystemExit as e:
            return e.code
    return None


class TestPrGate:
    def test_no_open_pr_skips_before_touching_changed_files(self, capsys):
        with mock.patch("solt_pre_commit.github_pr.has_open_pull_request", return_value=False), mock.patch.object(
            mod.SoltConfig, "changed_detector", new_callable=mock.PropertyMock
        ) as changed_detector:
            rc = _run_main()
        assert rc == 0
        changed_detector.assert_not_called()
        assert "No open PR" in capsys.readouterr().out

    def test_undetermined_pr_state_runs_anyway(self, capsys):
        with mock.patch("solt_pre_commit.github_pr.has_open_pull_request", return_value=None), mock.patch.object(
            mod.SoltConfig, "changed_detector", new_callable=mock.PropertyMock
        ) as changed_detector:
            changed_detector.return_value.get_changed_files.return_value = set()
            rc = _run_main()
        assert rc == 0
        changed_detector.assert_called()
        assert "Could not determine PR state" in capsys.readouterr().out

    def test_open_pr_proceeds_silently(self, capsys):
        with mock.patch("solt_pre_commit.github_pr.has_open_pull_request", return_value=True), mock.patch.object(
            mod.SoltConfig, "changed_detector", new_callable=mock.PropertyMock
        ) as changed_detector:
            changed_detector.return_value.get_changed_files.return_value = set()
            rc = _run_main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "No open PR" not in out
        assert "Could not determine" not in out

    def test_gate_skipped_entirely_when_disabled_in_config(self):
        fake_config = mock.Mock(test_require_open_pr=False)
        fake_config.changed_detector.get_changed_files.return_value = set()
        with mock.patch("solt_pre_commit.github_pr.has_open_pull_request") as pr_check, mock.patch.object(
            mod, "SoltConfig", return_value=fake_config
        ):
            _run_main()
        pr_check.assert_not_called()


class TestNoChangesDetected:
    def test_no_changed_files_exits_cleanly(self, capsys):
        with mock.patch("solt_pre_commit.github_pr.has_open_pull_request", return_value=True), mock.patch.object(
            mod.SoltConfig, "changed_detector", new_callable=mock.PropertyMock
        ) as changed_detector:
            changed_detector.return_value.get_changed_files.return_value = set()
            rc = _run_main()
        assert rc == 0
        assert "No changed files detected" in capsys.readouterr().out

    def test_changed_files_with_no_odoo_modules_exits_cleanly(self, capsys):
        with mock.patch("solt_pre_commit.github_pr.has_open_pull_request", return_value=True), mock.patch.object(
            mod.SoltConfig, "changed_detector", new_callable=mock.PropertyMock
        ) as changed_detector, mock.patch(
            "solt_pre_commit.checks_test_changed_modules._detect_modules_from_paths", return_value=[]
        ):
            changed_detector.return_value.get_changed_files.return_value = {"/repo/README.md"}
            rc = _run_main()
        assert rc == 0
        assert "No Odoo modules among changed files" in capsys.readouterr().out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
