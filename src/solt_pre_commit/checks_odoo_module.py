# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Main orchestrator for Odoo module validations with severity support."""

import argparse
import ast
import glob
import os
import re
import sys
from collections import defaultdict

from . import (
    checks_odoo_module_csv,
    checks_odoo_module_po,
    checks_odoo_module_python,
    checks_odoo_module_xml,
    checks_odoo_module_xml_advanced,
)
from .config_loader import (
    ChangedFilesDetector,
    Severity,
    SoltConfig,
)

# Backward compatibility alias
SeverityConfig = SoltConfig

DFTL_README_TMPL_URL = "https://github.com/soltein-net/solt-pre-commit/blob/17.0/docs/README_TEMPLATE.rst"
DFTL_README_FILES = ["README.md", "README.txt", "README.rst"]
DFTL_MANIFEST_DATA_KEYS = ["data", "demo", "demo_xml", "init_xml", "test", "update_xml"]
MANIFEST_NAMES = ("__openerp__.py", "__manifest__.py")


class CheckResult:
    """Container for check results with severity."""

    def __init__(self, severity_config):
        self.severity_config = severity_config
        self.results = defaultdict(list)

    def _shorten_path(self, message):
        """Remove CI runner path prefix from error messages.

        Converts:
          /home/runner/work/solt-budget/solt-budget/module/file.py:25 Error
        To:
          solt-budget/module/file.py:25 Error
        """
        # Pattern matches: /home/runner/work/REPO_NAME/
        # This removes the CI runner prefix but keeps REPO_NAME/rest/of/path
        return re.sub(r"/home/runner/work/[^/]+/", "", message)

    def add(self, check_name, messages):
        if not messages:
            return
        if self.severity_config.should_report(check_name):
            # Shorten paths in all messages
            shortened_messages = [self._shorten_path(msg) for msg in messages]
            self.results[check_name].extend(shortened_messages)

    def add_from_dict(self, checks_errors):
        for check_name, messages in checks_errors.items():
            self.add(check_name, messages)

    def get_by_severity(self):
        by_severity = {Severity.ERROR: {}, Severity.WARNING: {}, Severity.INFO: {}}
        for check_name, messages in self.results.items():
            severity = self.severity_config.get_severity(check_name)
            by_severity[severity][check_name] = messages
        return by_severity

    def has_blocking_issues(self):
        for check_name, messages in self.results.items():
            if not messages:
                continue
            severity = self.severity_config.get_severity(check_name)
            if self.severity_config.is_blocking(severity):
                return True
        return False

    def get_counts(self):
        counts = {Severity.ERROR: 0, Severity.WARNING: 0, Severity.INFO: 0}
        for check_name, messages in self.results.items():
            severity = self.severity_config.get_severity(check_name)
            counts[severity] += len(messages)
        return counts

    def is_empty(self):
        return all(len(msgs) == 0 for msgs in self.results.values())


