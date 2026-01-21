# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Configuration loader for solt-pre-commit.

Loads configuration from .solt-hooks.yaml with fallback to defaults.
Supports validation_scope for changed-only or full repository validation.

Context Detection:
- LOCAL (pre-commit): Uses staged files (git diff --cached)
- CI (GitHub Actions): Uses PR diff (base...HEAD)
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
    # ASCII-safe icons for CI environments
    ICONS = {ERROR: "[ERROR]", WARNING: "[WARN]", INFO: "[INFO]"}
    # Unicode icons for terminal
    ICONS_UNICODE = {ERROR: "\u274c", WARNING: "\u26a0\ufe0f", INFO: "\u2139\ufe0f"}


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


class ExecutionContext:
    """Determines execution context: local pre-commit or CI."""

    LOCAL = "local"
    CI = "ci"
    UNKNOWN = "unknown"

    @staticmethod
    def detect() -> str:
        """Detect current execution context.

        Returns:
            'local' - Running locally (pre-commit hook)
            'ci' - Running in CI environment
            'unknown' - Cannot determine
        """
        # Check for CI environment variables
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            return ExecutionContext.CI

        # Check for GitHub PR context
        if os.environ.get("GITHUB_BASE_REF") or os.environ.get("SOLT_BASE_BRANCH"):
            return ExecutionContext.CI

        # Check if we have staged files (indicates local pre-commit)
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                capture_output=True,
                text=True,
                check=True,
            )
            if result.stdout.strip():
                return ExecutionContext.LOCAL
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return ExecutionContext.UNKNOWN

    @staticmethod
    def is_local() -> bool:
        """Check if running locally (not in CI)."""
        return ExecutionContext.detect() == ExecutionContext.LOCAL

    @staticmethod
    def is_ci() -> bool:
        """Check if running in CI environment."""
        return ExecutionContext.detect() == ExecutionContext.CI


