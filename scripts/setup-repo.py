#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Setup script to initialize solt-pre-commit in a client repository.

Usage:
    python setup-repo.py /path/to/odoo-repo
    python setup-repo.py /path/to/odoo-repo --scope full
    python setup-repo.py /path/to/odoo-repo --dry-run
    python setup-repo.py /path/to/odoo-repo --local  # For monorepo

Example:
    python scripts/setup-repo.py ../solt-budget --scope changed

Workflows installed:
    - solt-validate.yml: PR/push validation (runs on every PR)
    - Includes weekly badge updates using centralized Soltein Gist
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# PATH CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.absolute()
REPO_ROOT = SCRIPT_DIR.parent
TEMPLATES_DIR = REPO_ROOT / "templates"
CONFIGS_DIR = REPO_ROOT / "configs"

# ─────────────────────────────────────────────────────────────────────────────
# CENTRALIZED GIST CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
SOLTEIN_GIST_ID = "147d543a086f6735d1ffa02172766e86"

# ─────────────────────────────────────────────────────────────────────────────
# FILE MAPPINGS
# ─────────────────────────────────────────────────────────────────────────────
# (source_path, destination_relative_path, description)
FILES_TO_COPY = [
    # Config files (root level)
    (CONFIGS_DIR / ".pylintrc", ".pylintrc", "Pylint configuration"),
    (CONFIGS_DIR / "pyproject-base.toml", "pyproject.toml", "Python project configuration"),
    (TEMPLATES_DIR / ".solt-hooks.yaml", ".solt-hooks.yaml", "Solt hooks configuration"),
]

# Pre-commit config (depends on --local flag)
PRECOMMIT_REMOTE = (
    TEMPLATES_DIR / ".pre-commit-config.yaml",
    ".pre-commit-config.yaml",
    "Pre-commit config (GitHub)",
)
PRECOMMIT_LOCAL = (
    TEMPLATES_DIR / ".pre-commit-config-local.yaml",
    ".pre-commit-config.yaml",
    "Pre-commit config (local/monorepo)",
)

# GitHub workflow (combined validation + weekly badges)
WORKFLOW_FILE = (
    TEMPLATES_DIR / "github-workflows" / "solt-validate.yml",
    ".github/workflows/solt-validate.yml",
    "GitHub Actions workflow (validation + badges)",
)

# Client workflow content (generated, not from template)
CLIENT_WORKFLOW_CONTENT = """# =============================================================================
# SOLT VALIDATION + WEEKLY BADGES
# =============================================================================
# This workflow runs:
# 1. Validation on every PR/push (solt-validate.yml)
# 2. Badge updates weekly (solt-update-badges.yml)
#
# CENTRALIZED BADGES:
# - All badges stored in Soltein's central Gist
# - No configuration needed - uses repository name automatically
# =============================================================================
name: Solt Validation

on:
  push:
    branches:
      - main
      - master
      - develop
      - '17.0'
      - '18.0'
      - '19.0'
      - '*.0'
  pull_request:
    branches:
      - main
      - master
      - develop
      - '17.0'
      - '18.0'
      - '19.0'
      - '*.0'

  # Weekly badge updates - Every Monday at 6:00 AM UTC
  schedule:
    - cron: '0 6 * * 1'

  # Allow manual trigger
  workflow_dispatch:

jobs:
  # ---------------------------------------------------------------------------
  # PR/PUSH VALIDATION
  # ---------------------------------------------------------------------------
  validate:
    if: github.event_name != 'schedule'
    uses: soltein-net/solt-pre-commit/.github/workflows/solt-validate.yml@v1.0.0
    with:
      validation-scope: 'changed'
      fail-on-warnings: false
      pylint-blocking: true
      ruff-blocking: false
      docstring-threshold: 80

  # ---------------------------------------------------------------------------
  # WEEKLY BADGE UPDATES
  # ---------------------------------------------------------------------------
  update-badges:
    if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
    uses: soltein-net/solt-pre-commit/.github/workflows/solt-update-badges.yml@v1.0.0
    # No inputs needed - uses defaults:
    # - gist-id: Soltein central gist ({gist_id})
    # - badge-filename-prefix: repository name (automatic)
    secrets:
      GIST_SECRET: ${{{{ secrets.GIST_SECRET }}}}
"""


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}")


