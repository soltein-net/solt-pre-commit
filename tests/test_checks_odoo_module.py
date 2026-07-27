# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Tests for checks_odoo_module.py: the main orchestrator - module/path
detection helpers, CheckResult/ResultPrinter, the `installable` decorator,
ChecksOdooModule's manifest parsing and check_* delegation, the global
coverage summary, and the run()/main() entry points.

Includes a regression test for the empty-diff fallback fix (CHANGELOG
1.1.0): `pre-commit run --all-files` with nothing staged used to fall back
to validating the repo root itself as a fake module and fail with a
confusing "could not be loaded" error. It should now skip cleanly instead."""

import subprocess
from unittest import mock

import pytest

from solt_pre_commit import checks_odoo_module as mod
from solt_pre_commit.config_loader import SoltConfig


def _run_main(argv=None):
    with mock.patch("sys.argv", ["solt-check-odoo"] + (argv or [])):
        try:
            mod.main()
        except SystemExit as e:
            return e.code
    return None


def _make_config(tmp_path, **overrides):
    # An explicit, nonexistent config_path guarantees config == {} (pure
    # defaults) - the default (no config_path) walks up parent directories
    # from cwd looking for .solt-hooks.yaml, which would pick up this repo's
    # own super-repo config when tests run from within a checkout.
    config = SoltConfig(config_path=str(tmp_path / "nonexistent-hooks.yaml"))
    config.validation_scope = "full"
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def _make_module(tmp_path, name="my_module", manifest=None, files=None):
    mod_dir = tmp_path / name
    mod_dir.mkdir()
    manifest = manifest if manifest is not None else {"name": "My Module", "version": "17.0.1.0.0"}
    (mod_dir / "__manifest__.py").write_text(repr(manifest))
    (mod_dir / "__init__.py").write_text("")
    for relpath, content in (files or {}).items():
        path = mod_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return mod_dir


class TestEmptyDiffFallback:
    def test_no_staged_modules_skips_cleanly_not_root_fallback(self, capsys):
        with mock.patch.object(mod, "_detect_modules_from_staged_files", return_value=[]):
            rc = _run_main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "No Odoo modules detected from staged files" in out

    def test_explicit_paths_with_no_modules_also_skips_cleanly(self, capsys):
        with (
            mock.patch.object(mod, "_is_file_list", return_value=True),
            mock.patch.object(mod, "_detect_modules_from_paths", return_value=[]),
        ):
            rc = _run_main(["some_file.md"])
        assert rc == 0
        assert "No Odoo modules detected from provided files" in capsys.readouterr().out


class TestGetStagedFiles:
    def test_returns_staged_file_list(self):
        with mock.patch(
            "subprocess.run",
            return_value=mock.Mock(stdout="a.py\nb.xml\n", returncode=0),
        ):
            assert mod._get_staged_files() == ["a.py", "b.xml"]

    def test_git_failure_returns_empty_list(self):
        with mock.patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")):
            assert mod._get_staged_files() == []

    def test_git_not_installed_returns_empty_list(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            assert mod._get_staged_files() == []


class TestFindModuleFromFile:
    def test_file_inside_a_module_resolves_to_the_module_dir(self, tmp_path):
        module_dir = _make_module(tmp_path, files={"models/x.py": ""})
        assert mod._find_module_from_file(str(module_dir / "models" / "x.py")) == str(module_dir)

    def test_module_directory_itself_resolves_to_itself(self, tmp_path):
        module_dir = _make_module(tmp_path)
        assert mod._find_module_from_file(str(module_dir)) == str(module_dir)

    def test_file_with_no_manifest_anywhere_above_it_returns_none(self, tmp_path):
        loose_file = tmp_path / "loose.txt"
        loose_file.write_text("")
        assert mod._find_module_from_file(str(loose_file)) is None


class TestDetectModulesFromPaths:
    def test_file_inside_a_module_is_resolved_to_that_module(self, tmp_path):
        module_dir = _make_module(tmp_path, files={"models/x.py": ""})
        assert mod._detect_modules_from_paths([str(module_dir / "models" / "x.py")]) == [str(module_dir)]

    def test_module_directory_passed_directly_is_returned_as_is(self, tmp_path):
        module_dir = _make_module(tmp_path)
        assert mod._detect_modules_from_paths([str(module_dir)]) == [str(module_dir)]

    def test_direct_module_directories_take_precedence_over_discovered_ones(self, tmp_path):
        # If any path IS a module directory, direct_modules short-circuits -
        # discovered modules from other file paths in the same call are
        # dropped rather than merged in.
        direct_module = _make_module(tmp_path, name="direct_module")
        other_module = _make_module(tmp_path, name="other_module", files={"models/x.py": ""})
        result = mod._detect_modules_from_paths([str(other_module / "models" / "x.py"), str(direct_module)])
        assert result == [str(direct_module)]

    def test_none_and_empty_paths_are_skipped(self):
        assert mod._detect_modules_from_paths([None, ""]) == []

    def test_no_matching_modules_returns_empty_list(self, tmp_path):
        loose_file = tmp_path / "loose.txt"
        loose_file.write_text("")
        assert mod._detect_modules_from_paths([str(loose_file)]) == []


class TestIsFileList:
    def test_known_extension_is_a_file(self):
        assert mod._is_file_list(["models.py"]) is True

    def test_existing_file_without_a_recognized_extension_is_a_file(self, tmp_path):
        extensionless = tmp_path / "AUTHORS"
        extensionless.write_text("")
        assert mod._is_file_list([str(extensionless)]) is True

    def test_nonexistent_path_with_unknown_extension_is_not_a_file(self):
        assert mod._is_file_list(["some_module.unknownext"]) is False

    def test_empty_list_is_not_a_file_list(self):
        assert mod._is_file_list([]) is False


class TestDetectModulesFromStagedFiles:
    def test_no_staged_files_returns_none(self):
        with mock.patch.object(mod, "_get_staged_files", return_value=[]):
            assert mod._detect_modules_from_staged_files() is None

    def test_no_relevant_extensions_returns_none(self):
        with mock.patch.object(mod, "_get_staged_files", return_value=["README.md", "docs/notes.txt"]):
            assert mod._detect_modules_from_staged_files() is None

    def test_relevant_files_are_delegated_to_detect_modules_from_paths(self):
        with (
            mock.patch.object(mod, "_get_staged_files", return_value=["my_module/models/x.py", "README.md"]),
            mock.patch.object(mod, "_detect_modules_from_paths", return_value=["my_module"]) as detect_mock,
        ):
            assert mod._detect_modules_from_staged_files() == ["my_module"]
            detect_mock.assert_called_once_with(["my_module/models/x.py"])

    def test_manifest_file_itself_counts_as_relevant_even_without_a_tracked_extension(self):
        with (
            mock.patch.object(mod, "_get_staged_files", return_value=["my_module/__manifest__.py"]),
            mock.patch.object(mod, "_detect_modules_from_paths", return_value=["my_module"]) as detect_mock,
        ):
            mod._detect_modules_from_staged_files()
            detect_mock.assert_called_once_with(["my_module/__manifest__.py"])


class TestCheckResult:
    def test_add_stores_messages_under_the_check_name(self, tmp_path):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("missing_readme", ["msg1", "msg2"])
        assert result.results["missing_readme"] == ["msg1", "msg2"]

    def test_add_is_a_no_op_for_empty_messages(self, tmp_path):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("missing_readme", [])
        assert result.results == {}

    def test_add_skips_disabled_checks(self, tmp_path):
        config = _make_config(tmp_path, disabled_checks={"missing_readme"})
        result = mod.CheckResult(config)
        result.add("missing_readme", ["msg1"])
        assert result.results == {}

    def test_add_shortens_github_actions_runner_paths(self, tmp_path):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("missing_readme", ["/home/runner/work/soltein/soltein/addons/x.py:5 error"])
        assert result.results["missing_readme"] == ["soltein/addons/x.py:5 error"]

    def test_add_from_dict_adds_every_entry(self, tmp_path):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add_from_dict({"missing_readme": ["a"], "manifest_syntax_error": ["b"]})
        assert result.results["missing_readme"] == ["a"]
        assert result.results["manifest_syntax_error"] == ["b"]

    def test_get_by_severity_groups_checks_under_their_configured_severity(self, tmp_path):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("manifest_syntax_error", ["a"])  # ERROR by default
        result.add("missing_readme", ["b"])  # INFO by default
        by_severity = result.get_by_severity()
        assert by_severity[mod.Severity.ERROR] == {"manifest_syntax_error": ["a"]}
        assert by_severity[mod.Severity.INFO] == {"missing_readme": ["b"]}

    def test_has_blocking_issues_true_when_a_blocking_severity_has_messages(self, tmp_path):
        config = _make_config(tmp_path)  # default blocking_severities = {ERROR}
        result = mod.CheckResult(config)
        result.add("manifest_syntax_error", ["a"])  # ERROR
        assert result.has_blocking_issues() is True

    def test_has_blocking_issues_false_when_only_non_blocking_severities_present(self, tmp_path):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("missing_readme", ["a"])  # INFO, not blocking by default
        assert result.has_blocking_issues() is False

    def test_get_counts_tallies_messages_per_severity(self, tmp_path):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("manifest_syntax_error", ["a", "b"])  # ERROR
        result.add("missing_readme", ["c"])  # INFO
        counts = result.get_counts()
        assert counts[mod.Severity.ERROR] == 2
        assert counts[mod.Severity.INFO] == 1
        assert counts[mod.Severity.WARNING] == 0

    def test_has_errors_or_warnings_false_when_only_info_present(self, tmp_path):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("missing_readme", ["a"])  # INFO
        assert result.has_errors_or_warnings() is False

    def test_has_errors_or_warnings_true_when_an_error_is_present(self, tmp_path):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("manifest_syntax_error", ["a"])
        assert result.has_errors_or_warnings() is True

    def test_is_empty_true_for_a_fresh_result(self, tmp_path):
        config = _make_config(tmp_path)
        assert mod.CheckResult(config).is_empty() is True

    def test_is_empty_false_once_something_is_added(self, tmp_path):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("missing_readme", ["a"])
        assert result.is_empty() is False

    def test_has_visible_issues_true_for_an_error_regardless_of_show_info(self, tmp_path):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("manifest_syntax_error", ["a"])
        assert result.has_visible_issues(show_info=False) is True

    def test_has_visible_issues_false_for_info_only_when_show_info_is_false(self, tmp_path):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("missing_readme", ["a"])  # INFO
        assert result.has_visible_issues(show_info=False) is False
        assert result.has_visible_issues(show_info=True) is True

    def test_has_blocking_issues_skips_a_check_name_with_no_messages(self, tmp_path):
        # add() never stores an empty list (it returns early), but the
        # `if not messages: continue` guard in has_blocking_issues covers a
        # defaultdict entry that ended up empty by direct manipulation.
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.results["manifest_syntax_error"] = []
        assert result.has_blocking_issues() is False

    def test_has_visible_issues_skips_a_check_name_with_no_messages(self, tmp_path):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.results["manifest_syntax_error"] = []
        assert result.has_visible_issues() is False


class TestResultPrinter:
    def test_defaults_disable_colors_and_unicode_outside_a_tty(self):
        # sys.stdout.isatty() is False under pytest, so both are forced off
        # even though use_colors defaults to True.
        printer = mod.ResultPrinter()
        assert printer.use_colors is False
        assert printer.use_unicode is False

    def test_max_messages_defaults_to_ten_outside_ci(self, monkeypatch):
        monkeypatch.delenv("CI", raising=False)
        assert mod.ResultPrinter().max_messages == 10

    def test_max_messages_defaults_to_unlimited_in_ci(self, monkeypatch):
        monkeypatch.setenv("CI", "true")
        assert mod.ResultPrinter().max_messages is None

    def test_explicit_max_messages_overrides_the_ci_default(self, monkeypatch):
        monkeypatch.setenv("CI", "true")
        assert mod.ResultPrinter(max_messages=3).max_messages == 3

    def test_print_results_is_a_no_op_for_an_empty_result(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        mod.ResultPrinter(use_colors=False).print_results(result)
        assert capsys.readouterr().out == ""

    def test_print_results_shows_module_header_and_severity_sections(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("manifest_syntax_error", ["bad.py:1 broken"])  # ERROR, blocking
        mod.ResultPrinter(use_colors=False, use_unicode=False).print_results(
            result, module_name="my_module", validation_scope="full"
        )
        out = capsys.readouterr().out
        assert "MODULE: my_module" in out
        assert "full repository" in out
        assert "[BLOCKING]" in out
        assert "Manifest Syntax Error (1)" in out
        assert "bad.py:1 broken" in out

    def test_print_results_truncates_overly_long_messages(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        long_message = "x" * 250
        result.add("missing_readme", [long_message])
        mod.ResultPrinter(use_colors=False, max_messages=None).print_results(result)
        out = capsys.readouterr().out
        assert "..." in out
        assert long_message not in out

    def test_print_results_reports_remaining_count_past_max_messages(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("missing_readme", ["a", "b", "c"])
        mod.ResultPrinter(use_colors=False, max_messages=2).print_results(result)
        assert "... and 1 more" in capsys.readouterr().out

    def test_print_results_hides_info_when_show_info_is_false(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("missing_readme", ["a"])  # INFO only
        mod.ResultPrinter(use_colors=False, show_info=False).print_results(result)
        # is_empty() is False (there IS a result), but the INFO section is
        # skipped entirely, so nothing check-specific gets printed.
        out = capsys.readouterr().out
        assert "Missing Readme" not in out

    def test_print_blocking_notice_is_a_no_op_without_blocking_issues(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("missing_readme", ["a"])  # INFO, not blocking
        mod.ResultPrinter(use_colors=False).print_blocking_notice(result)
        assert capsys.readouterr().out == ""

    def test_print_blocking_notice_prints_when_blocking_issues_exist(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        result = mod.CheckResult(config)
        result.add("manifest_syntax_error", ["a"])  # ERROR, blocking
        mod.ResultPrinter(use_colors=False).print_blocking_notice(result)
        assert "VALIDATION FAILED" in capsys.readouterr().out

    def test_print_success_mentions_module_name_and_changed_scope(self, capsys):
        mod.ResultPrinter(use_colors=False).print_success("my_module", validation_scope="changed")
        out = capsys.readouterr().out
        assert "my_module" in out
        assert "(changed files)" in out

    def test_print_success_without_a_module_name_is_generic(self, capsys):
        mod.ResultPrinter(use_colors=False).print_success()
        assert "All checks passed!" in capsys.readouterr().out

    def test_get_icon_uses_unicode_icons_when_enabled(self):
        printer = mod.ResultPrinter(use_unicode=True)
        assert printer._get_icon(mod.Severity.ERROR) == mod.Severity.ICONS_UNICODE[mod.Severity.ERROR]

    def test_color_wraps_text_in_ansi_codes_when_colors_are_enabled(self):
        # use_colors is normally forced off outside a tty (see the
        # defaults-disable test above) - set the instance attribute directly
        # to exercise the colored-output branch without faking a tty.
        printer = mod.ResultPrinter(use_colors=False)
        printer.use_colors = True
        assert printer._color("text", mod.Severity.COLORS[mod.Severity.ERROR]) == (
            f"{mod.Severity.COLORS[mod.Severity.ERROR]}text{mod.Severity.RESET}"
        )

    def test_bold_wraps_text_in_ansi_codes_when_colors_are_enabled(self):
        printer = mod.ResultPrinter(use_colors=False)
        printer.use_colors = True
        assert printer._bold("text") == f"{mod.Severity.BOLD}text{mod.Severity.RESET}"


class TestInstallableDecorator:
    def test_runs_the_method_when_installable_and_no_error(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_missing_readme()
        assert "missing_readme" in checks.check_result.results

    def test_skips_and_logs_when_module_is_not_installable(self, tmp_path, capsys):
        module_dir = _make_module(tmp_path, manifest={"name": "x", "installable": False})
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), verbose=True, severity_config=config)
        checks.check_missing_readme()
        assert checks.check_result.results == {}
        assert "is not installable" in capsys.readouterr().out

    def test_skips_and_logs_when_manifest_failed_to_parse(self, tmp_path, capsys):
        module_dir = tmp_path / "broken_module"
        module_dir.mkdir()
        (module_dir / "__manifest__.py").write_text("{not valid python at all")
        (module_dir / "__init__.py").write_text("")
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), verbose=True, severity_config=config)
        checks.check_missing_readme()
        assert checks.check_result.results == {}
        assert "with error" in capsys.readouterr().out

    def test_silent_when_not_verbose(self, tmp_path, capsys):
        module_dir = _make_module(tmp_path, manifest={"name": "x", "installable": False})
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), verbose=False, severity_config=config)
        checks.check_missing_readme()
        assert capsys.readouterr().out == ""


class TestChecksOdooModuleInit:
    def test_manifest_file_path_resolves_from_a_directory(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks.manifest_path == str(module_dir / "__manifest__.py")

    def test_manifest_file_path_passed_directly_is_unchanged(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        manifest_file = str(module_dir / "__manifest__.py")
        checks = mod.ChecksOdooModule(manifest_file, severity_config=config)
        assert checks.manifest_path == manifest_file

    def test_manifest_without_init_py_is_treated_as_empty(self, tmp_path):
        # A directory that merely happens to contain a __manifest__.py isn't
        # a real installable Odoo module without __init__.py too.
        module_dir = tmp_path / "not_a_real_module"
        module_dir.mkdir()
        (module_dir / "__manifest__.py").write_text(repr({"name": "x"}))
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks.manifest_dict == {}

    def test_is_installable_defaults_to_true(self, tmp_path):
        module_dir = _make_module(tmp_path, manifest={"name": "x"})
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks.is_module_installable is True

    def test_is_installable_respects_explicit_false(self, tmp_path):
        module_dir = _make_module(tmp_path, manifest={"name": "x", "installable": False})
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks.is_module_installable is False

    def test_odoo_version_detected_from_manifest(self, tmp_path):
        module_dir = _make_module(tmp_path, manifest={"name": "x", "version": "18.0.2.0.0"})
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks.odoo_version == "18.0"

    def test_odoo_version_accepts_a_future_major_version(self, tmp_path):
        module_dir = _make_module(tmp_path, manifest={"name": "x", "version": "25.0.1.0.0"})
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks.odoo_version == "25.0"

    def test_odoo_version_falls_back_to_config_when_manifest_has_none(self, tmp_path):
        module_dir = _make_module(tmp_path, manifest={"name": "x"})
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks.odoo_version == "17.0"

    def test_odoo_version_falls_back_to_config_for_an_unparseable_version(self, tmp_path):
        module_dir = _make_module(tmp_path, manifest={"name": "x", "version": "not.a.version"})
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks.odoo_version == "17.0"

    def test_explicit_odoo_version_argument_overrides_detection(self, tmp_path):
        module_dir = _make_module(tmp_path, manifest={"name": "x", "version": "17.0.1.0.0"})
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config, odoo_version="19.0")
        assert checks.odoo_version == "19.0"

    def test_directory_with_no_manifest_at_all_has_an_empty_manifest_dict(self, tmp_path):
        # _get_manifest_file_path falls through unchanged for a directory
        # with no __manifest__.py/__openerp__.py - its basename (the
        # directory's own name) never matches MANIFEST_NAMES.
        empty_dir = tmp_path / "not_a_module"
        empty_dir.mkdir()
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(empty_dir), severity_config=config)
        assert checks.manifest_dict == {}

    def test_manifest_path_pointing_at_a_nonexistent_file_has_an_empty_manifest_dict(self, tmp_path):
        missing_manifest = tmp_path / "ghost_module" / "__manifest__.py"
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(missing_manifest), severity_config=config)
        assert checks.manifest_dict == {}


class TestReferencedFilesByExtension:
    def test_manifest_data_files_are_collected_by_extension(self, tmp_path):
        module_dir = _make_module(
            tmp_path,
            manifest={"name": "x", "data": ["views/x.xml"], "demo": ["demo/d.xml"]},
            files={"views/x.xml": "<odoo/>", "demo/d.xml": "<odoo/>"},
        )
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        xml_files = checks.manifest_referenced_files[".xml"]
        assert {f["filename_short"] for f in xml_files} == {"views/x.xml", "demo/d.xml"}
        assert {f["data_section"] for f in xml_files} == {"data", "demo"}

    def test_excluded_paths_are_not_collected(self, tmp_path):
        module_dir = _make_module(
            tmp_path,
            manifest={"name": "x", "data": ["data/migrations/17.0.1.0/x.xml"]},
            files={"data/migrations/17.0.1.0/x.xml": "<odoo/>"},
        )
        config = _make_config(tmp_path)  # DEFAULT_EXCLUDE_PATHS includes **/migrations/**
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks.manifest_referenced_files[".xml"] == []

    def test_i18n_po_and_pot_files_are_discovered_without_being_in_the_manifest(self, tmp_path):
        module_dir = _make_module(
            tmp_path,
            files={"i18n/es.po": "", "i18n/my_module.pot": ""},
        )
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        po_files = {f["filename_short"] for f in checks.manifest_referenced_files[".po"]}
        pot_files = {f["filename_short"] for f in checks.manifest_referenced_files[".pot"]}
        assert any("es.po" in f for f in po_files)
        assert any("my_module.pot" in f for f in pot_files)

    def test_python_files_are_discovered_by_walking_the_module_tree(self, tmp_path):
        module_dir = _make_module(tmp_path, files={"models/res_partner.py": "", "static/ignored.py": ""})
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        py_files = {f["filename_short"] for f in checks.manifest_referenced_files[".py"]}
        # static/ is excluded from the directory walk entirely.
        assert any("res_partner.py" in f for f in py_files)
        assert not any("ignored.py" in f for f in py_files)

    def test_excluded_python_paths_are_not_collected(self, tmp_path):
        module_dir = _make_module(tmp_path, files={"models/tests/test_x.py": ""})
        config = _make_config(tmp_path)  # DEFAULT_EXCLUDE_PATHS includes **/tests/**
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        py_files = {f["filename_short"] for f in checks.manifest_referenced_files[".py"]}
        assert not any("test_x.py" in f for f in py_files)

    def test_excluded_i18n_paths_are_not_collected(self, tmp_path):
        module_dir = _make_module(tmp_path, files={"i18n/es.po": ""})
        config = _make_config(tmp_path, exclude_paths=["**/i18n/**"])
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks.manifest_referenced_files[".po"] == []


class TestGetFilesToValidate:
    def test_no_changed_detector_returns_all_referenced_files(self, tmp_path):
        module_dir = _make_module(
            tmp_path, manifest={"name": "x", "data": ["views/x.xml"]}, files={"views/x.xml": "<odoo/>"}
        )
        config = _make_config(tmp_path)  # validation_scope="full" -> no changed detector
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert len(checks._get_files_to_validate(".xml")) == 1

    def test_unreferenced_extension_returns_empty_list(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks._get_files_to_validate(".csv") == []

    def test_changed_scope_delegates_to_the_changed_detector(self, tmp_path):
        module_dir = _make_module(
            tmp_path, manifest={"name": "x", "data": ["views/x.xml"]}, files={"views/x.xml": "<odoo/>"}
        )
        config = _make_config(tmp_path, validation_scope="changed")
        fake_detector = mock.Mock()
        fake_detector.filter_changed_files.return_value = ["filtered"]
        config._changed_detector = fake_detector
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks._get_files_to_validate(".xml") == ["filtered"]


class TestHasChangedFiles:
    def test_true_when_scope_is_full(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks.has_changed_files() is True

    def test_false_when_changed_scope_has_no_matching_files(self, tmp_path):
        module_dir = _make_module(
            tmp_path, manifest={"name": "x", "data": ["views/x.xml"]}, files={"views/x.xml": "<odoo/>"}
        )
        config = _make_config(tmp_path, validation_scope="changed")
        fake_detector = mock.Mock()
        fake_detector.filter_changed_files.return_value = []
        config._changed_detector = fake_detector
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks.has_changed_files() is False

    def test_true_when_changed_scope_has_at_least_one_matching_file(self, tmp_path):
        module_dir = _make_module(
            tmp_path, manifest={"name": "x", "data": ["views/x.xml"]}, files={"views/x.xml": "<odoo/>"}
        )
        config = _make_config(tmp_path, validation_scope="changed")
        fake_detector = mock.Mock()
        fake_detector.filter_changed_files.return_value = [{"filename": "views/x.xml"}]
        config._changed_detector = fake_detector
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks.has_changed_files() is True


class TestShouldRunCheck:
    def test_none_check_mode_always_runs(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert checks._should_run_check("xml") is True
        assert checks._should_run_check("python") is True

    def test_matching_check_mode_runs(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), check_mode="xml", severity_config=config)
        assert checks._should_run_check("xml") is True

    def test_non_matching_check_mode_is_skipped(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), check_mode="xml", severity_config=config)
        assert checks._should_run_check("python") is False


class TestCheckManifest:
    def test_empty_manifest_reports_syntax_error(self, tmp_path):
        module_dir = tmp_path / "broken_module"
        module_dir.mkdir()
        (module_dir / "__manifest__.py").write_text("{not valid python at all")
        (module_dir / "__init__.py").write_text("")
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_manifest()
        assert "manifest_syntax_error" in checks.check_result.results

    def test_valid_manifest_reports_nothing(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_manifest()
        assert checks.check_result.results == {}

    def test_skipped_when_check_mode_is_something_else(self, tmp_path):
        module_dir = tmp_path / "broken_module"
        module_dir.mkdir()
        (module_dir / "__manifest__.py").write_text("{not valid python at all")
        (module_dir / "__init__.py").write_text("")
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), check_mode="xml", severity_config=config)
        checks.check_manifest()
        assert checks.check_result.results == {}


class TestCheckMissingReadme:
    def test_missing_readme_is_reported(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_missing_readme()
        assert "missing_readme" in checks.check_result.results

    def test_present_readme_is_not_reported(self, tmp_path):
        module_dir = _make_module(tmp_path, files={"README.md": "# My Module\n"})
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_missing_readme()
        assert checks.check_result.results == {}

    def test_skipped_when_check_mode_is_something_else(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), check_mode="xml", severity_config=config)
        checks.check_missing_readme()
        assert checks.check_result.results == {}


class TestCheckXmlDelegation:
    def test_no_xml_files_is_a_no_op(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_xml()
        assert checks.check_result.results == {}

    def test_xml_issue_is_aggregated_into_check_result(self, tmp_path):
        module_dir = _make_module(
            tmp_path,
            manifest={"name": "x", "data": ["views/x.xml"]},
            files={"views/x.xml": '<odoo><record id="r1" model="x"/><record id="r1" model="x"/></odoo>'},
        )
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_xml()
        assert "xml_duplicate_record_id" in checks.check_result.results

    def test_xml_advanced_issue_is_aggregated_into_check_result(self, tmp_path):
        module_dir = _make_module(
            tmp_path,
            manifest={"name": "x", "data": ["views/x.xml"]},
            files={"views/x.xml": '<odoo><field t-raw="v"/></odoo>'},
        )
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_xml_advanced()
        assert "xml_deprecated_t_raw" in checks.check_result.results

    def test_check_xml_skipped_when_check_mode_is_something_else(self, tmp_path):
        module_dir = _make_module(
            tmp_path,
            manifest={"name": "x", "data": ["views/x.xml"]},
            files={"views/x.xml": '<odoo><record id="r1" model="x"/><record id="r1" model="x"/></odoo>'},
        )
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), check_mode="python", severity_config=config)
        checks.check_xml()
        assert checks.check_result.results == {}

    def test_check_xml_advanced_skipped_when_check_mode_is_something_else(self, tmp_path):
        module_dir = _make_module(
            tmp_path,
            manifest={"name": "x", "data": ["views/x.xml"]},
            files={"views/x.xml": '<odoo><field t-raw="v"/></odoo>'},
        )
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), check_mode="python", severity_config=config)
        checks.check_xml_advanced()
        assert checks.check_result.results == {}


class TestCheckCsvDelegation:
    def test_no_csv_files_is_a_no_op(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_csv()
        assert checks.check_result.results == {}

    def test_csv_issue_is_aggregated_into_check_result(self, tmp_path):
        module_dir = _make_module(
            tmp_path,
            manifest={"name": "x", "data": ["data/d.csv"]},
            files={"data/d.csv": "id,name\nrec1,a\nrec1,b\n"},
        )
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_csv()
        assert "csv_duplicate_record_id" in checks.check_result.results

    def test_skipped_when_check_mode_is_something_else(self, tmp_path):
        module_dir = _make_module(
            tmp_path,
            manifest={"name": "x", "data": ["data/d.csv"]},
            files={"data/d.csv": "id,name\nrec1,a\nrec1,b\n"},
        )
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), check_mode="xml", severity_config=config)
        checks.check_csv()
        assert checks.check_result.results == {}


class TestCheckPoDelegation:
    def test_no_po_files_is_a_no_op(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_po()
        assert checks.check_result.results == {}

    def test_po_issue_is_aggregated_into_check_result(self, tmp_path):
        module_dir = _make_module(
            tmp_path,
            files={"i18n/es.po": 'msgid ""\nmsgstr ""\n\nmsgid "Hello"\nmsgstr "Hola"\n'},
        )
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_po()
        assert "po_requires_module" in checks.check_result.results

    def test_skipped_when_check_mode_is_something_else(self, tmp_path):
        module_dir = _make_module(
            tmp_path, files={"i18n/es.po": 'msgid ""\nmsgstr ""\n\nmsgid "Hello"\nmsgstr "Hola"\n'}
        )
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), check_mode="xml", severity_config=config)
        checks.check_po()
        assert checks.check_result.results == {}


class TestCheckPythonDelegation:
    def test_no_python_files_beyond_init_is_a_no_op(self, tmp_path):
        # __init__.py itself has no fields/methods worth flagging.
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_python()
        assert checks.check_result.results == {}

    def test_python_issue_is_aggregated_into_check_result(self, tmp_path):
        module_dir = _make_module(
            tmp_path,
            files={
                "models/x.py": "from odoo import fields, models\n\n\n"
                'class M(models.Model):\n    _name = "m"\n\n    custom_field = fields.Char()\n'
            },
        )
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_python()
        assert "python_field_missing_string" in checks.check_result.results

    def test_populates_manifest_referenced_files_with_extracted_models_and_fields(self, tmp_path):
        module_dir = _make_module(
            tmp_path,
            files={
                "models/x.py": "from odoo import fields, models\n\n\n"
                'class M(models.Model):\n    _name = "m"\n\n    name = fields.Char()\n'
            },
        )
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_python()
        (file_data,) = [f for f in checks.manifest_referenced_files[".py"] if "x.py" in f["filename"]]
        assert file_data["models"]
        assert file_data["fields"]

    def test_skipped_when_check_mode_is_something_else(self, tmp_path):
        module_dir = _make_module(
            tmp_path,
            files={
                "models/x.py": "from odoo import fields, models\n\n\n"
                'class M(models.Model):\n    _name = "m"\n\n    custom_field = fields.Char()\n'
            },
        )
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), check_mode="xml", severity_config=config)
        checks.check_python()
        assert checks.check_result.results == {}

    def test_no_matching_python_files_in_changed_scope_is_a_no_op(self, tmp_path):
        # __manifest__.py itself always ends in ".py" and gets swept up by
        # the directory walk, so a real module directory never has zero
        # entries in manifest_referenced_files[".py"] - the only way
        # _get_files_to_validate(".py") comes back empty is the "changed"
        # scope filtering everything out.
        module_dir = _make_module(
            tmp_path,
            files={
                "models/x.py": "from odoo import fields, models\n\n\n"
                'class M(models.Model):\n    _name = "m"\n\n    custom_field = fields.Char()\n'
            },
        )
        config = _make_config(tmp_path, validation_scope="changed")
        fake_detector = mock.Mock()
        fake_detector.filter_changed_files.return_value = []
        config._changed_detector = fake_detector
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.check_python()
        assert checks.check_result.results == {}


class TestCollectCoverageData:
    def test_populates_models_regardless_of_validation_scope(self, tmp_path):
        # collect_coverage_data ignores the changed/full scope split entirely -
        # it always parses every .py file the manifest references.
        module_dir = _make_module(
            tmp_path,
            files={
                "models/x.py": "from odoo import fields, models\n\n\n"
                'class M(models.Model):\n    _name = "m"\n\n    name = fields.Char()\n'
            },
        )
        config = _make_config(tmp_path, validation_scope="changed")
        fake_detector = mock.Mock()
        fake_detector.filter_changed_files.return_value = []  # nothing "changed"
        config._changed_detector = fake_detector
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.collect_coverage_data()
        (file_data,) = [f for f in checks.manifest_referenced_files[".py"] if "x.py" in f["filename"]]
        assert file_data["models"]

    def test_no_python_files_is_a_no_op(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        checks.collect_coverage_data()  # must not raise

    def test_directory_with_zero_python_files_anywhere_is_a_no_op(self, tmp_path):
        # Unlike check_python's manifest_datas, collect_coverage_data reads
        # straight from manifest_referenced_files - genuinely empty only for
        # a directory with no .py file anywhere, not even a manifest.
        empty_dir = tmp_path / "not_a_module_at_all"
        empty_dir.mkdir()
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(empty_dir), severity_config=config)
        assert checks.manifest_referenced_files.get(".py", []) == []
        checks.collect_coverage_data()  # must not raise


class TestGetCheckMethods:
    def test_get_check_methods_yields_every_check_prefixed_attribute(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        names = {getattr(m, "__name__", None) for m in checks._get_check_methods(checks)}
        # installable-wrapped methods all resolve to the decorator's own
        # closure ("inner"), not their original name - only the undecorated
        # check_manifest keeps its real __name__.
        assert "check_manifest" in names
        assert len(list(checks._get_check_methods(checks))) == 7

    def test_getattr_checks_is_equivalent_to_get_check_methods_on_an_instance(self, tmp_path):
        module_dir = _make_module(tmp_path)
        config = _make_config(tmp_path)
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config)
        assert len(list(checks.getattr_checks())) == len(list(checks._get_check_methods(checks)))


class TestPrintGlobalCoverageMetrics:
    def _checks_obj_with(self, models=None, fields=None, methods=None):
        obj = mock.Mock()
        obj.manifest_referenced_files = {
            ".py": [{"models": models or {}, "fields": fields or {}, "methods": methods or {}}]
        }
        return obj

    def test_reports_nothing_when_there_is_no_data_at_all(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        mod._print_global_coverage_metrics([("m", self._checks_obj_with())], config)
        assert capsys.readouterr().out == ""

    def test_reports_field_and_method_coverage_percentages(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        obj = self._checks_obj_with(
            models={"M": {"is_odoo_model": True}},
            fields={"M": [{"name": "custom_field", "string": "Label", "help": None}]},
            methods={"M": [{"name": "do_x", "has_docstring": True}]},
        )
        mod._print_global_coverage_metrics([("m", obj)], config)
        out = capsys.readouterr().out
        assert "REPOSITORY COVERAGE" in out
        assert "Models: 1" in out
        assert "METRICS:" in out

    def test_skip_listed_field_names_are_excluded_from_the_denominator(self, tmp_path, capsys):
        config = _make_config(tmp_path)  # "name" is in DEFAULT_SKIP_STRING_FIELDS/HELP_FIELDS
        obj = self._checks_obj_with(
            fields={
                "M": [
                    {"name": "name", "string": None, "help": None},
                    {"name": "custom_field", "string": None, "help": None},
                ]
            }
        )
        mod._print_global_coverage_metrics([("m", obj)], config)
        out = capsys.readouterr().out
        # 2 total fields, but "name" is skip-listed - only custom_field counts.
        assert "Fields needing string: 1" in out

    def test_related_fields_are_excluded_entirely(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        obj = self._checks_obj_with(
            fields={"M": [{"name": "custom_field", "related": "x.y", "string": None, "help": None}]}
        )
        mod._print_global_coverage_metrics([("m", obj)], config)
        assert capsys.readouterr().out == ""

    def test_private_field_names_are_excluded_entirely(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        obj = self._checks_obj_with(fields={"M": [{"name": "_private", "string": None, "help": None}]})
        mod._print_global_coverage_metrics([("m", obj)], config)
        assert capsys.readouterr().out == ""

    def test_field_with_help_counts_toward_the_help_percentage(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        obj = self._checks_obj_with(fields={"M": [{"name": "custom_field", "string": "Label", "help": "Explains it"}]})
        mod._print_global_coverage_metrics([("m", obj)], config)
        out = capsys.readouterr().out
        assert "Fields with help:    100.0%  (1/1)" in out

    def test_private_and_skip_listed_methods_are_excluded_from_the_docstring_count(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        obj = self._checks_obj_with(
            fields={"M": [{"name": "custom_field", "string": "x", "help": "x"}]},
            methods={
                "M": [
                    {"name": "_helper", "has_docstring": False},
                    {"name": "__init__", "has_docstring": False},  # in DEFAULT_SKIP_DOCSTRING_METHODS
                    {"name": "do_x", "has_docstring": True},
                ]
            },
        )
        mod._print_global_coverage_metrics([("m", obj)], config)
        out = capsys.readouterr().out
        # Only "do_x" counts - the private helper and the skip-listed dunder don't.
        assert "Total Fields: 1 | Public Methods: 1" in out
        assert "Docstrings:          100.0%  (1/1)" in out


class TestRun:
    def test_manifest_paths_defaults_to_empty_list_when_none(self, tmp_path):
        all_results, exit_code = mod.run(
            manifest_paths=None,
            do_exit=False,
            verbose=True,
            config_path=str(tmp_path / "nonexistent-hooks.yaml"),
            force_scope="full",
            show_coverage=False,
        )
        assert all_results == []
        assert exit_code == 0

    def test_no_blocking_issues_returns_exit_code_zero(self, tmp_path, capsys):
        module_dir = _make_module(tmp_path, files={"README.md": "# x\n"})
        all_results, exit_code = mod.run(
            manifest_paths=[str(module_dir)],
            do_exit=False,
            verbose=False,
            config_path=str(tmp_path / "nonexistent-hooks.yaml"),
            force_scope="full",
        )
        assert exit_code == 0

    def test_blocking_issue_returns_exit_code_one(self, tmp_path):
        module_dir = tmp_path / "broken_module"
        module_dir.mkdir()
        (module_dir / "__manifest__.py").write_text("{not valid python at all")
        (module_dir / "__init__.py").write_text("")
        all_results, exit_code = mod.run(
            manifest_paths=[str(module_dir)],
            do_exit=False,
            verbose=False,
            config_path=str(tmp_path / "nonexistent-hooks.yaml"),
            force_scope="full",
        )
        assert exit_code == 1
        assert any(result.has_blocking_issues() for _name, result in all_results)

    def test_verbose_prints_module_results_and_summary(self, tmp_path, capsys):
        module_dir = tmp_path / "broken_module"
        module_dir.mkdir()
        (module_dir / "__manifest__.py").write_text("{not valid python at all")
        (module_dir / "__init__.py").write_text("")
        mod.run(
            manifest_paths=[str(module_dir)],
            do_exit=False,
            verbose=True,
            config_path=str(tmp_path / "nonexistent-hooks.yaml"),
            force_scope="full",
            show_coverage=False,
        )
        combined = capsys.readouterr()
        assert "SOLT PRE-COMMIT VALIDATION" in combined.err
        assert "broken_module" in combined.err

    def test_show_all_modules_prints_success_for_clean_modules(self, tmp_path, capsys):
        module_dir = _make_module(tmp_path, files={"README.md": "# x\n"})
        mod.run(
            manifest_paths=[str(module_dir)],
            do_exit=False,
            verbose=True,
            config_path=str(tmp_path / "nonexistent-hooks.yaml"),
            force_scope="full",
            show_coverage=False,
            show_all_modules=True,
        )
        # run()'s printer is constructed with use_stderr=True.
        assert "All checks passed!" in capsys.readouterr().err

    def test_show_all_modules_prints_full_results_for_a_module_with_issues(self, tmp_path, capsys):
        module_dir = tmp_path / "broken_module"
        module_dir.mkdir()
        (module_dir / "__manifest__.py").write_text("{not valid python at all")
        (module_dir / "__init__.py").write_text("")
        mod.run(
            manifest_paths=[str(module_dir)],
            do_exit=False,
            verbose=True,
            config_path=str(tmp_path / "nonexistent-hooks.yaml"),
            force_scope="full",
            show_coverage=False,
            show_all_modules=True,
        )
        assert "MODULE: broken_module" in capsys.readouterr().err

    def test_show_info_true_prints_info_count_in_summary(self, tmp_path, capsys):
        module_dir = _make_module(tmp_path)  # missing README -> an INFO-level issue
        mod.run(
            manifest_paths=[str(module_dir)],
            do_exit=False,
            verbose=True,
            config_path=str(tmp_path / "nonexistent-hooks.yaml"),
            force_scope="full",
            show_coverage=False,
            show_info=True,
        )
        assert "Info:" in capsys.readouterr().err

    def test_show_coverage_default_prints_repository_coverage_section(self, tmp_path, capsys):
        module_dir = _make_module(
            tmp_path,
            files={
                "models/x.py": "from odoo import fields, models\n\n\n"
                'class M(models.Model):\n    _name = "m"\n\n    custom_field = fields.Char()\n',
                "README.md": "# x\n",
            },
        )
        mod.run(
            manifest_paths=[str(module_dir)],
            do_exit=False,
            verbose=True,
            config_path=str(tmp_path / "nonexistent-hooks.yaml"),
            force_scope="full",
        )
        assert "REPOSITORY COVERAGE" in capsys.readouterr().out

    def test_verbose_json_report_success_prints_saved_message(self, tmp_path, capsys):
        module_dir = _make_module(tmp_path, files={"README.md": "# x\n"})
        report_path = tmp_path / "coverage.json"
        mod.run(
            manifest_paths=[str(module_dir)],
            do_exit=False,
            verbose=True,
            config_path=str(tmp_path / "nonexistent-hooks.yaml"),
            force_scope="full",
            show_coverage=False,
            json_report=str(report_path),
        )
        assert f"Coverage report saved to: {report_path}" in capsys.readouterr().out

    def test_do_exit_true_calls_sys_exit_with_the_computed_code(self, tmp_path):
        module_dir = _make_module(tmp_path, files={"README.md": "# x\n"})
        with pytest.raises(SystemExit) as exc_info:
            mod.run(
                manifest_paths=[str(module_dir)],
                do_exit=True,
                verbose=False,
                config_path=str(tmp_path / "nonexistent-hooks.yaml"),
                force_scope="full",
                show_coverage=False,
            )
        assert exc_info.value.code == 0

    def test_odoo_version_override_is_applied(self, tmp_path):
        module_dir = _make_module(tmp_path, files={"README.md": "# x\n"})
        all_results, _exit_code = mod.run(
            manifest_paths=[str(module_dir)],
            do_exit=False,
            verbose=False,
            config_path=str(tmp_path / "nonexistent-hooks.yaml"),
            force_scope="full",
            odoo_version="19.0",
        )
        # No results means no issues - confirm indirectly via a second run
        # that inspects the checks_obj instead, since `run` only returns
        # results, not the checks_objects themselves. Re-run through
        # ChecksOdooModule directly to check the version was actually used.
        from solt_pre_commit.config_loader import OdooVersionDetector, SoltConfig

        config = SoltConfig(config_path=str(tmp_path / "nonexistent-hooks.yaml"))
        config.set_odoo_version(OdooVersionDetector.normalize_version("19.0"))
        checks = mod.ChecksOdooModule(str(module_dir), severity_config=config, odoo_version="19.0")
        assert checks.odoo_version == "19.0"

    def test_no_manifest_paths_produces_no_summary_output(self, tmp_path, capsys):
        all_results, exit_code = mod.run(
            manifest_paths=[],
            do_exit=False,
            verbose=True,
            config_path=str(tmp_path / "nonexistent-hooks.yaml"),
            force_scope="full",
            show_coverage=False,
        )
        assert exit_code == 0
        assert all_results == []
        assert capsys.readouterr().err == ""

    def test_json_report_is_written_on_success(self, tmp_path):
        module_dir = _make_module(tmp_path, files={"README.md": "# x\n"})
        report_path = tmp_path / "coverage.json"
        mod.run(
            manifest_paths=[str(module_dir)],
            do_exit=False,
            verbose=False,
            config_path=str(tmp_path / "nonexistent-hooks.yaml"),
            force_scope="full",
            json_report=str(report_path),
        )
        assert report_path.exists()

    def test_json_report_failure_is_reported_but_does_not_crash(self, tmp_path, capsys):
        module_dir = _make_module(tmp_path, files={"README.md": "# x\n"})
        with mock.patch("solt_pre_commit.doc_coverage.build_coverage_report", side_effect=RuntimeError("boom")):
            mod.run(
                manifest_paths=[str(module_dir)],
                do_exit=False,
                verbose=True,
                config_path=str(tmp_path / "nonexistent-hooks.yaml"),
                force_scope="full",
                json_report=str(tmp_path / "coverage.json"),
                show_coverage=False,
            )
        assert "Failed to generate coverage report" in capsys.readouterr().out


class TestMain:
    def test_check_xml_only_flag_sets_check_mode(self, tmp_path):
        module_dir = _make_module(tmp_path)
        with mock.patch.object(mod, "run") as run_mock:
            _run_main(["--check-xml-only", str(module_dir)])
        assert run_mock.call_args.kwargs["check_mode"] == "xml"

    def test_check_python_only_flag_sets_check_mode(self, tmp_path):
        module_dir = _make_module(tmp_path)
        with mock.patch.object(mod, "run") as run_mock:
            _run_main(["--check-python-only", str(module_dir)])
        assert run_mock.call_args.kwargs["check_mode"] == "python"

    def test_check_csv_only_flag_sets_check_mode(self, tmp_path):
        module_dir = _make_module(tmp_path)
        with mock.patch.object(mod, "run") as run_mock:
            _run_main(["--check-csv-only", str(module_dir)])
        assert run_mock.call_args.kwargs["check_mode"] == "csv"

    def test_check_po_only_flag_sets_check_mode(self, tmp_path):
        module_dir = _make_module(tmp_path)
        with mock.patch.object(mod, "run") as run_mock:
            _run_main(["--check-po-only", str(module_dir)])
        assert run_mock.call_args.kwargs["check_mode"] == "po"

    def test_no_limit_flag_forces_max_messages_none(self, tmp_path):
        module_dir = _make_module(tmp_path)
        with mock.patch.object(mod, "run") as run_mock:
            _run_main(["--no-limit", str(module_dir)])
        assert run_mock.call_args.kwargs["max_messages"] is None

    def test_explicit_max_messages_is_forwarded(self, tmp_path):
        module_dir = _make_module(tmp_path)
        with mock.patch.object(mod, "run") as run_mock:
            _run_main(["--max-messages", "5", str(module_dir)])
        assert run_mock.call_args.kwargs["max_messages"] == 5

    def test_auto_odoo_version_is_passed_as_none(self, tmp_path):
        module_dir = _make_module(tmp_path)
        with mock.patch.object(mod, "run") as run_mock:
            _run_main([str(module_dir)])
        assert run_mock.call_args.kwargs["odoo_version"] is None

    def test_explicit_odoo_version_is_forwarded(self, tmp_path):
        module_dir = _make_module(tmp_path)
        with mock.patch.object(mod, "run") as run_mock:
            _run_main(["--odoo-version", "18.0", str(module_dir)])
        assert run_mock.call_args.kwargs["odoo_version"] == "18.0"

    def test_explicit_module_path_is_used_directly(self, tmp_path):
        module_dir = _make_module(tmp_path)
        with mock.patch.object(mod, "run") as run_mock:
            _run_main([str(module_dir)])
        assert run_mock.call_args.kwargs["manifest_paths"] == [str(module_dir)]

    def test_quiet_flag_suppresses_detection_messages(self, tmp_path, capsys):
        module_dir = _make_module(tmp_path)
        with mock.patch.object(mod, "run"):
            _run_main(["-q", str(module_dir)])
        assert capsys.readouterr().out == ""

    def test_file_paths_resolve_to_their_module_and_print_detection_message(self, tmp_path, capsys):
        module_dir = _make_module(tmp_path, files={"models/x.py": ""})
        py_file = module_dir / "models" / "x.py"
        with mock.patch.object(mod, "run") as run_mock:
            _run_main([str(py_file)])
        assert run_mock.call_args.kwargs["manifest_paths"] == [str(module_dir)]
        out = capsys.readouterr().out
        assert "Detected 1 module(s) from 1 file(s)" in out
        assert "my_module" in out

    def test_staged_files_resolve_to_their_module_and_print_detection_message(self, tmp_path, capsys):
        module_dir = _make_module(tmp_path, files={"models/x.py": ""})
        py_file = module_dir / "models" / "x.py"
        with (
            mock.patch.object(mod, "_get_staged_files", return_value=[str(py_file)]),
            mock.patch.object(mod, "_detect_modules_from_staged_files", return_value=[str(module_dir)]),
            mock.patch.object(mod, "run") as run_mock,
        ):
            _run_main([])
        assert run_mock.call_args.kwargs["manifest_paths"] == [str(module_dir)]
        out = capsys.readouterr().out
        assert "Detected 1 module(s) from 1 staged file(s)" in out
        assert "my_module" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
