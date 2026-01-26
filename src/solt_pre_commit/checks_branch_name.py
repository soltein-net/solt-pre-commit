# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Branch naming policy validation with multi-version Odoo support.

Supports branch patterns (Odoo version is REQUIRED):
- Version + ticket: feature/17.0-SOLT-123-description (recommended)
- Version only: feature/17.0-description (flexible mode)
- Version-type: 17.0-hotfix-description
- Release: release/17.0.1.0
- Protected: main, master, 17.0, 18.0 (skipped)

Patterns WITHOUT Odoo version are NOT allowed:
- feature/add-something (INVALID)
- feature/SOLT-123-something (INVALID)
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

DEFAULT_BRANCH_TYPES = [
    "feature",
    "fix",
    "hotfix",
    "bugfix",
    "release",
    "refactor",
    "docs",
    "test",
    "chore",
    # additional types
    "imp",
    "improvement",
    "perf",
    "style",
    "ci",
    "build",
    "deps",
    "config",
    "security",
    "ux",
    "ui",
    "infra",
    "ops",
    "release-candidate",
    "revert",
]

DEFAULT_PROTECTED_BRANCHES = {
    "main",
    "master",
    "develop",
    "development",
    "staging",
    "production",
    "HEAD",
}

# Odoo version pattern: 16.0, 17.0, 18.0, etc.
ODOO_VERSION_PATTERN = r"\d+\.0"

# Default protected patterns (Odoo version branches)
DEFAULT_PROTECTED_PATTERNS = [
    rf"^{ODOO_VERSION_PATTERN}$",  # 17.0, 18.0
    rf"^{ODOO_VERSION_PATTERN}\.\d+.*$",  # 17.0.1, 17.0.1.0, 17.0-stable
]