def print_step(icon: str, text: str) -> None:
    """Print a step with icon."""
    print(f"  {icon} {text}")


def copy_file(src: Path, dest: Path, dry_run: bool = False, force: bool = True) -> bool:
    """Copy a file to destination, creating directories as needed.

    Args:
        src: Source file path
        dest: Destination file path
        dry_run: If True, only show what would be done
        force: If True, overwrite existing files

    Returns:
        True if file was copied/would be copied, False otherwise
    """
    # Check source exists
    if not src.exists():
        print_step("⚠️ ", f"Source not found: {src}")
        return False

    # Determine action
    if dest.exists():
        if not force:
            print_step("⏭️ ", f"Skipped (exists): {dest.name}")
            return False
        action = "overwrite"
    else:
        action = "create"

    # Dry run - just show what would happen
    if dry_run:
        print_step("📄", f"Would {action}: {dest}")
        return True

    # Actually copy the file
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

        if action == "overwrite":
            print_step("🔄", f"Updated: {dest}")
        else:
            print_step("✅", f"Created: {dest}")

        # Verify the copy worked
        if not dest.exists():
            print_step("❌", f"Failed to create: {dest}")
            return False

        return True

    except Exception as e:
        print_step("❌", f"Error copying {src.name}: {e}")
        return False


def update_file_content(
    filepath: Path,
    replacements: dict[str, str],
    dry_run: bool = False,
) -> bool:
    """Update file content with replacements."""
    if not filepath.exists():
        return False

    content = filepath.read_text()
    modified = False

    for old, new in replacements.items():
        if old in content:
            content = content.replace(old, new)
            modified = True

    if modified and not dry_run:
        filepath.write_text(content)
        print_step("✏️ ", f"Updated: {filepath.name}")

    return modified


def install_precommit_hooks(target: Path, dry_run: bool = False) -> bool:
    """Install pre-commit hooks in target repository."""
    if dry_run:
        print_step("📄", "Would run: pre-commit install")
        return True

    try:
        subprocess.run(
            ["pre-commit", "install"],
            cwd=target,
            check=True,
            capture_output=True,
        )
        print_step("✅", "Pre-commit hooks installed")
        return True
    except subprocess.CalledProcessError as e:
        print_step("⚠️ ", f"Failed to install hooks: {e}")
        return False
    except FileNotFoundError:
        print_step("⚠️ ", "pre-commit not found. Install with: pip install pre-commit")
        return False


def cleanup_old_files(target: Path, dry_run: bool = False) -> None:
    """Remove old config files that are now consolidated."""
    old_files = [
        "ruff.toml",  # Now in pyproject.toml
    ]

    for filename in old_files:
        filepath = target / filename
        if filepath.exists():
            if dry_run:
                print_step("🗑️ ", f"Would remove (now in pyproject.toml): {filename}")
            else:
                filepath.unlink()
                print_step("🗑️ ", f"Removed (now in pyproject.toml): {filename}")