class ResultPrinter:
    """Pretty printer for check results."""

    # Maximum message length before truncation (increased from 120)
    MAX_MESSAGE_LENGTH = 200

    def __init__(self, use_colors=True, verbose=False, use_unicode=None, max_messages=None):
        self.use_colors = use_colors and sys.stdout.isatty()
        self.verbose = verbose
        # Auto-detect unicode support: use ASCII in CI, unicode in terminal
        if use_unicode is None:
            self.use_unicode = sys.stdout.isatty() and os.environ.get("CI") is None
        else:
            self.use_unicode = use_unicode
        # Max messages per check type (None = show all, useful for CI)
        # Default: 10 for terminal, unlimited for CI
        if max_messages is None:
            self.max_messages = None if os.environ.get("CI") else 10
        else:
            self.max_messages = max_messages

    def _get_icon(self, severity):
        """Get the appropriate icon based on environment."""
        if self.use_unicode:
            return Severity.ICONS_UNICODE.get(severity, "")
        return Severity.ICONS.get(severity, "")

    def _color(self, text, color):
        if self.use_colors:
            return f"{color}{text}{Severity.RESET}"
        return text

    def _bold(self, text):
        if self.use_colors:
            return f"{Severity.BOLD}{text}{Severity.RESET}"
        return text

    def _severity_header(self, severity, count):
        icon = self._get_icon(severity)
        color = Severity.COLORS[severity]
        name = severity.upper()
        header = f"{icon} {name}S ({count})"
        return self._color(header, color)

    def _format_check_name(self, check_name):
        return check_name.replace("_", " ").title()

    def print_results(self, check_result, module_name="", validation_scope="full"):
        if check_result.is_empty():
            return

        by_severity = check_result.get_by_severity()
        counts = check_result.get_counts()
        blocking = check_result.severity_config.blocking_severities

        print("")
        if module_name:
            print(self._bold("=" * 60))
            print(self._bold(f"MODULE: {module_name}"))
            scope_label = "changed files only" if validation_scope == "changed" else "full repository"
            print(f"   Scope: {scope_label}")
            print(self._bold("=" * 60))

        for severity in [Severity.ERROR, Severity.WARNING, Severity.INFO]:
            checks = by_severity[severity]
            if not checks:
                continue
            if severity == Severity.INFO and not self.verbose:
                continue

            count = counts[severity]
            is_blocking = severity in blocking

            print("")
            header = self._severity_header(severity, count)
            if is_blocking:
                header += self._color(" [BLOCKING]", Severity.COLORS[Severity.ERROR])
            print(header)
            print("-" * 50)

            for check_name, messages in sorted(checks.items()):
                check_display = self._format_check_name(check_name)
                print(f"\n  {self._bold(check_display)} ({len(messages)})")

                # Show all messages if max_messages is None, otherwise limit
                display_messages = messages if self.max_messages is None else messages[: self.max_messages]
                for msg in display_messages:
                    # Truncate long messages but preserve readability
                    if len(msg) > self.MAX_MESSAGE_LENGTH:
                        msg = msg[: self.MAX_MESSAGE_LENGTH - 3] + "..."
                    print(f"    - {msg}")

                if self.max_messages and len(messages) > self.max_messages:
                    remaining = len(messages) - self.max_messages
                    print(f"    ... and {remaining} more")

        print("")
        print("-" * 50)
        self._print_summary(counts, blocking)

    def _print_summary(self, counts, blocking):
        parts = []
        for severity in [Severity.ERROR, Severity.WARNING, Severity.INFO]:
            count = counts[severity]
            if count == 0 and severity == Severity.INFO:
                continue
            icon = self._get_icon(severity)
            color = Severity.COLORS[severity]
            text = f"{icon} {count} {severity}{'s' if count != 1 else ''}"
            if severity in blocking and count > 0:
                text += " (blocking)"
            parts.append(self._color(text, color))
        print(f"Summary: {' | '.join(parts)}")

    def print_blocking_notice(self, check_result):
        if not check_result.has_blocking_issues():
            return
        print("")
        print(self._color("=" * 60, Severity.COLORS[Severity.ERROR]))
        print(self._color("VALIDATION FAILED - Blocking issues found", Severity.COLORS[Severity.ERROR]))
        print(self._color("=" * 60, Severity.COLORS[Severity.ERROR]))
        print("")

    def print_success(self, module_name="", validation_scope="full"):
        scope_label = "(changed files)" if validation_scope == "changed" else "(full)"
        msg = f"{module_name}: All checks passed! {scope_label}" if module_name else "All checks passed!"
        print(self._color(msg, "\033[92m"))


def installable(method):
    """Decorator to run checks only on installable modules."""

    def inner(self):
        msg_tmpl = f"Skipped check '{method.__name__}' for '{self.manifest_path}'"
        if self.error:
            if self.verbose:
                print(f"{msg_tmpl} with error: '{self.error}'")
        elif not self.is_module_installable:
            if self.verbose:
                print(f"{msg_tmpl} is not installable")
        else:
            return method(self)

    return inner