class BranchNameValidator:
    """Validates branch names against naming policy.

    Odoo version prefix is REQUIRED in all branch names.

    Supports multiple branch naming conventions:
    1. Version + ticket: feature/17.0-SOLT-123-description (recommended)
    2. Version only: feature/17.0-description (flexible mode)
    3. Version-type: 17.0-hotfix-description
    4. Release: release/17.0.1.0
    5. Protected: main, master, 17.0, 18.0 (validation skipped)

    NOT allowed (missing version):
    - feature/add-something
    - feature/SOLT-123-something
    """

    CONFIG_FILES = [".solt-hooks.yaml", ".solt-hooks.yml", "solt-hooks.yaml"]

    def __init__(
        self,
        ticket_prefixes: Optional[List[str]] = None,
        config_path: Optional[str] = None,
        strict: Optional[bool] = None,
    ):
        """Initialize the validator.

        Args:
            ticket_prefixes: List of valid ticket prefixes (e.g., ['SOLT', 'PROJ'])
            config_path: Path to configuration file
            strict: If True, requires ticket in branch name
        """
        self.config = self._load_config(config_path)
        self.branch_config = self.config.get("branch_naming", {})

        if strict is not None:
            self.strict = strict
        else:
            self.strict = self.branch_config.get("strict", False)

        self.ticket_prefixes = ticket_prefixes or self._get_prefixes_from_config()
        self.allowed_types = self._get_allowed_types()
        self.protected_patterns = self._get_protected_patterns()
        self._compile_patterns()

    def _load_config(self, config_path: Optional[str] = None) -> dict:
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

    def _get_prefixes_from_config(self) -> List[str]:
        """Get ticket prefixes from config."""
        prefixes = self.branch_config.get("ticket_prefixes", [])
        return prefixes if prefixes else ["[A-Z]+"]

    def _get_allowed_types(self) -> List[str]:
        """Get allowed branch types from config."""
        return self.branch_config.get("allowed_types", DEFAULT_BRANCH_TYPES)

    def _get_protected_patterns(self) -> List[str]:
        """Get protected patterns from config."""
        config_patterns = self.branch_config.get("protected_patterns", [])
        if config_patterns:
            # Merge with defaults
            return list(set(DEFAULT_PROTECTED_PATTERNS + config_patterns))
        return DEFAULT_PROTECTED_PATTERNS

    def _compile_patterns(self):
        """Compile regex patterns for branch validation.

        Creates patterns for each branch type supporting:
        - Version + ticket: type/17.0-TICKET-123-description (recommended)
        - Version only: type/17.0-description
        - Release: release/17.0.1.0
        - Version-type: 17.0-type-description (e.g., 17.0-hotfix-something)

        NOTE: Odoo version prefix is REQUIRED in all branch names.
        """
        if self.ticket_prefixes == ["[A-Z]+"]:
            prefix_pattern = "[A-Z]+"
        else:
            prefix_pattern = "(" + "|".join(re.escape(p) for p in self.ticket_prefixes) + ")"

        self.patterns = {}

        # Build types pattern for version-type format
        types_pattern = "|".join(self.allowed_types)

        for branch_type in self.allowed_types:
            if branch_type == "release":
                # release/17.0.1.0 or release/1.0.0
                self.patterns[branch_type] = re.compile(r"^release/\d+\.\d+(\.\d+)*$")
            elif self.strict:
                # Strict mode: requires version AND ticket
                # - feature/17.0-SOLT-123-description (version + ticket)
                self.patterns[branch_type] = re.compile(
                    rf"^{branch_type}/"
                    rf"{ODOO_VERSION_PATTERN}-{prefix_pattern}-\d+-.+$"  # 17.0-SOLT-123-description
                )
            else:
                # Flexible mode: version required, ticket optional
                # - type/17.0-TICKET-123-description (version + ticket)
                # - type/17.0-description (version only)
                self.patterns[branch_type] = re.compile(
                    rf"^{branch_type}/("
                    rf"{ODOO_VERSION_PATTERN}-{prefix_pattern}-\d+-.+|"  # 17.0-SOLT-123-description
                    rf"{ODOO_VERSION_PATTERN}-.+"  # 17.0-description
                    rf")$"
                )

        # Add pattern for version-type-description format: 17.0-hotfix-something, 18.0-feature-new
        self.patterns["version-type"] = re.compile(
            rf"^{ODOO_VERSION_PATTERN}-({types_pattern})-.+$"
        )

    def get_current_branch(self) -> Optional[str]:
        """Get current git branch name."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def is_protected_branch(self, branch_name: str) -> bool:
        """Check if branch is protected (skip validation).

        Protected branches include:
        - Explicit names: main, master, develop, etc.
        - Odoo version branches: 17.0, 18.0, 17.0.1.0
        - Custom patterns from config
        """
        # Check explicit protected branches
        if branch_name in DEFAULT_PROTECTED_BRANCHES:
            return True

        # Check additional protected branches from config
        additional_protected = self.branch_config.get("protected_branches", [])
        if branch_name in additional_protected:
            return True

        # Check protected patterns
        for pattern in self.protected_patterns:
            try:
                if re.match(pattern, branch_name):
                    return True
            except re.error:
                pass

        return False

    def extract_odoo_version(self, branch_name: str) -> Optional[str]:
        """Extract Odoo version from branch name if present.

        Args:
            branch_name: The branch name to analyze

        Returns:
            Odoo version string (e.g., '17.0') or None
        """
        # Pattern 1: Direct version branch (17.0, 18.0)
        match = re.match(rf"^({ODOO_VERSION_PATTERN})", branch_name)
        if match:
            return match.group(1)

        # Pattern 2: Prefixed branch (feature/17.0-something)
        match = re.match(rf"^[a-z]+/({ODOO_VERSION_PATTERN})", branch_name)
        if match:
            return match.group(1)

        # Pattern 3: Version anywhere
        match = re.search(rf"({ODOO_VERSION_PATTERN})", branch_name)
        if match:
            return match.group(1)

        return None

    def validate(self, branch_name: str) -> Tuple[bool, str]:
        """Validate a branch name against the naming policy.

        Args:
            branch_name: The branch name to validate

        Returns:
            Tuple of (is_valid, message)
        """
        # Check if protected (skip validation)
        if self.is_protected_branch(branch_name):
            odoo_version = self.extract_odoo_version(branch_name)
            if odoo_version:
                return True, f"Protected Odoo {odoo_version} branch '{branch_name}' - skipped validation"
            return True, f"Protected branch '{branch_name}' - skipped validation"

        # Check against type patterns
        for branch_type, pattern in self.patterns.items():
            if pattern.match(branch_name):
                odoo_version = self.extract_odoo_version(branch_name)
                if odoo_version:
                    return True, f"Valid {branch_type} branch for Odoo {odoo_version}: {branch_name}"
                return True, f"Valid {branch_type} branch: {branch_name}"

        return False, self._generate_error_message(branch_name)

    def _generate_error_message(self, branch_name: str) -> str:
        """Generate a helpful error message for invalid branch names."""
        types_str = ", ".join(self.allowed_types[:10])  # Show first 10
        if len(self.allowed_types) > 10:
            types_str += f", ... (+{len(self.allowed_types) - 10} more)"

        if self.strict:
            if self.ticket_prefixes == ["[A-Z]+"]:
                prefixes_str = "Any UPPERCASE prefix (e.g., SOLT, PROJ)"
            else:
                prefixes_str = ", ".join(self.ticket_prefixes)

            example_prefix = self.ticket_prefixes[0] if self.ticket_prefixes[0] != "[A-Z]+" else "PROJ"

            message = f"""
