# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Tests for config_loader.py: version detection, base-branch auto-detection
(including the version-branch convention this suite actually uses), and
SoltConfig defaults."""

import subprocess
from unittest import mock

import pytest

from solt_pre_commit.config_loader import (
    ChangedFilesDetector,
    OdooVersionDetector,
    SoltConfig,
)


class TestNormalizeVersion:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("17.0", "17.0"),
            ("17", "17.0"),
            ("v19.0", "19.0"),
            ("V18.0", "18.0"),
            (" 17.0 ", "17.0"),
        ],
    )
    def test_normal_strings(self, raw, expected):
        assert OdooVersionDetector.normalize_version(raw) == expected

    def test_bare_float_from_unquoted_yaml(self):
        # odoo_version: 17.0 in YAML without quotes parses as a Python float,
        # not a string - this used to crash on .lower(). (CHANGELOG 1.1.0 fix)
        assert OdooVersionDetector.normalize_version(17.0) == "17.0"

    def test_future_version_accepted(self):
        assert OdooVersionDetector.normalize_version("22.0") == "22.0"

    def test_unsupported_below_minimum_falls_back_to_default(self):
        assert OdooVersionDetector.normalize_version("9.0") == "17.0"

    def test_garbage_falls_back_to_default(self):
        assert OdooVersionDetector.normalize_version("not-a-version") == "17.0"


class TestFeatureDeprecation:
    def test_deprecated_in_declared_version(self):
        assert OdooVersionDetector.is_feature_deprecated("active_id_context", "17.0") is True

    def test_not_deprecated_before_declared_version(self):
        assert OdooVersionDetector.is_feature_deprecated("active_id_context", "16.0") is False

    def test_unknown_feature_is_never_deprecated(self):
        assert OdooVersionDetector.is_feature_deprecated("not_a_real_feature", "19.0") is False


class TestPythonVersion:
    @pytest.mark.parametrize(
        "odoo_version,expected",
        [("17.0", "3.10"), ("18.0", "3.10"), ("19.0", "3.12"), ("99.0", "3.12")],
    )
    def test_known_and_default_mappings(self, odoo_version, expected):
        assert OdooVersionDetector.get_python_version(odoo_version) == expected


class TestDetectVersionFromManifest:
    def test_detects_from_manifest_in_current_dir(self, tmp_path):
        manifest = tmp_path / "__manifest__.py"
        manifest.write_text("{'name': 'x', 'version': '17.0.1.0.0'}")
        detector = OdooVersionDetector(tmp_path)
        assert detector.detect_version() == "17.0"

    def test_detects_from_manifest_in_subdirectory(self, tmp_path):
        module_dir = tmp_path / "my_module"
        module_dir.mkdir()
        (module_dir / "__manifest__.py").write_text("{'name': 'x', 'version': '19.0.1.0.0'}")
        detector = OdooVersionDetector(tmp_path)
        assert detector.detect_version() == "19.0"

    def test_falls_back_to_default_when_no_manifest(self, tmp_path):
        detector = OdooVersionDetector(tmp_path)
        assert detector.detect_version() == "17.0"

    def test_caches_detected_version(self, tmp_path):
        manifest = tmp_path / "__manifest__.py"
        manifest.write_text("{'name': 'x', 'version': '18.0.1.0.0'}")
        detector = OdooVersionDetector(tmp_path)
        assert detector.detect_version() == "18.0"
        manifest.unlink()
        # Still cached, doesn't re-scan the (now-empty) directory.
        assert detector.detect_version() == "18.0"


class TestVersionBranchFromCurrentBranch:
    def _run(self, current_branch, verify_side_effect):
        def fake_run(cmd, **kwargs):
            if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
                return mock.Mock(stdout=current_branch, returncode=0)
            if cmd[:3] == ["git", "rev-parse", "--verify"]:
                if verify_side_effect:
                    raise verify_side_effect
                return mock.Mock(returncode=0)
            raise AssertionError(f"unexpected command: {cmd}")

        with mock.patch("subprocess.run", side_effect=fake_run):
            return ChangedFilesDetector._version_branch_from_current_branch()

    def test_version_embedded_and_branch_exists(self):
        assert self._run("feature/17.0-add-invoice\n", None) == "origin/17.0"

    def test_version_embedded_but_remote_branch_missing(self):
        assert self._run("feature/17.0-add-invoice\n", subprocess.CalledProcessError(1, "git")) is None

    def test_no_version_in_branch_name(self):
        assert self._run("my-random-branch\n", None) is None

    def test_git_command_unavailable(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            assert ChangedFilesDetector._version_branch_from_current_branch() is None


class TestDetectBaseBranch:
    def test_solt_base_branch_env_wins_first(self, monkeypatch):
        monkeypatch.setenv("SOLT_BASE_BRANCH", "17.0")
        monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
        detector = ChangedFilesDetector.__new__(ChangedFilesDetector)
        assert detector._detect_base_branch() == "origin/17.0"

    def test_solt_base_branch_env_already_prefixed(self, monkeypatch):
        monkeypatch.setenv("SOLT_BASE_BRANCH", "origin/19.0")
        monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
        detector = ChangedFilesDetector.__new__(ChangedFilesDetector)
        assert detector._detect_base_branch() == "origin/19.0"

    def test_github_base_ref_used_when_no_solt_override(self, monkeypatch):
        monkeypatch.delenv("SOLT_BASE_BRANCH", raising=False)
        monkeypatch.setenv("GITHUB_BASE_REF", "19.0")
        detector = ChangedFilesDetector.__new__(ChangedFilesDetector)
        assert detector._detect_base_branch() == "origin/19.0"

    def test_version_branch_in_current_branch_name_wins_over_main_fallback(self, monkeypatch):
        monkeypatch.delenv("SOLT_BASE_BRANCH", raising=False)
        monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
        detector = ChangedFilesDetector.__new__(ChangedFilesDetector)
        with mock.patch.object(
            ChangedFilesDetector, "_version_branch_from_current_branch", return_value="origin/17.0"
        ):
            assert detector._detect_base_branch() == "origin/17.0"

    def test_falls_back_to_main_master_develop(self, monkeypatch):
        monkeypatch.delenv("SOLT_BASE_BRANCH", raising=False)
        monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
        detector = ChangedFilesDetector.__new__(ChangedFilesDetector)
        with mock.patch.object(ChangedFilesDetector, "_version_branch_from_current_branch", return_value=None):

            def fake_run(cmd, **kwargs):
                if cmd[-1] == "origin/main":
                    return mock.Mock(returncode=0)
                raise subprocess.CalledProcessError(1, cmd)

            with mock.patch("subprocess.run", side_effect=fake_run):
                assert detector._detect_base_branch() == "origin/main"

    def test_ultimate_fallback_is_head_tilde_1(self, monkeypatch):
        monkeypatch.delenv("SOLT_BASE_BRANCH", raising=False)
        monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
        detector = ChangedFilesDetector.__new__(ChangedFilesDetector)
        with mock.patch.object(ChangedFilesDetector, "_version_branch_from_current_branch", return_value=None):
            with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
                assert detector._detect_base_branch() == "HEAD~1"


class TestSoltConfigDefaults:
    def test_defaults_with_no_config_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = SoltConfig()
        assert config.validation_scope == "changed"
        assert config.test_odoo_bin == "odoo/odoo-bin"
        assert config.test_odoo_conf is None
        assert config.test_require_open_pr is True
        assert config.test_harness_script is None
        assert config.disabled_checks == set()

    def test_test_require_open_pr_overridable_to_false(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".solt-hooks.yaml").write_text("test_require_open_pr: false\n")
        config = SoltConfig()
        assert config.test_require_open_pr is False

    def test_db_settings_fall_back_to_env_vars(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DB_HOST", "postgres")
        monkeypatch.setenv("DB_PORT", "5433")
        config = SoltConfig()
        assert config.test_db_host == "postgres"
        assert config.test_db_port == "5433"

    def test_explicit_config_value_wins_over_env_var(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DB_HOST", "postgres")
        (tmp_path / ".solt-hooks.yaml").write_text("test_db_host: localhost\n")
        config = SoltConfig()
        assert config.test_db_host == "localhost"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