class ChecksOdooModule:
    """Main class to run validations on Odoo modules."""

    def __init__(self, manifest_path, verbose=True, check_mode=None, severity_config=None):
        self.manifest_path = self._get_manifest_file_path(manifest_path)
        self.verbose = verbose
        self.check_mode = check_mode
        self.severity_config = severity_config or SeverityConfig()
        self.odoo_addon_path = os.path.dirname(self.manifest_path)
        self.odoo_addon_name = os.path.basename(self.odoo_addon_path)
        self.error = ""
        self.manifest_dict = self._manifest2dict()
        self.is_module_installable = self._is_installable()
        self.manifest_referenced_files = self._referenced_files_by_extension()
        self.check_result = CheckResult(self.severity_config)

        self._changed_detector = None
        if self.severity_config.use_changed_files_only():
            self._changed_detector = ChangedFilesDetector(self.severity_config.base_branch)

    @staticmethod
    def _get_manifest_file_path(original_manifest_path):
        for manifest_name in MANIFEST_NAMES:
            manifest_path = os.path.join(original_manifest_path, manifest_name)
            if os.path.isfile(manifest_path):
                return manifest_path
        return original_manifest_path

    def _manifest2dict(self):
        if os.path.basename(self.manifest_path) not in MANIFEST_NAMES:
            return {}
        if not os.path.isfile(self.manifest_path):
            return {}
        if not os.path.isfile(os.path.join(self.odoo_addon_path, "__init__.py")):
            return {}
        with open(self.manifest_path, "r", encoding="UTF-8") as f_manifest:
            try:
                return ast.literal_eval(f_manifest.read())
            except Exception as err:
                self.error = f"Manifest {self.manifest_path} with error {err}"
        return {}

    def _is_installable(self):
        return self.manifest_dict and self.manifest_dict.get("installable", True)

    def _referenced_files_by_extension(self):
        ext_referenced_files = defaultdict(list)

        for data_section in DFTL_MANIFEST_DATA_KEYS:
            for fname in self.manifest_dict.get(data_section) or []:
                full_path = os.path.realpath(os.path.join(self.odoo_addon_path, os.path.normpath(fname)))
                if self.severity_config.is_path_excluded(fname):
                    continue

                ext = os.path.splitext(fname)[1].lower()
                ext_referenced_files[ext].append(
                    {
                        "filename": full_path,
                        "filename_short": os.path.normpath(fname),
                        "data_section": data_section,
                    }
                )

        fnames = glob.glob(os.path.join(self.odoo_addon_path, "i18n*", "*.po")) + glob.glob(
            os.path.join(self.odoo_addon_path, "i18n*", "*.pot")
        )
        for fname in fnames:
            if self.severity_config.is_path_excluded(fname):
                continue
            ext = os.path.splitext(fname)[1].lower()
            ext_referenced_files[ext].append(
                {
                    "filename": os.path.realpath(fname),
                    "filename_short": os.path.normpath(fname),
                    "data_section": "default",
                }
            )

        for root, dirs, files in os.walk(self.odoo_addon_path):
            dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", "node_modules", "static", "lib"}]
            for fname in files:
                if fname.endswith(".py"):
                    full_path = os.path.join(str(root), fname)
                    addon_path = str(self.odoo_addon_path)
                    rel_path = os.path.relpath(full_path, addon_path)

                    if self.severity_config.is_path_excluded(rel_path):
                        continue

                    ext_referenced_files[".py"].append(
                        {
                            "filename": os.path.realpath(full_path),
                            "filename_short": rel_path,
                            "data_section": "python",
                        }
                    )

        return ext_referenced_files

    def _get_files_to_validate(self, extension):
        """Get files to validate based on scope configuration."""
        all_files = self.manifest_referenced_files.get(extension, [])
        if not all_files:
            return []
        if self._changed_detector:
            return self._changed_detector.filter_changed_files(all_files)
        return all_files

    def _should_run_check(self, check_type):
        if self.check_mode is None:
            return True
        return self.check_mode == check_type

    def check_manifest(self):
        if not self._should_run_check("manifest"):
            return
        if not self.manifest_dict:
            self.check_result.add(
                "manifest_syntax_error",
                [f"{self.manifest_path} could not be loaded {self.error}"],
            )

    @installable
    def check_missing_readme(self):
        if not self._should_run_check("manifest"):
            return
        for readme_name in DFTL_README_FILES:
            readme_path = os.path.join(self.odoo_addon_path, readme_name)
            if os.path.isfile(readme_path):
                return
        self.check_result.add(
            "missing_readme",
            [f"{self.odoo_addon_path} missing README. Template: {DFTL_README_TMPL_URL}"],
        )

    @installable
    def check_xml(self):
        if not self._should_run_check("xml"):
            return
        manifest_datas = self._get_files_to_validate(".xml")
        if not manifest_datas:
            return

        checks_obj = checks_odoo_module_xml.ChecksOdooModuleXML(manifest_datas, self.odoo_addon_name)
        for check_meth in self._get_check_methods(checks_obj):
            check_meth()
        self.check_result.add_from_dict(checks_obj.checks_errors)

    @installable
    def check_xml_advanced(self):
        if not self._should_run_check("xml"):
            return
        manifest_datas = self._get_files_to_validate(".xml")
        if not manifest_datas:
            return

        checks_obj = checks_odoo_module_xml_advanced.ChecksOdooModuleXMLAdvanced(manifest_datas, self.odoo_addon_name)
        for check_meth in self._get_check_methods(checks_obj):
            check_meth()
        self.check_result.add_from_dict(checks_obj.checks_errors)

    @installable
    def check_csv(self):
        if not self._should_run_check("csv"):
            return
        manifest_datas = self._get_files_to_validate(".csv")
        if not manifest_datas:
            return

        checks_obj = checks_odoo_module_csv.ChecksOdooModuleCSV(manifest_datas, self.odoo_addon_name)
        for check_meth in self._get_check_methods(checks_obj):
            check_meth()
        self.check_result.add_from_dict(checks_obj.checks_errors)

    @installable
    def check_po(self):
        if not self._should_run_check("po"):
            return
        manifest_datas = self._get_files_to_validate(".po") + self._get_files_to_validate(".pot")
        if not manifest_datas:
            return

        checks_obj = checks_odoo_module_po.ChecksOdooModulePO(manifest_datas, self.odoo_addon_name)
        for check_meth in self._get_check_methods(checks_obj):
            check_meth()
        self.check_result.add_from_dict(checks_obj.checks_errors)

    @installable
    def check_python(self):
        """Run Python validations and store analysis data for coverage report."""
        if not self._should_run_check("python"):
            return
        manifest_datas = self._get_files_to_validate(".py")
        if not manifest_datas:
            return

        checks_obj = checks_odoo_module_python.ChecksOdooModulePython(
            manifest_datas,
            self.odoo_addon_name,
            config=self.severity_config,
        )
        for check_meth in self._get_check_methods(checks_obj):
            check_meth()
        self.check_result.add_from_dict(checks_obj.checks_errors)

        # Store analysis data for coverage report
        for file_data in self.manifest_referenced_files.get(".py", []):
            filename = file_data["filename"]
            for manifest_data in manifest_datas:
                if manifest_data["filename"] == filename:
                    file_data["models"] = manifest_data.get("models", {})
                    file_data["fields"] = manifest_data.get("fields", {})
                    file_data["methods"] = manifest_data.get("methods", {})
                    break

    def collect_coverage_data(self):
        """Collect coverage data from ALL Python files (ignores validation_scope).

        This method is for generating global repository metrics without blocking.
        It does NOT add errors to check_result, only collects metadata.
        """
        all_py_files = self.manifest_referenced_files.get(".py", [])
        if not all_py_files:
            return

        # Parse all files for coverage data only (no error reporting)
        # The constructor already parses files and populates models/fields/methods
        _parser = checks_odoo_module_python.ChecksOdooModulePython(
            all_py_files,
            self.odoo_addon_name,
            config=self.severity_config,
        )
        # _parser is used only for side effects (populating all_py_files dicts)
        del _parser  # Explicitly delete to avoid unused variable warning

        # Store coverage data in ALL files
        for file_data in all_py_files:
            filename = file_data["filename"]
            for manifest_data in all_py_files:
                if manifest_data["filename"] == filename:
                    file_data["models"] = manifest_data.get("models", {})
                    file_data["fields"] = manifest_data.get("fields", {})
                    file_data["methods"] = manifest_data.get("methods", {})
                    break

    @staticmethod
    def _get_check_methods(obj):
        for attr in dir(obj):
            if callable(getattr(obj, attr)) and attr.startswith("check_"):
                yield getattr(obj, attr)

    @staticmethod
    def getattr_checks(obj_or_class=None):
        if obj_or_class is None:
            obj_or_class = ChecksOdooModule
        for attr in dir(obj_or_class):
            if callable(getattr(obj_or_class, attr)) and attr.startswith("check_"):
                yield getattr(obj_or_class, attr)


