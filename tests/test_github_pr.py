# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Tests for github_pr.py - the pre-push PR-existence gate."""

import json
import subprocess
from unittest import mock

import pytest

from solt_pre_commit import github_pr


class TestOwnerRepoFromRemote:
    def _run(self, remote_get_url_stdout):
        with mock.patch(
            "subprocess.run",
            return_value=mock.Mock(stdout=remote_get_url_stdout, returncode=0),
        ):
            return github_pr._owner_repo_from_remote()

    def test_ssh_remote(self):
        assert self._run("git@github.com:soltein-net/solt-pre-commit.git\n") == (
            "soltein-net",
            "solt-pre-commit",
        )

    def test_https_remote(self):
        assert self._run("https://github.com/soltein-net/solt-pre-commit.git\n") == (
            "soltein-net",
            "solt-pre-commit",
        )

    def test_https_remote_no_dot_git_suffix(self):
        assert self._run("https://github.com/soltein-net/solt-pre-commit\n") == (
            "soltein-net",
            "solt-pre-commit",
        )

    def test_non_github_remote_returns_none(self):
        assert self._run("https://gitlab.com/soltein-net/solt-pre-commit.git\n") is None

    def test_git_command_failure_returns_none(self):
        with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
            assert github_pr._owner_repo_from_remote() is None

    def test_git_not_installed_returns_none(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            assert github_pr._owner_repo_from_remote() is None


class TestCurrentBranch:
    def test_returns_branch_name(self):
        with mock.patch("subprocess.run", return_value=mock.Mock(stdout="imp/17.0-agent-skills\n")):
            assert github_pr._current_branch() == "imp/17.0-agent-skills"

    def test_empty_output_returns_none(self):
        with mock.patch("subprocess.run", return_value=mock.Mock(stdout="\n")):
            assert github_pr._current_branch() is None

    def test_git_failure_returns_none(self):
        with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
            assert github_pr._current_branch() is None


class TestCheckViaGh:
    def test_gh_not_installed_returns_none(self):
        with mock.patch("shutil.which", return_value=None):
            assert github_pr._check_via_gh("o", "r", "b") is None

    def test_open_pr_found(self):
        with mock.patch("shutil.which", return_value="/usr/bin/gh"), mock.patch(
            "subprocess.run",
            return_value=mock.Mock(returncode=0, stdout=json.dumps([{"number": 9}])),
        ):
            assert github_pr._check_via_gh("o", "r", "b") is True

    def test_no_open_pr(self):
        with mock.patch("shutil.which", return_value="/usr/bin/gh"), mock.patch(
            "subprocess.run", return_value=mock.Mock(returncode=0, stdout="[]")
        ):
            assert github_pr._check_via_gh("o", "r", "b") is False

    def test_gh_not_authenticated_returns_none(self):
        with mock.patch("shutil.which", return_value="/usr/bin/gh"), mock.patch(
            "subprocess.run", return_value=mock.Mock(returncode=1, stdout="")
        ):
            assert github_pr._check_via_gh("o", "r", "b") is None

    def test_gh_bad_json_returns_none(self):
        with mock.patch("shutil.which", return_value="/usr/bin/gh"), mock.patch(
            "subprocess.run", return_value=mock.Mock(returncode=0, stdout="not json")
        ):
            assert github_pr._check_via_gh("o", "r", "b") is None

    def test_gh_timeout_returns_none(self):
        with mock.patch("shutil.which", return_value="/usr/bin/gh"), mock.patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 15)
        ):
            assert github_pr._check_via_gh("o", "r", "b") is None


class TestCheckViaRestApi:
    def test_no_token_returns_none(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        assert github_pr._check_via_rest_api("o", "r", "b") is None

    def test_open_pr_found(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        response = mock.MagicMock()
        response.status = 200
        response.read.return_value = json.dumps([{"number": 1}]).encode()
        response.__enter__.return_value = response
        with mock.patch("urllib.request.urlopen", return_value=response):
            assert github_pr._check_via_rest_api("o", "r", "b") is True

    def test_no_open_pr(self, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "fake-token")
        response = mock.MagicMock()
        response.status = 200
        response.read.return_value = b"[]"
        response.__enter__.return_value = response
        with mock.patch("urllib.request.urlopen", return_value=response):
            assert github_pr._check_via_rest_api("o", "r", "b") is False

    def test_network_error_returns_none(self, monkeypatch):
        import urllib.error

        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("no network")):
            assert github_pr._check_via_rest_api("o", "r", "b") is None


class TestHasOpenPullRequest:
    def test_no_branch_returns_none(self):
        with mock.patch.object(github_pr, "_current_branch", return_value=None):
            assert github_pr.has_open_pull_request() is None

    def test_no_github_remote_returns_none(self):
        with mock.patch.object(github_pr, "_current_branch", return_value="feature/x"), mock.patch.object(
            github_pr, "_owner_repo_from_remote", return_value=None
        ):
            assert github_pr.has_open_pull_request() is None

    def test_gh_result_used_when_available(self):
        with mock.patch.object(github_pr, "_current_branch", return_value="feature/x"), mock.patch.object(
            github_pr, "_owner_repo_from_remote", return_value=("o", "r")
        ), mock.patch.object(github_pr, "_check_via_gh", return_value=True) as gh_mock, mock.patch.object(
            github_pr, "_check_via_rest_api"
        ) as rest_mock:
            assert github_pr.has_open_pull_request() is True
            gh_mock.assert_called_once_with("o", "r", "feature/x")
            rest_mock.assert_not_called()

    def test_falls_back_to_rest_api_when_gh_undetermined(self):
        with mock.patch.object(github_pr, "_current_branch", return_value="feature/x"), mock.patch.object(
            github_pr, "_owner_repo_from_remote", return_value=("o", "r")
        ), mock.patch.object(github_pr, "_check_via_gh", return_value=None), mock.patch.object(
            github_pr, "_check_via_rest_api", return_value=False
        ) as rest_mock:
            assert github_pr.has_open_pull_request() is False
            rest_mock.assert_called_once_with("o", "r", "feature/x")

    def test_both_undetermined_returns_none(self):
        with mock.patch.object(github_pr, "_current_branch", return_value="feature/x"), mock.patch.object(
            github_pr, "_owner_repo_from_remote", return_value=("o", "r")
        ), mock.patch.object(github_pr, "_check_via_gh", return_value=None), mock.patch.object(
            github_pr, "_check_via_rest_api", return_value=None
        ):
            assert github_pr.has_open_pull_request() is None

    def test_explicit_branch_argument_skips_current_branch_lookup(self):
        with mock.patch.object(github_pr, "_current_branch") as current_branch_mock, mock.patch.object(
            github_pr, "_owner_repo_from_remote", return_value=("o", "r")
        ), mock.patch.object(github_pr, "_check_via_gh", return_value=True):
            assert github_pr.has_open_pull_request(branch="explicit-branch") is True
            current_branch_mock.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
