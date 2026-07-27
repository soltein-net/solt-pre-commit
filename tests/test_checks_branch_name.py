# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Tests for checks_branch_name.py: BranchNameValidator's protected-branch
detection, Odoo-version extraction, flexible/strict validation modes, config
loading, and the `solt-check-branch` CLI entry point.

All validators here pass config_path="/nonexistent" unless a test is
specifically exercising config loading - the default (no config_path) walks
up 5 parent directories from cwd looking for .solt-hooks.yaml, which would
pick up the real super-repo config when tests run from within a checkout."""

import subprocess
import sys
from unittest import mock

import pytest

from solt_pre_commit.checks_branch_name import BranchNameValidator, main


def _validator(**kwargs):
    kwargs.setdefault("config_path", "/nonexistent")
    return BranchNameValidator(**kwargs)


class TestConstructorDefaults:
    def test_flexible_mode_by_default(self):
        assert _validator().strict is False

    def test_default_ticket_prefix_accepts_any_uppercase(self):
        assert _validator().ticket_prefixes == ["[A-Z]+"]

    def test_default_allowed_types_include_feature_and_release(self):
        allowed = _validator().allowed_types
        assert "feature" in allowed
        assert "release" in allowed


class TestIsProtectedBranch:
    @pytest.mark.parametrize(
        "branch",
        ["main", "master", "develop", "development", "staging", "production", "HEAD"],
    )
    def test_explicit_protected_names(self, branch):
        assert _validator().is_protected_branch(branch) is True

    @pytest.mark.parametrize("branch", ["17.0", "18.0", "17.0.1.0", "17.0.1.0.0"])
    def test_odoo_version_branches_are_protected(self, branch):
        assert _validator().is_protected_branch(branch) is True

    def test_version_with_trailing_qualifier_not_protected(self):
        # DEFAULT_PROTECTED_PATTERNS only matches "<version>.<digit>..." (a
        # dot then a digit, e.g. "17.0.1"), not "<version>-word". A
        # dash-suffixed name like "17.0-stable" falls through to normal
        # validation and is rejected as an invalid branch name.
        assert _validator().is_protected_branch("17.0-stable") is False

    def test_ordinary_branch_is_not_protected(self):
        assert _validator().is_protected_branch("feature/17.0-add-invoice") is False

    def test_additional_protected_branches_from_config(self, tmp_path):
        config = tmp_path / ".solt-hooks.yaml"
        config.write_text("branch_naming:\n  protected_branches: [qa]\n")
        validator = _validator(config_path=str(config))
        assert validator.is_protected_branch("qa") is True

    def test_additional_protected_patterns_from_config(self, tmp_path):
        config = tmp_path / ".solt-hooks.yaml"
        config.write_text("branch_naming:\n  protected_patterns: ['^sprint-.*$']\n")
        validator = _validator(config_path=str(config))
        assert validator.is_protected_branch("sprint-cleanup") is True

    def test_invalid_regex_in_protected_patterns_is_skipped_not_raised(self, tmp_path):
        config = tmp_path / ".solt-hooks.yaml"
        config.write_text("branch_naming:\n  protected_patterns: ['(unclosed']\n")
        validator = _validator(config_path=str(config))
        # Must not raise re.error - the invalid pattern is silently skipped,
        # and an ordinary branch still isn't protected.
        assert validator.is_protected_branch("feature/17.0-x") is False


class TestExtractOdooVersion:
    def test_direct_version_branch(self):
        assert _validator().extract_odoo_version("17.0") == "17.0"

    def test_prefixed_branch(self):
        assert _validator().extract_odoo_version("feature/17.0-add-invoice") == "17.0"

    def test_version_anywhere_fallback(self):
        # extract_odoo_version's third pattern (re.search, not anchored)
        # pulls a version out of any branch name that contains one, even
        # when the branch doesn't follow any recognized naming convention.
        assert _validator().extract_odoo_version("sprint-17.0-cleanup") == "17.0"

    def test_no_version_present_returns_none(self):
        assert _validator().extract_odoo_version("no-version-here") is None


class TestValidateFlexibleMode:
    def test_version_and_ticket(self):
        is_valid, message = _validator().validate("feature/17.0-SOLT-123-add-invoice")
        assert is_valid is True
        assert "Odoo 17.0" in message

    def test_version_only(self):
        assert _validator().validate("feature/17.0-add-invoice")[0] is True

    def test_version_type_format(self):
        assert _validator().validate("17.0-hotfix-urgent-fix")[0] is True

    def test_release_branch(self):
        assert _validator().validate("release/17.0.1.0")[0] is True

    def test_release_branch_not_tied_to_odoo_version_pattern(self):
        # The release pattern is r"^release/\d+\.\d+(\.\d+)*$" - any
        # dotted-number version, not specifically an Odoo "NN.0" version.
        assert _validator().validate("release/1.0.0")[0] is True

    def test_missing_version_is_rejected(self):
        is_valid, message = _validator().validate("feature/add-something")
        assert is_valid is False
        assert "Invalid branch name" in message

    def test_missing_version_with_ticket_is_still_rejected(self):
        assert _validator().validate("feature/SOLT-123-something")[0] is False

    def test_uppercase_type_is_rejected(self):
        # Branch types are matched case-sensitively; "Feature" isn't in
        # DEFAULT_BRANCH_TYPES (which is all lowercase).
        assert _validator().validate("Feature/17.0-something")[0] is False

    def test_unrecognized_branch_is_rejected(self):
        assert _validator().validate("random-branch-name")[0] is False

    def test_protected_branch_message_mentions_odoo_version_when_present(self):
        is_valid, message = _validator().validate("17.0")
        assert is_valid is True
        assert "Protected Odoo 17.0 branch" in message

    def test_protected_branch_message_without_odoo_version(self):
        is_valid, message = _validator().validate("main")
        assert is_valid is True
        assert message == "Protected branch 'main' - skipped validation"

    def test_ticket_prefix_is_effectively_unenforced_in_flexible_mode(self):
        # Flexible mode's pattern is "(VERSION-PREFIX-N-desc | VERSION-desc)".
        # Even with a restricted ticket_prefixes list, any text after the
        # version still matches the second, unrestricted alternative - so an
        # unrecognized "ticket" prefix is accepted as a plain description,
        # not rejected. Ticket prefixes only bite in strict mode (see
        # TestValidateStrictMode).
        validator = _validator(ticket_prefixes=["SOLT", "PROJ"])
        assert validator.validate("feature/17.0-XYZ-99-x")[0] is True


class TestValidateGithubRevertBranches:
    def test_revert_branch_without_odoo_version_is_rejected(self):
        # github-revert requires an Odoo version somewhere in the wrapped
        # name, consistent with every other pattern's "version is REQUIRED"
        # policy - a version-less revert branch means the original branch
        # shouldn't have passed validation either.
        assert _validator().validate("revert-123-some-branch-with-no-version")[0] is False

    def test_revert_branch_wrapping_a_valid_branch(self):
        is_valid, message = _validator().validate("revert-123-feature/17.0-add-invoice")
        assert is_valid is True
        assert "github-revert" in message


class TestValidateStrictMode:
    def test_version_and_ticket_required(self):
        validator = _validator(strict=True)
        assert validator.validate("feature/17.0-SOLT-123-add-invoice")[0] is True

    def test_version_only_is_rejected(self):
        validator = _validator(strict=True)
        assert validator.validate("feature/17.0-add-invoice")[0] is False

    def test_version_type_format_still_allowed(self):
        # The version-type and release patterns aren't gated by `strict` -
        # only the per-branch-type patterns are.
        validator = _validator(strict=True)
        assert validator.validate("17.0-hotfix-urgent-fix")[0] is True

    def test_custom_ticket_prefix_enforced(self):
        validator = _validator(strict=True, ticket_prefixes=["PROJ"])
        assert validator.validate("feature/17.0-PROJ-99-x")[0] is True
        assert validator.validate("feature/17.0-SOLT-99-x")[0] is False


class TestConfigLoading:
    def test_strict_from_config_used_when_param_omitted(self, tmp_path):
        config = tmp_path / ".solt-hooks.yaml"
        config.write_text("branch_naming:\n  strict: true\n")
        validator = BranchNameValidator(config_path=str(config))
        assert validator.strict is True

    def test_explicit_strict_param_overrides_config(self, tmp_path):
        config = tmp_path / ".solt-hooks.yaml"
        config.write_text("branch_naming:\n  strict: true\n")
        validator = BranchNameValidator(config_path=str(config), strict=False)
        assert validator.strict is False

    def test_allowed_types_from_config_restricts_valid_types(self, tmp_path):
        config = tmp_path / ".solt-hooks.yaml"
        config.write_text("branch_naming:\n  allowed_types: [feature]\n")
        validator = BranchNameValidator(config_path=str(config))
        assert validator.validate("feature/17.0-x")[0] is True
        assert validator.validate("fix/17.0-x")[0] is False

    def test_ticket_prefixes_from_config_used_when_param_omitted(self, tmp_path):
        config = tmp_path / ".solt-hooks.yaml"
        config.write_text("branch_naming:\n  strict: true\n  ticket_prefixes: [FOO]\n")
        validator = BranchNameValidator(config_path=str(config))
        assert validator.validate("feature/17.0-FOO-1-x")[0] is True
        assert validator.validate("feature/17.0-SOLT-1-x")[0] is False

    def test_malformed_yaml_falls_back_to_empty_config(self, tmp_path):
        config = tmp_path / ".solt-hooks.yaml"
        config.write_text(": : : not valid yaml [[[")
        validator = BranchNameValidator(config_path=str(config))
        assert validator.config == {}
        assert validator.strict is False

    def test_nonexistent_config_path_falls_back_to_empty_config(self):
        validator = BranchNameValidator(config_path="/does/not/exist.yaml")
        assert validator.config == {}


class TestGetCurrentBranch:
    def test_returns_branch_name(self):
        with mock.patch("subprocess.run", return_value=mock.Mock(stdout="feature/17.0-x\n")):
            assert _validator().get_current_branch() == "feature/17.0-x"

    def test_git_failure_returns_none(self):
        with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
            assert _validator().get_current_branch() is None


class TestMainCli:
    def _run(self, argv, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["solt-check-branch", "--config", "/nonexistent", *argv])
        with pytest.raises(SystemExit) as exc_info:
            main()
        return exc_info.value.code

    def test_valid_branch_exits_zero_and_prints_ok(self, monkeypatch, capsys):
        code = self._run(["feature/17.0-x"], monkeypatch)
        assert code == 0
        assert capsys.readouterr().out.startswith("[OK]")

    def test_invalid_branch_exits_one_and_prints_to_stderr(self, monkeypatch, capsys):
        code = self._run(["bad-branch"], monkeypatch)
        assert code == 1
        assert "Invalid branch name" in capsys.readouterr().err

    def test_quiet_suppresses_success_output(self, monkeypatch, capsys):
        code = self._run(["-q", "feature/17.0-x"], monkeypatch)
        assert code == 0
        assert capsys.readouterr().out == ""

    def test_show_version_prints_detected_version_and_exits_zero(self, monkeypatch, capsys):
        code = self._run(["--show-version", "feature/17.0-x"], monkeypatch)
        assert code == 0
        assert "Detected Odoo version: 17.0" in capsys.readouterr().out

    def test_show_version_with_no_version_in_branch(self, monkeypatch, capsys):
        code = self._run(["--show-version", "random-branch-name"], monkeypatch)
        assert code == 0
        assert "No Odoo version detected" in capsys.readouterr().out

    def test_no_branch_arg_falls_back_to_current_branch(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["solt-check-branch", "--config", "/nonexistent"])
        with mock.patch.object(BranchNameValidator, "get_current_branch", return_value="feature/17.0-x"):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0

    def test_no_branch_arg_and_no_current_branch_errors(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["solt-check-branch", "--config", "/nonexistent"])
        with mock.patch.object(BranchNameValidator, "get_current_branch", return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 1
        assert "Could not determine branch name" in capsys.readouterr().err

    def test_strict_flag_enforces_ticket(self, monkeypatch):
        code = self._run(["--strict", "feature/17.0-add-invoice"], monkeypatch)
        assert code == 1

    def test_no_strict_flag_allows_version_only(self, monkeypatch):
        code = self._run(["--no-strict", "feature/17.0-add-invoice"], monkeypatch)
        assert code == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