def _print_global_coverage_metrics(checks_objects, severity_config):
    """Print global coverage metrics for the repository.

    These metrics are informational and do NOT affect the exit code.
    They show coverage of the entire repository, not just changed files.
    """
    total_models = 0
    total_fields = 0
    total_methods = 0
    fields_with_string = 0
    fields_with_help = 0
    methods_with_docstring = 0
    public_methods = 0

    # Skip list from config
    skip_string = severity_config.skip_string_fields
    skip_help = severity_config.skip_help_fields
    skip_docstring = severity_config.skip_docstring_methods

    # Separate counters for fields that actually need string/help
    fields_needing_string = 0
    fields_needing_help = 0

    for _module_name, checks_obj in checks_objects:
        for file_data in checks_obj.manifest_referenced_files.get(".py", []):
            models = file_data.get("models", {})
            fields = file_data.get("fields", {})
            methods = file_data.get("methods", {})

            for _class_name, model_info in models.items():
                if model_info.get("is_odoo_model"):
                    total_models += 1

            for _class_name, field_list in fields.items():
                for fld in field_list:
                    field_name = fld.get("name", "")
                    # Skip private fields
                    if field_name.startswith("_"):
                        continue
                    # Skip related fields (they inherit attributes from source)
                    if fld.get("related"):
                        continue

                    total_fields += 1

                    # Only count fields that NEED string (not in skip list)
                    if field_name not in skip_string:
                        fields_needing_string += 1
                        if fld.get("string"):
                            fields_with_string += 1

                    # Only count fields that NEED help (not in skip list)
                    if field_name not in skip_help:
                        fields_needing_help += 1
                        if fld.get("help"):
                            fields_with_help += 1

            for _class_name, method_list in methods.items():
                for meth in method_list:
                    name = meth.get("name", "")
                    if name.startswith("_") and not name.startswith("__"):
                        continue  # Skip private
                    if name in skip_docstring:
                        continue

                    total_methods += 1
                    public_methods += 1

                    if meth.get("has_docstring"):
                        methods_with_docstring += 1

    if fields_needing_string == 0 and fields_needing_help == 0 and public_methods == 0:
        return  # No data to show

    # Calculate percentages using fields_needing_* instead of total_fields
    string_pct = (fields_with_string / fields_needing_string * 100) if fields_needing_string > 0 else 100
    help_pct = (fields_with_help / fields_needing_help * 100) if fields_needing_help > 0 else 100
    docstring_pct = (methods_with_docstring / public_methods * 100) if public_methods > 0 else 100

    # Get thresholds from config (or defaults)
    docstring_threshold = 80
    string_threshold = 90
    help_threshold = 50

    print("")
    print("-" * 60)
    print("REPOSITORY COVERAGE (Informational)")
    print("-" * 60)
    print(f"  Modules analyzed: {len(checks_objects)}")
    print(f"  Models: {total_models} | Total Fields: {total_fields} | Public Methods: {public_methods}")
    print(f"  Fields needing string: {fields_needing_string} | Fields needing help: {fields_needing_help}")
    print("")
    print(
        f"  Docstrings:          {docstring_pct:5.1f}%  ({methods_with_docstring}/{public_methods})  "
        f"{'PASS' if docstring_pct >= docstring_threshold else 'WARN'} (goal: >={docstring_threshold}%)"
    )
    print(
        f"  Fields with string:  {string_pct:5.1f}%  ({fields_with_string}/{fields_needing_string})  "
        f"{'PASS' if string_pct >= string_threshold else 'WARN'} (goal: >={string_threshold}%)"
    )
    print(
        f"  Fields with help:    {help_pct:5.1f}%  ({fields_with_help}/{fields_needing_help})  "
        f"{'PASS' if help_pct >= help_threshold else 'WARN'} (goal: >={help_threshold}%)"
    )
    print("-" * 60)
    print("These metrics are informational and do NOT block validation.")
    # Machine-readable output for CI parsing (do not modify format)
    # Output fields_needing_* as totals instead of total_fields
    print(
        f"METRICS:docstring_cov={docstring_pct:.1f},"
        f"docstring_documented={methods_with_docstring},"
        f"docstring_total={public_methods},"
        f"string_cov={string_pct:.1f},"
        f"string_documented={fields_with_string},"
        f"string_total={fields_needing_string},"
        f"help_cov={help_pct:.1f},"
        f"help_documented={fields_with_help},"
        f"help_total={fields_needing_help},"
        f"models={total_models}"
    )
    print("")


