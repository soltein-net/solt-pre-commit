# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Configuration loader for solt-pre-commit.

Loads configuration from .solt-hooks.yaml with fallback to defaults.
Supports validation_scope for changed-only or full repository validation.
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
from pathlib import Path

import yaml


class Severity:
    """Severity levels for checks."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    PRIORITY = {ERROR: 3, WARNING: 2, INFO: 1}
    COLORS = {ERROR: "\033[91m", WARNING: "\033[93m", INFO: "\033[94m"}
    RESET = "\033[0m"
    BOLD = "\033[1m"
    ICONS = {ERROR: "❌", WARNING: "⚠️ ", INFO: "ℹ️ "}


# Default severity for each check
DEFAULT_SEVERITY: dict[str, str] = {
    # Syntax errors - always block
    "xml_syntax_error": Severity.ERROR,
    "csv_syntax_error": Severity.ERROR,
    "python_syntax_error": Severity.ERROR,
    "manifest_syntax_error": Severity.ERROR,
    "po_syntax_error": Severity.ERROR,
    # Duplicates - block
    "xml_duplicate_record_id": Severity.ERROR,
    "csv_duplicate_record_id": Severity.ERROR,
    "po_duplicate_message_definition": Severity.ERROR,
    "xml_duplicate_fields": Severity.ERROR,
    # Odoo runtime warnings - block
    "python_duplicate_field_label": Severity.ERROR,
    "python_inconsistent_compute_sudo": Severity.ERROR,
    "python_tracking_without_mail_thread": Severity.ERROR,
    "python_selection_on_related": Severity.ERROR,
    "xml_deprecated_active_id_usage": Severity.ERROR,
    "xml_alert_missing_role": Severity.ERROR,
    # Dangerous patterns - warning
    "xml_view_dangerous_replace_low_priority": Severity.WARNING,
    "xml_create_user_wo_reset_password": Severity.WARNING,
    "xml_dangerous_filter_wo_user": Severity.WARNING,
    "xml_hardcoded_id": Severity.WARNING,
    "xml_duplicate_view_priority": Severity.WARNING,
    # Deprecations - warning
    "xml_deprecated_tree_attribute": Severity.WARNING,
    "xml_deprecated_data_node": Severity.WARNING,
    "xml_deprecated_openerp_xml_node": Severity.WARNING,
    "xml_deprecated_t_raw": Severity.WARNING,
    "xml_deprecated_qweb_directive": Severity.WARNING,
    "xml_button_without_type": Severity.WARNING,
    # Code quality - warning/info
    "python_field_missing_string": Severity.WARNING,
    "python_field_missing_help": Severity.WARNING,
    "python_method_missing_docstring": Severity.WARNING,
    "python_docstring_too_short": Severity.INFO,
    "python_docstring_uninformative": Severity.INFO,
    # PO quality
    "po_requires_module": Severity.WARNING,
    "po_python_parse_printf": Severity.WARNING,
    "po_python_parse_format": Severity.WARNING,
    # Other
    "xml_redundant_module_name": Severity.INFO,
    "xml_not_valid_char_link": Severity.WARNING,
    "missing_readme": Severity.INFO,
}

# Default skip lists
DEFAULT_SKIP_STRING_FIELDS: set[str] = {
    "active",
    "name",
    "sequence",
    "company_id",
    "currency_id",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
    "message_ids",
    "message_follower_ids",
    "activity_ids",
}

DEFAULT_SKIP_HELP_FIELDS: set[str] = {
    "active",
    "name",
    "sequence",
    "company_id",
    "currency_id",
}

DEFAULT_SKIP_DOCSTRING_METHODS: set[str] = {
    "__init__",
    "__str__",
    "__repr__",
    "__len__",
    "__bool__",
    "__getitem__",
    "__setitem__",
    "__delitem__",
    "__iter__",
    "__next__",
    "__contains__",
    "__call__",
    "__enter__",
    "__exit__",
    "__eq__",
    "__ne__",
    "__lt__",
    "__le__",
    "__gt__",
    "__ge__",
    "__hash__",
    "__format__",
}

DEFAULT_EXCLUDE_PATHS: list[str] = [
    "**/migrations/**",
    "**/tests/**",
    "**/static/**",
    "**/__pycache__/**",
    "**/node_modules/**",
]


class ChangedFilesDetector:
    """Detects which files have changed for PR/commit validation."""

    def __init__(self, base_branch: str | None = None):
        self.base_branch = base_branch or self._detect_base_branch()
        self._changed_files: set[str] | None = None

    def _detect_base_branch(self) -> str:
        """Auto-detect the base branch."""
        candidates = ["main", "master", "develop"]
        for branch in candidates:
            try:
                subprocess.run(
                    ["git", "rev-parse", "--verify", f"origin/{branch}"],
                    capture_output=True,
                    check=True,
                )
                return f"origin/{branch}"
            except subprocess.CalledProcessError:
                continue
        return "HEAD~1"

    def get_changed_files(self) -> set[str]:
        """Get set of changed files compared to base branch."""
        if self._changed_files is not None:
            return self._changed_files

        self._changed_files = set()

        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=ACMR", self.base_branch],
                capture_output=True,
                text=True,
                check=True,
            )
            files = result.stdout.strip().split("\n")
            self._changed_files = {os.path.realpath(f) for f in files if f}
        except subprocess.CalledProcessError:
            try:
                result = subprocess.run(
                    ["git", "diff", "--name-only", "--cached", "--diff-filter=ACMR"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                files = result.stdout.strip().split("\n")
                self._changed_files = {os.path.realpath(f) for f in files if f}
            except subprocess.CalledProcessError:
                pass

        return self._changed_files

    def is_file_changed(self, filepath: str) -> bool:
        """Check if a specific file has changed."""
        return os.path.realpath(filepath) in self.get_changed_files()

    def filter_changed_files(self, files: list[dict]) -> list[dict]:
        """Filter a list of file dicts to only those that changed."""
        changed = self.get_changed_files()
        return [f for f in files if os.path.realpath(f["filename"]) in changed]


class SoltConfig:
    """Configuration manager for solt-pre-commit."""

    CONFIG_FILES = [".solt-hooks.yaml", ".solt-hooks.yml", "solt-hooks.yaml"]

    def __init__(self, config_path: str | None = None):
        self.config = self._load_config(config_path)
        self._init_settings()

    def _load_config(self, config_path: str | None = None) -> dict:
        """Load configuration from .solt-hooks.yaml."""
        if config_path:
            search_paths = [Path(config_path)]
        else:
            current = Path.cwd()
            search_paths = []
            for _ in range(5):
                for config_name in self.CONFIG_FILES:
                    search_paths.append(current / config_name)
                current = current.parent

        for path in search_paths:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return yaml.safe_load(f) or {}
                except (yaml.YAMLError, OSError):
                    pass
        return {}

    def _init_settings(self):
        """Initialize all settings from config."""
        # Validation scope
        self.validation_scope: str = self.config.get("validation_scope", "changed")
        self.base_branch: str | None = self.config.get("base_branch")

        # Severity settings
        self.severity_map: dict[str, str] = DEFAULT_SEVERITY.copy()
        config_severity = self.config.get("severity", {})
        for check_name, level in config_severity.items():
            if level in (Severity.ERROR, Severity.WARNING, Severity.INFO):
                self.severity_map[check_name] = level

        # Blocking severities
        default_blocking = [Severity.ERROR]
        blocking = self.config.get("blocking_severities", default_blocking)
        if isinstance(blocking, str):
            blocking = [blocking]
        self.blocking_severities: set[str] = set(blocking)

        # Disabled checks
        self.disabled_checks: set[str] = set(self.config.get("disabled_checks", []))

        # Skip lists
        self.skip_string_fields: set[str] = set(
            self.config.get("skip_string_fields", DEFAULT_SKIP_STRING_FIELDS)
        )
        self.skip_help_fields: set[str] = set(
            self.config.get("skip_help_fields", DEFAULT_SKIP_HELP_FIELDS)
        )
        self.skip_docstring_methods: set[str] = (
            set(self.config.get("skip_docstring_methods", []))
            | DEFAULT_SKIP_DOCSTRING_METHODS
        )

        # Docstring settings
        self.min_docstring_length: int = self.config.get("min_docstring_length", 10)

        # Path exclusions
        self.exclude_paths: list[str] = self.config.get(
            "exclude_paths", DEFAULT_EXCLUDE_PATHS
        )

        # Changed files detector (lazy init)
        self._changed_detector: ChangedFilesDetector | None = None

    @property
    def changed_detector(self) -> ChangedFilesDetector:
        """Get or create changed files detector."""
        if self._changed_detector is None:
            self._changed_detector = ChangedFilesDetector(self.base_branch)
        return self._changed_detector

    def get_severity(self, check_name: str) -> str:
        """Get severity for a check."""
        return self.severity_map.get(check_name, Severity.WARNING)

    def is_check_disabled(self, check_name: str) -> bool:
        """Check if a check is disabled."""
        return check_name in self.disabled_checks

    def is_blocking(self, severity: str) -> bool:
        """Check if a severity level should block."""
        return severity in self.blocking_severities

    def should_report(self, check_name: str) -> bool:
        """Check if a check should be reported (not disabled)."""
        return not self.is_check_disabled(check_name)

    def is_path_excluded(self, filepath: str) -> bool:
        """Check if a file path should be excluded."""
        for pattern in self.exclude_paths:
            if fnmatch.fnmatch(filepath, pattern):
                return True
        return False

    def use_changed_files_only(self) -> bool:
        """Check if we should only validate changed files."""
        return self.validation_scope == "changed"

    def filter_files_by_scope(self, files: list[dict]) -> list[dict]:
        """Filter files based on validation scope."""
        if not self.use_changed_files_only():
            return files
        return self.changed_detector.filter_changed_files(files)