# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Main orchestrator for Odoo module validations with severity support.

Supports Odoo versions: 17.0, 18.0, 19.0, and future versions (20.0+)
Auto-detects version from manifest or branch name.
"""

import argparse
import ast
import glob
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from . import (
    checks_odoo_module_csv,
    checks_odoo_module_po,
    checks_odoo_module_python,
    checks_odoo_module_xml,
    checks_odoo_module_xml_advanced,
)
from .config_loader import (
    MINIMUM_SUPPORTED_VERSION,
    SUPPORTED_ODOO_VERSIONS,
    OdooVersionDetector,
    Severity,
    SoltConfig,
)

# Backward compatibility alias
SeverityConfig = SoltConfig

DFTL_README_TMPL_URL = "https://github.com/soltein-net/solt-pre-commit/blob/main/docs/README_TEMPLATE.rst"
DFTL_README_FILES = ["README.md", "README.txt", "README.rst"]
DFTL_MANIFEST_DATA_KEYS = ["data", "demo", "demo_xml", "init_xml", "test", "update_xml"]
MANIFEST_NAMES = ("__openerp__.py", "__manifest__.py")


# =============================================================================
# HELPER FUNCTIONS - Detect modules from files (for pre-commit compatibility)
# =============================================================================


def _get_staged_files():
    """Get list of staged files from git.

    Returns:
        List of staged file paths, or empty list if not in a git repo
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def _find_module_from_file(filepath):
    """Find the Odoo module directory from a file path."""
    path = Path(filepath).resolve()
    if path.is_file():
        path = path.parent

    for _ in range(10):
        for manifest_name in MANIFEST_NAMES:
            if (path / manifest_name).exists():
                return str(path)
        parent = path.parent
        if parent == path:
            break
        path = parent
    return None


def _detect_modules_from_paths(paths):
    """Detect unique Odoo modules from a list of paths."""
    modules = set()
    direct_modules = []

    for path in paths:
        if not path:
            continue
        path_obj = Path(path)

        if path_obj.is_dir():
            if any((path_obj / m).exists() for m in MANIFEST_NAMES):
                direct_modules.append(str(path_obj.resolve()))
                continue

        module_path = _find_module_from_file(path)
        if module_path:
            modules.add(module_path)

    if direct_modules:
        return direct_modules
    return sorted(modules) if modules else []


def _is_file_list(paths):
    """Check if paths are individual files or module directories."""
    if not paths:
        return False

    file_extensions = {".py", ".xml", ".csv", ".po", ".pot", ".yml", ".yaml", ".json", ".md", ".rst", ".txt"}
    for path in paths:
        ext = Path(path).suffix.lower()
        if ext in file_extensions:
            return True
        if Path(path).is_file():
            return True
    return False


def _detect_modules_from_staged_files():
    """Detect Odoo modules from git staged files."""
    staged_files = _get_staged_files()
    if not staged_files:
        return None

    relevant_extensions = {".py", ".xml", ".csv", ".po", ".pot"}
    relevant_files = [
        f
        for f in staged_files
        if Path(f).suffix.lower() in relevant_extensions or "__manifest__" in f or "__openerp__" in f
    ]

    if not relevant_files:
        return None

    return _detect_modules_from_paths(relevant_files)


# =============================================================================


class CheckResult:
    """Container for check results with severity."""

    def __init__(self, severity_config):
        self.severity_config = severity_config
        self.results = defaultdict(list)

    def _shorten_path(self, message):
        return re.sub(r"/home/runner/work/[^/]+/", "", message)

    def add(self, check_name, messages):
        if not messages:
            return
        if self.severity_config.should_report(check_name):
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

    def has_errors_or_warnings(self):
        counts = self.get_counts()
        return counts[Severity.ERROR] > 0 or counts[Severity.WARNING] > 0

    def is_empty(self):
        return all(len(msgs) == 0 for msgs in self.results.values())


