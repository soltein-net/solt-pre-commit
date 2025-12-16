# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Branch naming policy validation."""

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

# Odoo version branches pattern (e.g., 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0)
ODOO_VERSION_BRANCH_PATTERN = r"^\d+\.0$"

# Release version pattern (e.g., 17.0.1.0)
RELEASE_VERSION_PATTERN = r"^\d+\.\d+\.\d+(\.\d+)?$"


class BranchNameValidator:
    """Validates branch names against naming policy."""

    CONFIG_FILES = [".solt-hooks.yaml", ".solt-hooks.yml", "solt-hooks.yaml"]

    def __init__(
        self,
        ticket_prefixes: Optional[List[str]] = None,
        config_path: Optional[str] = None,
        strict: Optional[bool] = None,
    ):
        self.config = self._load_config(config_path)
        self.branch_config = self.config.get("branch_naming", {})

        if strict is not None:
            self.strict = strict
        else:
            self.strict = self.branch_config.get("strict", False)

        self.ticket_prefixes = ticket_prefixes or self._get_prefixes_from_config()
        self.allowed_types = self._get_allowed_types()
        self._compile_patterns()

    def _load_config(self, config_path: Optional[str] = None) -> dict:
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
        prefixes = self.branch_config.get("ticket_prefixes", [])
        return prefixes if prefixes else ["[A-Z]+"]

    def _get_allowed_types(self) -> List[str]:
        return self.branch_config.get("allowed_types", DEFAULT_BRANCH_TYPES)

    def _compile_patterns(self):
        if self.ticket_prefixes == ["[A-Z]+"]:
            prefix_pattern = "[A-Z]+"
        else:
            prefix_pattern = "(" + "|".join(self.ticket_prefixes) + ")"

        self.patterns = {}

        for branch_type in self.allowed_types:
            if branch_type == "release":
                self.patterns[branch_type] = re.compile(r"^release/\d+\.\d+\.\d+(\.\d+)?$")
            elif self.strict:
                self.patterns[branch_type] = re.compile(f"^{branch_type}/{prefix_pattern}-\\d+-.+$")
            else:
                self.patterns[branch_type] = re.compile(
                    f"^{branch_type}/([a-z0-9][-a-z0-9]*|{prefix_pattern}-\\d+-.+)$"
                )

    def get_current_branch(self) -> Optional[str]:
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
        if branch_name in DEFAULT_PROTECTED_BRANCHES:
            return True
        if re.match(ODOO_VERSION_BRANCH_PATTERN, branch_name):
            return True
        additional_protected = self.branch_config.get("protected_branches", [])
        if branch_name in additional_protected:
            return True
        protected_patterns = self.branch_config.get("protected_patterns", [])
        for pattern in protected_patterns:
            try:
                if re.match(pattern, branch_name):
                    return True
            except re.error:
                pass
        return False

    def validate(self, branch_name: str) -> Tuple[bool, str]:
        if self.is_protected_branch(branch_name):
            return True, f"Protected branch '{branch_name}' - skipped validation"

        for branch_type, pattern in self.patterns.items():
            if pattern.match(branch_name):
                return True, f"Valid {branch_type} branch: {branch_name}"

        return False, self._generate_error_message(branch_name)

    def _generate_error_message(self, branch_name: str) -> str:
        types_str = ", ".join(self.allowed_types)

        if self.strict:
            if self.ticket_prefixes == ["[A-Z]+"]:
                prefixes_str = "Any UPPERCASE prefix (e.g., SOLT, PROJ)"
            else:
                prefixes_str = ", ".join(self.ticket_prefixes)

            example_prefix = self.ticket_prefixes[0] if self.ticket_prefixes[0] != "[A-Z]+" else "PROJ"

            message = f"""
❌ Invalid branch name: '{branch_name}'

Mode: STRICT (ticket required)

Branch names must follow the pattern:
  <type>/<TICKET>-<number>-<description>

Valid types: {types_str}
Ticket prefixes: {prefixes_str}

Examples:
  ✔ feature/{example_prefix}-123-add-new-feature
  ✔ fix/{example_prefix}-456-correct-bug
  ✔ release/17.0.1.0

Common mistakes:
  ✗ Feature/... (use lowercase)
  ✗ feature/add-something (missing ticket number)
  ✗ my-branch (missing type prefix)
"""
        else:
            message = f"""
❌ Invalid branch name: '{branch_name}'

Mode: FLEXIBLE (ticket optional)

Branch names must follow the pattern:
  <type>/<description>
  OR
  <type>/<TICKET>-<number>-<description>

Valid types: {types_str}

Examples:
  ✔ feature/add-new-feature
  ✔ feature/SOLT-123-add-new-feature
  ✔ fix/correct-calculation
  ✔ release/17.0.1.0

Common mistakes:
  ✗ Feature/... (use lowercase)
  ✗ my-branch (missing type prefix)
"""

        protected = list(DEFAULT_PROTECTED_BRANCHES)
        protected.extend(self.branch_config.get("protected_branches", []))

        message += f"""
Protected branches (no validation required):
  {", ".join(sorted(protected))}
  Odoo versions: 12.0, 13.0, ..., 17.0, 18.0
"""
        return message


def main():
    parser = argparse.ArgumentParser(description="Validate git branch naming policy")
    parser.add_argument("branch", nargs="?", help="Branch name to validate")
    parser.add_argument("--ticket-prefixes", nargs="+", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--strict", action="store_true", default=None)
    parser.add_argument("--no-strict", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_true")

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

    is_valid, message = validator.validate(branch_name)

    if is_valid:
        if not args.quiet:
            print(f"✔ {message}")
        sys.exit(0)
    else:
        print(message, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