def run(
    manifest_paths=None,
    verbose=True,
    do_exit=True,
    check_mode=None,
    config_path=None,
    show_info=False,
    force_scope=None,
    json_report=None,
    show_coverage=True,
):
    """Main entry point."""
    import time

    start_time = time.time()

    if manifest_paths is None:
        manifest_paths = []

    severity_config = SeverityConfig(config_path)

    if force_scope:
        severity_config.validation_scope = force_scope

    printer = ResultPrinter(use_colors=True, verbose=show_info)

    all_results = []
    checks_objects = []
    has_blocking = False

    for manifest_path in manifest_paths:
        checks_obj = ChecksOdooModule(
            os.path.realpath(manifest_path),
            verbose=verbose,
            check_mode=check_mode,
            severity_config=severity_config,
        )

        for check in checks_obj.getattr_checks():
            check(checks_obj)

        # Collect coverage data from ALL files (for metrics display)
        checks_obj.collect_coverage_data()

        checks_objects.append((checks_obj.odoo_addon_name, checks_obj))

        if not checks_obj.check_result.is_empty():
            all_results.append((checks_obj.odoo_addon_name, checks_obj.check_result))
            if checks_obj.check_result.has_blocking_issues():
                has_blocking = True

            if verbose:
                printer.print_results(
                    checks_obj.check_result,
                    checks_obj.odoo_addon_name,
                    severity_config.validation_scope,
                )
        elif verbose:
            printer.print_success(checks_obj.odoo_addon_name, severity_config.validation_scope)

    # Show global coverage metrics
    if verbose and show_coverage:
        _print_global_coverage_metrics(checks_objects, severity_config)
    # Calculate elapsed time
    elapsed_time = time.time() - start_time

    if len(manifest_paths) > 1 and verbose:
        print("")
        print("=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)
        scope_label = "changed files only" if severity_config.validation_scope == "changed" else "full repository"
        print(f"  Validation scope: {scope_label}")

        total_counts = {Severity.ERROR: 0, Severity.WARNING: 0, Severity.INFO: 0}
        for _module_name, result in all_results:
            counts = result.get_counts()
            for sev, count in counts.items():
                total_counts[sev] += count

        print(f"  Modules checked: {len(manifest_paths)}")
        print(f"  Modules with issues: {len(all_results)}")
        print(f"  Errors: {total_counts[Severity.ERROR]}")
        print(f"  Warnings: {total_counts[Severity.WARNING]}")
        print(f"  Info: {total_counts[Severity.INFO]}")
        print(f"  Elapsed time: {elapsed_time:.2f}s")

    if has_blocking and verbose:
        if all_results:
            printer.print_blocking_notice(all_results[0][1])

    # Generate JSON coverage report if requested
    if json_report:
        try:
            from . import doc_coverage

            report = doc_coverage.build_coverage_report(checks_objects)
            report.save(json_report)
            if verbose:
                print(f"\nCoverage report saved to: {json_report}")
        except Exception as e:
            if verbose:
                print(f"\nFailed to generate coverage report: {e}")

    exit_code = 1 if has_blocking else 0

    if do_exit:
        sys.exit(exit_code)

    return all_results, exit_code


def main():
    """Console entry point."""
    parser = argparse.ArgumentParser(description="Solt Pre-commit: Odoo module validation hooks")
    parser.add_argument("paths", nargs="*", help="Paths to Odoo modules to validate")
    parser.add_argument("--check-xml-only", action="store_true", help="Run only XML checks")
    parser.add_argument("--check-csv-only", action="store_true", help="Run only CSV checks")
    parser.add_argument("--check-po-only", action="store_true", help="Run only PO/POT checks")
    parser.add_argument("--check-python-only", action="store_true", help="Run only Python checks")
    parser.add_argument("--config", default=None, help="Path to config file")
    parser.add_argument("--show-info", action="store_true", help="Show info-level issues")
    parser.add_argument(
        "--scope",
        choices=["changed", "full"],
        default=None,
        help="Override validation scope",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output")
    parser.add_argument(
        "--json-report",
        default=None,
        help="Generate JSON coverage report to specified file path",
    )

    args = parser.parse_args()

    check_mode = None
    if args.check_xml_only:
        check_mode = "xml"
    elif args.check_csv_only:
        check_mode = "csv"
    elif args.check_po_only:
        check_mode = "po"
    elif args.check_python_only:
        check_mode = "python"

    paths = args.paths or ["."]

    return run(
        manifest_paths=paths,
        verbose=not args.quiet,
        check_mode=check_mode,
        config_path=args.config,
        show_info=args.show_info,
        force_scope=args.scope,
        json_report=args.json_report,
    )


if __name__ == "__main__":
    main()