class ResultPrinter:
    """Pretty printer for check results."""

    MAX_MESSAGE_LENGTH = 200

    def __init__(self, use_colors=True, verbose=False, use_unicode=None, max_messages=None):
        self.use_colors = use_colors and sys.stdout.isatty()
        self.verbose = verbose
        if use_unicode is None:
            self.use_unicode = sys.stdout.isatty() and os.environ.get("CI") is None
        else:
            self.use_unicode = use_unicode
        if max_messages is None:
            self.max_messages = None if os.environ.get("CI") else 10
        else:
            self.max_messages = max_messages

    def _get_icon(self, severity):
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

                display_messages = messages if self.max_messages is None else messages[: self.max_messages]
                for msg in display_messages:
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
    """Main class to run validations on Odoo modules.

    Supports Odoo versions: 17.0, 18.0, 19.0, and future versions (X.0 where X >= 17)
    Auto-detects version from module manifest or allows explicit override.
    """

    def __init__(self, manifest_path, verbose=True, check_mode=None, severity_config=None, odoo_version=None):
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

        # Odoo version detection/configuration
        if odoo_version:
            self.odoo_version = OdooVersionDetector.normalize_version(odoo_version)
        else:
            self.odoo_version = self._detect_odoo_version()

        self._changed_detector = None
        if self.severity_config.use_changed_files_only():
            self._changed_detector = self.severity_config.changed_detector

    def _detect_odoo_version(self) -> str:
        """Detect Odoo version from manifest or config.

        Supports both explicit SUPPORTED_ODOO_VERSIONS and future versions (X.0 where X >= 17)
        """
        # Try from manifest first
        version = self.manifest_dict.get("version", "")
        if version:
            parts = version.split(".")
            if len(parts) >= 2:
                odoo_version = f"{parts[0]}.{parts[1]}"
                # Check explicitly supported versions
                if odoo_version in SUPPORTED_ODOO_VERSIONS:
                    return odoo_version
                # Also accept future versions (X.0 where X >= MINIMUM_SUPPORTED_VERSION)
                try:
                    major = int(parts[0])
                    if major >= MINIMUM_SUPPORTED_VERSION and parts[1] == "0":
                        return odoo_version
                except ValueError:
                    pass

        # Fall back to config
        return self.severity_config.get_odoo_version(self.odoo_addon_path)

    def has_changed_files(self) -> bool:
        if not self._changed_detector:
            return True

        for ext in self.manifest_referenced_files:
            files = self._get_files_to_validate(ext)
            if files:
                return True
        return False

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

        checks_obj = checks_odoo_module_xml.ChecksOdooModuleXML(
            manifest_datas, self.odoo_addon_name, odoo_version=self.odoo_version
        )
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

        checks_obj = checks_odoo_module_xml_advanced.ChecksOdooModuleXMLAdvanced(
            manifest_datas, self.odoo_addon_name, odoo_version=self.odoo_version
        )
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
            odoo_version=self.odoo_version,
        )
        for check_meth in self._get_check_methods(checks_obj):
            check_meth()
        self.check_result.add_from_dict(checks_obj.checks_errors)

        for file_data in self.manifest_referenced_files.get(".py", []):
            filename = file_data["filename"]
            for manifest_data in manifest_datas:
                if manifest_data["filename"] == filename:
                    file_data["models"] = manifest_data.get("models", {})
                    file_data["fields"] = manifest_data.get("fields", {})
                    file_data["methods"] = manifest_data.get("methods", {})
                    break

    def collect_coverage_data(self):
        """Collect coverage data from ALL Python files (ignores validation_scope)."""
        all_py_files = self.manifest_referenced_files.get(".py", [])
        if not all_py_files:
            return

        _parser = checks_odoo_module_python.ChecksOdooModulePython(
            all_py_files,
            self.odoo_addon_name,
            config=self.severity_config,
            odoo_version=self.odoo_version,
        )
        del _parser

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
    """Print global coverage metrics for the repository."""
    total_models = 0
    total_fields = 0
    total_methods = 0
    fields_with_string = 0
    fields_with_help = 0
    methods_with_docstring = 0
    public_methods = 0

    skip_string = severity_config.skip_string_fields
    skip_help = severity_config.skip_help_fields
    skip_docstring = severity_config.skip_docstring_methods

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
                    if field_name.startswith("_"):
                        continue
                    if fld.get("related"):
                        continue

                    total_fields += 1

                    if field_name not in skip_string:
                        fields_needing_string += 1
                        if fld.get("string"):
                            fields_with_string += 1

                    if field_name not in skip_help:
                        fields_needing_help += 1
                        if fld.get("help"):
                            fields_with_help += 1

            for _class_name, method_list in methods.items():
                for meth in method_list:
                    name = meth.get("name", "")
                    if name.startswith("_") and not name.startswith("__"):
                        continue
                    if name in skip_docstring:
                        continue

                    total_methods += 1
                    public_methods += 1

                    if meth.get("has_docstring"):
                        methods_with_docstring += 1

    if fields_needing_string == 0 and fields_needing_help == 0 and public_methods == 0:
        return

    string_pct = (fields_with_string / fields_needing_string * 100) if fields_needing_string > 0 else 100
    help_pct = (fields_with_help / fields_needing_help * 100) if fields_needing_help > 0 else 100
    docstring_pct = (methods_with_docstring / public_methods * 100) if public_methods > 0 else 100

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
    show_all_modules=False,
    odoo_version=None,
    max_messages=None,
):
    """Main entry point.

    Args:
        manifest_paths: List of paths to Odoo modules
        verbose: Show detailed output
        do_exit: Exit with code after validation
        check_mode: Run only specific checks (xml, csv, po, python)
        config_path: Path to .solt-hooks.yaml
        show_info: Show info-level issues
        force_scope: Override validation scope (changed, full)
        json_report: Path to save JSON coverage report
        show_coverage: Show coverage metrics
        show_all_modules: Show all modules even if no issues
        odoo_version: Odoo version override (17.0, 18.0, 19.0)
        max_messages: Maximum messages per check (None = use default, which is 10 in terminal or unlimited in CI)

    Returns:
        Tuple of (all_results, exit_code)
    """
    import time

    start_time = time.time()

    if manifest_paths is None:
        manifest_paths = []

    severity_config = SeverityConfig(config_path)

    if force_scope:
        severity_config.validation_scope = force_scope

    # Set Odoo version if provided
    if odoo_version:
        severity_config.set_odoo_version(odoo_version)
        detected_version = OdooVersionDetector.normalize_version(odoo_version)
    else:
        detected_version = None

    printer = ResultPrinter(use_colors=True, verbose=show_info, max_messages=max_messages)

    all_results = []
    checks_objects = []
    has_blocking = False
    versions_found = set()

    for manifest_path in manifest_paths:
        checks_obj = ChecksOdooModule(
            os.path.realpath(manifest_path),
            verbose=verbose,
            check_mode=check_mode,
            severity_config=severity_config,
            odoo_version=detected_version,
        )

        versions_found.add(checks_obj.odoo_version)

        for check in checks_obj.getattr_checks():
            check(checks_obj)

        checks_obj.collect_coverage_data()
        checks_objects.append((checks_obj.odoo_addon_name, checks_obj))

        if not checks_obj.check_result.is_empty():
            all_results.append((checks_obj.odoo_addon_name, checks_obj.check_result))
            if checks_obj.check_result.has_blocking_issues():
                has_blocking = True

        if verbose:
            if show_all_modules:
                if not checks_obj.check_result.is_empty():
                    printer.print_results(
                        checks_obj.check_result,
                        checks_obj.odoo_addon_name,
                        severity_config.validation_scope,
                    )
                else:
                    printer.print_success(checks_obj.odoo_addon_name, severity_config.validation_scope)
            elif not checks_obj.check_result.is_empty():
                printer.print_results(
                    checks_obj.check_result,
                    checks_obj.odoo_addon_name,
                    severity_config.validation_scope,
                )

    if verbose and show_coverage:
        _print_global_coverage_metrics(checks_objects, severity_config)

    elapsed_time = time.time() - start_time

    if len(manifest_paths) > 1 and verbose:
        print("")
        print("=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)
        scope_label = "changed files only" if severity_config.validation_scope == "changed" else "full repository"
        print(f"  Validation scope: {scope_label}")
        if versions_found:
            print(f"  Odoo version(s): {', '.join(sorted(versions_found))}")

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
    parser = argparse.ArgumentParser(
        description="Solt Pre-commit: Odoo module validation hooks",
        epilog=f"Supported Odoo versions: {', '.join(SUPPORTED_ODOO_VERSIONS)}",
    )
    parser.add_argument("paths", nargs="*", help="Paths to Odoo modules or files to validate")
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
    parser.add_argument(
        "--odoo-version",
        choices=SUPPORTED_ODOO_VERSIONS + ["auto"],
        default="auto",
        help="Odoo version for validation (default: auto-detect from manifest)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output")
    parser.add_argument(
        "--no-limit",
        action="store_true",
        help="Show all errors without limit (default: 10 in terminal, unlimited in CI)",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=None,
        help="Maximum number of messages to show per check (default: 10 in terminal, unlimited in CI)",
    )
    parser.add_argument(
        "--json-report",
        default=None,
        help="Generate JSON coverage report to specified file path",
    )
    parser.add_argument(
        "--show-all-modules",
        action="store_true",
        help="Show all modules even if they have no issues",
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

    # Handle Odoo version
    odoo_version = None if args.odoo_version == "auto" else args.odoo_version

    # Handle max messages limit
    if args.no_limit:
        max_messages = None  # No limit
    elif args.max_messages is not None:
        max_messages = args.max_messages
    else:
        max_messages = None  # Will use default (10 in terminal, None in CI)

    paths = args.paths or []

    # =========================================================================
    # DETECT MODULES AUTOMATICALLY
    # =========================================================================
    if paths:
        if _is_file_list(paths):
            detected_modules = _detect_modules_from_paths(paths)
            if detected_modules:
                if not args.quiet:
                    print(f"[solt-check-odoo] Detected {len(detected_modules)} module(s) from {len(paths)} file(s)")
                    for mod in detected_modules:
                        print(f"  -> {Path(mod).name}")
                paths = detected_modules
            else:
                if not args.quiet:
                    print("[solt-check-odoo] No Odoo modules detected from provided files")
                sys.exit(0)
    else:
        # No paths - detect from staged files (pre-commit with pass_filenames: false)
        detected_modules = _detect_modules_from_staged_files()
        if detected_modules:
            if not args.quiet:
                staged_count = len(_get_staged_files())
                print(
                    f"[solt-check-odoo] Detected {len(detected_modules)} module(s) from {staged_count} staged file(s)"
                )
                for mod in detected_modules:
                    print(f"  -> {Path(mod).name}")
            paths = detected_modules
        else:
            # Fallback to current directory
            paths = ["."]
    # =========================================================================

    # Show version being used
    if not args.quiet and odoo_version:
        print(f"[solt-check-odoo] Using Odoo version: {odoo_version}")

    return run(
        manifest_paths=paths,
        verbose=not args.quiet,
        check_mode=check_mode,
        config_path=args.config,
        show_info=args.show_info,
        force_scope=args.scope,
        json_report=args.json_report,
        show_all_modules=args.show_all_modules,
        odoo_version=odoo_version,
        max_messages=max_messages,
    )


if __name__ == "__main__":
    main()