[ERROR] Invalid branch name: '{branch_name}'

Mode: STRICT (version AND ticket required)

Branch names must follow this pattern:
  <type>/<odoo-version>-<TICKET>-<number>-<description>

Valid types: {types_str}
Ticket prefixes: {prefixes_str}

Examples:
  [OK] feature/17.0-{example_prefix}-123-add-new-feature
  [OK] fix/18.0-{example_prefix}-456-correct-bug
  [OK] hotfix/17.0-{example_prefix}-789-urgent-fix
  [OK] 17.0-hotfix-urgent-fix
  [OK] release/17.0.1.0

Invalid (missing version or ticket):
  [X] feature/{example_prefix}-123-something  (missing version)
  [X] feature/add-something                   (missing version and ticket)
  [X] feature/17.0-add-something              (missing ticket in strict mode)
"""
        else:
            message = f"""
[ERROR] Invalid branch name: '{branch_name}'

Mode: FLEXIBLE (version required, ticket optional)

Branch names must follow one of these patterns:
  <type>/<odoo-version>-<TICKET>-<number>-<description>  (recommended)
  <type>/<odoo-version>-<description>
  <odoo-version>-<type>-<description>

Valid types: {types_str}

Examples:
  [OK] feature/17.0-SOLT-123-add-new-feature  (version + ticket)
  [OK] fix/18.0-PROJ-456-correct-bug          (version + ticket)
  [OK] feature/17.0-add-new-feature           (version only)
  [OK] hotfix/18.0-urgent-fix                 (version only)
  [OK] 17.0-hotfix-urgent-fix                 (version-type format)
  [OK] release/17.0.1.0

Invalid (missing Odoo version):
  [X] feature/add-something          (missing version)
  [X] feature/SOLT-123-something     (missing version)
  [X] Feature/17.0-something         (uppercase type)
"""

        # List protected branches and patterns
        protected = sorted(DEFAULT_PROTECTED_BRANCHES)
        additional = self.branch_config.get("protected_branches", [])
        if additional:
            protected = sorted(set(protected) | set(additional))

        message += f"""
Protected branches (no validation required):
  {", ".join(protected)}

Protected patterns (Odoo version branches):
  * 17.0, 18.0, 19.0 (direct version)
  * 17.0.1.0 (version with patch)
"""
        return message


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate git branch naming policy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  solt-check-branch feature/17.0-add-invoice
  solt-check-branch fix/SOLT-123-bug-fix
  solt-check-branch --strict feature/SOLT-456-new-feature
        """,
    )
    parser.add_argument("branch", nargs="?", help="Branch name to validate")
    parser.add_argument("--ticket-prefixes", nargs="+", default=None, help="Valid ticket prefixes")
    parser.add_argument("--config", default=None, help="Path to config file")
    parser.add_argument("--strict", action="store_true", default=None, help="Require ticket or version")
    parser.add_argument("--no-strict", action="store_true", help="Allow simple descriptions")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output on success")
    parser.add_argument("--show-version", action="store_true", help="Show detected Odoo version")

    args = parser.parse_args()

    strict = None
    if args.strict:
        strict = True
    elif args.no_strict:
        strict = False

    validator = BranchNameValidator(
        ticket_prefixes=args.ticket_prefixes,
        config_path=args.config,
        strict=strict,
    )

    branch_name = args.branch or validator.get_current_branch()

    if not branch_name:
        print("Error: Could not determine branch name", file=sys.stderr)
        sys.exit(1)

    # Show detected version if requested
    if args.show_version:
        odoo_version = validator.extract_odoo_version(branch_name)
        if odoo_version:
            print(f"Detected Odoo version: {odoo_version}")
        else:
            print("No Odoo version detected in branch name")
        sys.exit(0)

    is_valid, message = validator.validate(branch_name)

    if is_valid:
        if not args.quiet:
            print(f"[OK] {message}")
        sys.exit(0)
    else:
        print(message, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