def setup_repo(
    target_path: str,
    scope: str = "changed",
    dry_run: bool = False,
    local: bool = False,
    force: bool = True,
    odoo_version: str = "auto",
) -> None:
    """Setup solt-pre-commit in a target repository.

    Args:
        target_path: Path to the target repository
        scope: Validation scope ('changed' or 'full')
        dry_run: If True, only show what would be done
        local: If True, use local hooks config (for monorepo)
        force: If True, overwrite existing files
        odoo_version: Odoo version (auto, 17.0, 18.0, 19.0)
    """
    target = Path(target_path).absolute()

    if not target.exists():
        print(f"❌ Target path does not exist: {target}")
        sys.exit(1)

    # ─────────────────────────────────────────────────────────────────────
    # HEADER
    # ─────────────────────────────────────────────────────────────────────
    mode_str = "DRY RUN - " if dry_run else ""
    print(f"\n{'=' * 60}")
    print(f"🚀 {mode_str}Setting up solt-pre-commit")
    print(f"{'=' * 60}")
    print(f"  Target:       {target}")
    print(f"  Scope:        {scope}")
    print(f"  Odoo Version: {odoo_version}")
    print(f"  Mode:         {'local (monorepo)' if local else 'remote (GitHub)'}")
    print(f"  Overwrite:    {'yes' if force else 'no'}")
    print(f"{'=' * 60}")

    # Show source paths for debugging
    print("\n  Source paths:")
    print(f"    REPO_ROOT:     {REPO_ROOT}")
    print(f"    CONFIGS_DIR:   {CONFIGS_DIR}")
    print(f"    TEMPLATES_DIR: {TEMPLATES_DIR}")

    # ─────────────────────────────────────────────────────────────────────
    # CLEANUP OLD FILES
    # ─────────────────────────────────────────────────────────────────────
    print_header("🧹 Cleanup Old Files")
    cleanup_old_files(target, dry_run)

    # ─────────────────────────────────────────────────────────────────────
    # COPY CONFIG FILES
    # ─────────────────────────────────────────────────────────────────────
    print_header("📁 Configuration Files")

    files = FILES_TO_COPY.copy()

    # Add pre-commit config based on mode
    if local:
        files.append(PRECOMMIT_LOCAL)
    else:
        files.append(PRECOMMIT_REMOTE)

    # Track success/failure
    copied = 0
    failed = 0

    for src, dest_rel, description in files:
        dest = target / dest_rel

        # Debug output
        print(f"\n  [{description}]")
        print(f"    Source: {src}")
        print(f"    Exists: {src.exists()}")
        print(f"    Dest:   {dest}")

        if src.exists():
            if copy_file(src, dest, dry_run, force):
                copied += 1
            else:
                failed += 1
        else:
            print_step("❌", f"Template not found: {src}")
            failed += 1

    # ─────────────────────────────────────────────────────────────────────
    # GENERATE CLIENT WORKFLOW (with centralized badges)
    # ─────────────────────────────────────────────────────────────────────
    print_header("📄 GitHub Workflow")

    workflow_dest = target / ".github" / "workflows" / "solt-validate.yml"
    workflow_content = CLIENT_WORKFLOW_CONTENT.format(gist_id=SOLTEIN_GIST_ID)

    print("\n  [GitHub Actions workflow (validation + badges)]")
    print(f"    Dest:   {workflow_dest}")
    print(f"    Gist:   {SOLTEIN_GIST_ID}")

    if dry_run:
        print_step("📄", f"Would create: {workflow_dest}")
        copied += 1
    else:
        try:
            workflow_dest.parent.mkdir(parents=True, exist_ok=True)
            workflow_dest.write_text(workflow_content, encoding="utf-8")
            if workflow_dest.exists():
                print_step("✅", f"Created: {workflow_dest}")
                copied += 1
            else:
                print_step("❌", f"Failed to create: {workflow_dest}")
                failed += 1
        except Exception as e:
            print_step("❌", f"Error creating workflow: {e}")
            failed += 1

    print(f"\n  Summary: {copied} copied, {failed} failed")

    # ─────────────────────────────────────────────────────────────────────
    # UPDATE CONFIGURATIONS
    # ─────────────────────────────────────────────────────────────────────
    print_header("⚙️  Applying Configuration")

    # Update .solt-hooks.yaml settings
    solt_hooks_file = target / ".solt-hooks.yaml"
    if solt_hooks_file.exists():
        replacements = {}

        # Update validation scope
        if scope != "changed":
            replacements["validation_scope: changed"] = f"validation_scope: {scope}"

        # Update Odoo version
        if odoo_version != "auto":
            replacements["odoo_version: auto"] = f"odoo_version: {odoo_version}"

        if replacements:
            update_file_content(solt_hooks_file, replacements, dry_run)
            if not dry_run:
                print_step("✅", f"Set validation_scope to: {scope}")
                if odoo_version != "auto":
                    print_step("✅", f"Set odoo_version to: {odoo_version}")
            else:
                print_step("📄", f"Would set validation_scope to: {scope}")
                if odoo_version != "auto":
                    print_step("📄", f"Would set odoo_version to: {odoo_version}")
        else:
            print_step("ℹ️ ", f"validation_scope: {scope}, odoo_version: {odoo_version}")
    else:
        print_step("ℹ️ ", f"validation_scope: {scope}, odoo_version: {odoo_version}")

    # ─────────────────────────────────────────────────────────────────────
    # INSTALL HOOKS
    # ─────────────────────────────────────────────────────────────────────
    print_header("🔧 Installing Hooks")
    install_precommit_hooks(target, dry_run)

    # ─────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    if dry_run:
        print("📋 DRY RUN COMPLETE - No changes made")
    else:
        print("✅ SETUP COMPLETE")
    print(f"{'=' * 60}")

    print("\n📂 Files created/updated:")
    print("   pyproject.toml             → Python tools config (ruff, black, isort, pytest)")
    print("   .pylintrc                  → Pylint-odoo configuration")
    print("   .solt-hooks.yaml           → Soltein validation settings")
    print("   .pre-commit-config.yaml    → Pre-commit hook configuration")
    print("   .github/workflows/solt-validate.yml → CI workflow + weekly badges")

    print("\n🏷️  Badges configuration:")
    print(f"   Gist ID: {SOLTEIN_GIST_ID}")
    print("   Prefix:  (repository name - automatic)")
    print("   Schedule: Weekly (Mondays 6:00 AM UTC)")

    print("\n📋 Next steps:")
    print("   1. Review .solt-hooks.yaml and adjust settings if needed")
    print("   2. Run: pre-commit run --all-files")
    print("   3. Commit the configuration files")
    print("   4. (Optional) Trigger badge update: Actions → Solt Validation → Run workflow")

    if local:
        print("\n⚠️  Local mode: Ensure solt-pre-commit is in PYTHONPATH")
        print("   Or install: pip install -e ../solt-pre-commit")

    print("")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Setup solt-pre-commit in a client repository",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Setup with default options (overwrites existing files)
  python setup-repo.py /path/to/solt-budget

  # Setup with full validation scope
  python setup-repo.py /path/to/solt-budget --scope full

  # Setup for specific Odoo version
  python setup-repo.py /path/to/solt-budget --odoo-version 18.0

  # Preview changes without applying
  python setup-repo.py /path/to/solt-budget --dry-run

  # Setup for monorepo (local hooks)
  python setup-repo.py /path/to/solt-addons --local

  # Skip existing files (don't overwrite)
  python setup-repo.py /path/to/solt-budget --no-force
        """,
    )

    parser.add_argument(
        "path",
        help="Path to the target repository",
    )
    parser.add_argument(
        "--scope",
        choices=["changed", "full"],
        default="changed",
        help="Validation scope: 'changed' for PR files, 'full' for entire repo (default: changed)",
    )
    parser.add_argument(
        "--odoo-version",
        default="auto",
        help="Odoo version: auto-detect or specify explicitly (e.g., 17.0, 18.0, 19.0, 20.0). Default: auto",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local hooks config (for soltein-4.0 monorepo)",
    )
    parser.add_argument(
        "--no-force",
        action="store_true",
        help="Don't overwrite existing files",
    )

    args = parser.parse_args()

    setup_repo(
        target_path=args.path,
        scope=args.scope,
        dry_run=args.dry_run,
        local=args.local,
        force=not args.no_force,
        odoo_version=args.odoo_version,
    )


if __name__ == "__main__":
    main()