class ChangedFilesDetector:
    """Detects which files have changed for PR/commit validation.

    Context-aware detection:
    - LOCAL: Uses staged files (git diff --cached)
    - CI: Uses PR diff against base branch (base...HEAD)
    """

    def __init__(self, base_branch: str | None = None):
        self._context = ExecutionContext.detect()
        self.base_branch = base_branch or self._detect_base_branch()
        self._changed_files: set[str] | None = None
        self._is_ci = self._context == ExecutionContext.CI

    def _log(self, message: str) -> None:
        """Log debug message."""
        # Log in CI or when SOLT_DEBUG is set
        if self._is_ci or os.environ.get("SOLT_DEBUG"):
            print(f"[ChangedFilesDetector] {message}")

    def _detect_base_branch(self) -> str:
        """Auto-detect the base branch.

        Priority:
        1. SOLT_BASE_BRANCH environment variable (set by CI workflow)
        2. GITHUB_BASE_REF environment variable (GitHub Actions PR context)
        3. Auto-detect from known branch names (main, master, develop)
        4. Fallback to HEAD~1
        """
        # 1. Check explicit environment variable from workflow
        solt_base = os.environ.get("SOLT_BASE_BRANCH")
        if solt_base:
            # Ensure it has origin/ prefix
            if not solt_base.startswith("origin/"):
                solt_base = f"origin/{solt_base}"
            return solt_base

        # 2. Check GitHub Actions PR context
        github_base = os.environ.get("GITHUB_BASE_REF")
        if github_base:
            return f"origin/{github_base}"

        # 3. Auto-detect from known branches
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

        # 4. Fallback
        return "HEAD~1"

    def _ensure_base_branch_available(self) -> bool:
        """Ensure the base branch ref is available for diff."""
        if self.base_branch == "HEAD~1":
            return True

        # Check if the ref exists
        try:
            subprocess.run(
                ["git", "rev-parse", "--verify", self.base_branch],
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            self._log(f"Base branch {self.base_branch} not found locally, trying to fetch...")
            # Try to fetch it
            branch_name = self.base_branch.replace("origin/", "")
            try:
                subprocess.run(
                    ["git", "fetch", "origin", branch_name, "--depth=1"],
                    capture_output=True,
                    check=True,
                )
                self._log(f"Successfully fetched origin/{branch_name}")
                return True
            except subprocess.CalledProcessError as e:
                self._log(f"Failed to fetch {branch_name}: {e}")
                return False

    def _get_staged_files(self) -> set[str]:
        """Get staged files for local pre-commit.

        Returns:
            Set of absolute file paths that are staged for commit
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                capture_output=True,
                text=True,
                check=True,
            )
            files = result.stdout.strip().split("\n")
            staged = {os.path.realpath(f) for f in files if f.strip()}
            self._log(f"Staged files: {len(staged)} files")
            return staged
        except subprocess.CalledProcessError:
            self._log("Failed to get staged files")
            return set()

    def _get_ci_changed_files(self) -> set[str]:
        """Get changed files for CI (PR diff).

        Uses three-dot diff to get only changes introduced by PR.
        """
        self._log(f"Detecting CI changed files vs {self.base_branch}")

        # Ensure base branch is available
        if not self._ensure_base_branch_available():
            self._log("Base branch not available, returning empty set")
            return set()

        # Try three-dot diff first (PR changes only - from merge base)
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{self.base_branch}...HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            files = result.stdout.strip().split("\n")
            changed = {os.path.realpath(f) for f in files if f}
            self._log(f"Three-dot diff found {len(changed)} changed files")
            return changed
        except subprocess.CalledProcessError:
            pass

        # Fallback to two-dot diff
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=ACMR", self.base_branch],
                capture_output=True,
                text=True,
                check=True,
            )
            files = result.stdout.strip().split("\n")
            changed = {os.path.realpath(f) for f in files if f}
            self._log(f"Two-dot diff found {len(changed)} changed files")
            return changed
        except subprocess.CalledProcessError:
            self._log("All CI diff methods failed")
            return set()

    def get_changed_files(self) -> set[str]:
        """Get set of changed files based on context.

        - LOCAL: Returns staged files (git diff --cached)
        - CI: Returns PR diff (base...HEAD)

        Returns:
            Set of absolute file paths that have changed
        """
        if self._changed_files is not None:
            return self._changed_files

        self._log(f"Context: {self._context}")

        if self._context == ExecutionContext.LOCAL:
            # LOCAL: Use staged files
            self._changed_files = self._get_staged_files()
        elif self._context == ExecutionContext.CI:
            # CI: Use PR diff
            self._changed_files = self._get_ci_changed_files()
        else:
            # UNKNOWN: Try staged first, then CI diff
            self._changed_files = self._get_staged_files()
            if not self._changed_files:
                self._changed_files = self._get_ci_changed_files()

        return self._changed_files

    def is_file_changed(self, filepath: str) -> bool:
        """Check if a specific file has changed."""
        return os.path.realpath(filepath) in self.get_changed_files()

    def filter_changed_files(self, files: list[dict]) -> list[dict]:
        """Filter a list of file dicts to only those that changed."""
        changed = self.get_changed_files()
        return [f for f in files if os.path.realpath(f["filename"]) in changed]

    @property
    def context(self) -> str:
        """Get the detected execution context."""
        return self._context


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
        self.skip_string_fields: set[str] = set(self.config.get("skip_string_fields", DEFAULT_SKIP_STRING_FIELDS))
        self.skip_help_fields: set[str] = set(self.config.get("skip_help_fields", DEFAULT_SKIP_HELP_FIELDS))
        self.skip_docstring_methods: set[str] = (
            set(self.config.get("skip_docstring_methods", [])) | DEFAULT_SKIP_DOCSTRING_METHODS
        )

        # Docstring settings
        self.min_docstring_length: int = self.config.get("min_docstring_length", 10)

        # Path exclusions
        self.exclude_paths: list[str] = self.config.get("exclude_paths", DEFAULT_EXCLUDE_PATHS)

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

    def get_execution_context(self) -> str:
        """Get the detected execution context (local/ci/unknown)."""
        return self.changed_detector.context
