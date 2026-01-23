#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Setup script to initialize solt-pre-commit in client repositories.

Usage (single repo):
    python setup-repo.py /path/to/odoo-repo
    python setup-repo.py /path/to/odoo-repo --scope full
    python setup-repo.py /path/to/odoo-repo --dry-run
    python setup-repo.py /path/to/odoo-repo --local  # For monorepo

Usage (batch mode):
    python setup-repo.py --batch repos.txt
    python setup-repo.py --batch repos.txt --dry-run
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
# Script location: /solt-pre-commit/scripts/setup-repo.py
# Config files:    /solt-pre-commit/configs/
# Template files:  /solt-pre-commit/templates/
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent  # Go up one level from scripts/ to solt-pre-commit/
CONFIGS_DIR = PROJECT_ROOT / "configs"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

# ─────────────────────────────────────────────────────────────────────────────
# FILE MAPPINGS (source -> destination)
# ─────────────────────────────────────────────────────────────────────────────
# Source files use dot prefix (.pylintrc, .solt-hooks-defaults.yaml)
# Destination files also use dot prefix
FILES_TO_COPY = [
    # (source_path, destination_relative_path, description)
    (CONFIGS_DIR / ".pylintrc", ".pylintrc", "Pylint configuration"),
    (CONFIGS_DIR / "pyproject-base.toml", "pyproject.toml", "Python project configuration"),
    (CONFIGS_DIR / ".solt-hooks-defaults.yaml", ".solt-hooks.yaml", "Solt hooks configuration"),
]

# Pre-commit config (depends on --local flag)
PRECOMMIT_REMOTE = (TEMPLATES_DIR / ".pre-commit-config.yaml", ".pre-commit-config.yaml", "Pre-commit config (GitHub)")
PRECOMMIT_LOCAL = (TEMPLATES_DIR / ".pre-commit-config-local.yaml", ".pre-commit-config.yaml", "Pre-commit config (local/monorepo)")

# GitHub workflow
WORKFLOW_FILE = (TEMPLATES_DIR / "github-workflows" / "solt-validate.yml", ".github/workflows/solt-validate.yml", "GitHub Actions workflow")

# Files to remove (consolidated into pyproject.toml)
FILES_TO_REMOVE = ["ruff.toml"]


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}")


def print_step(icon: str, text: str) -> None:
    """Print a step with icon."""
    print(f"  {icon} {text}")


def copy_file(src: Path, dest: Path, dry_run: bool = False, force: bool = True) -> bool:
    """Copy a file to destination, creating directories as needed."""
    if not src.exists():
        print_step("⚠️ ", f"Source not found: {src}")
        return False

    if dest.exists() and not force:
        print_step("⏭️ ", f"Skipped (exists): {dest.name}")
        return False

    action = "overwrite" if dest.exists() else "create"

    if dry_run:
        print_step("📄", f"Would {action}: {dest}")
        return True

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        icon = "🔄" if action == "overwrite" else "✅"
        print_step(icon, f"{'Updated' if action == 'overwrite' else 'Created'}: {dest}")
        return True
    except Exception as e:
        print_step("❌", f"Error copying {src.name}: {e}")
        return False


def update_file_content(filepath: Path, replacements: dict[str, str], dry_run: bool = False) -> bool:
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
        subprocess.run(["pre-commit", "install"], cwd=target, check=True, capture_output=True)
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
    for filename in FILES_TO_REMOVE:
        filepath = target / filename
        if filepath.exists():
            if dry_run:
                print_step("🗑️ ", f"Would remove: {filename}")
            else:
                filepath.unlink()
                print_step("🗑️ ", f"Removed: {filename}")


def setup_single_repo(
    target_path: str,
    scope: str = "changed",
    dry_run: bool = False,
    local: bool = False,
    force: bool = True,
    odoo_version: str = "auto",
    quiet: bool = False,
) -> bool:
    """Setup solt-pre-commit in a single target repository.

    Returns:
        True if setup was successful, False otherwise.
    """
    target = Path(target_path).absolute()

    if not target.exists():
        print(f"  ❌ Target path does not exist: {target}")
        return False

    if not quiet:
        mode_str = "DRY RUN - " if dry_run else ""
        print(f"\n{'=' * 60}")
        print(f"🚀 {mode_str}Setting up: {target.name}")
        print(f"{'=' * 60}")

    # Cleanup old files
    cleanup_old_files(target, dry_run)

    # Build file list
    files = FILES_TO_COPY.copy()
    files.append(PRECOMMIT_LOCAL if local else PRECOMMIT_REMOTE)
    files.append(WORKFLOW_FILE)

    # Copy files
    copied = 0
    failed = 0

    for src, dest_rel, _description in files:
        dest = target / dest_rel

        if src.exists():
            if copy_file(src, dest, dry_run, force):
                copied += 1
            else:
                failed += 1
        else:
            print_step("❌", f"Source not found: {src}")
            failed += 1

    # Update configurations
    solt_hooks_file = target / ".solt-hooks.yaml"
    if solt_hooks_file.exists():
        replacements = {}
        if scope != "changed":
            replacements["validation_scope: changed"] = f"validation_scope: {scope}"
        if odoo_version != "auto":
            replacements["odoo_version: auto"] = f"odoo_version: {odoo_version}"
        if replacements:
            update_file_content(solt_hooks_file, replacements, dry_run)

    # Install hooks
    install_precommit_hooks(target, dry_run)

    if not quiet:
        print(f"\n  Summary: {copied} copied, {failed} failed")

    return failed == 0


def setup_batch(
    repos_file: str,
    scope: str = "changed",
    dry_run: bool = False,
    local: bool = False,
    force: bool = True,
    odoo_version: str = "auto",
) -> None:
    """Setup solt-pre-commit in multiple repositories from a file."""
    repos_path = Path(repos_file)

    if not repos_path.exists():
        print(f"❌ Repos file not found: {repos_path}")
        sys.exit(1)

    repos = [
        line.strip()
        for line in repos_path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

    mode_str = "DRY RUN - " if dry_run else ""
    print(f"\n{'=' * 60}")
    print(f"🔄 {mode_str}Batch setup for {len(repos)} repositories")
    print(f"{'=' * 60}")
    print(f"  Scope:        {scope}")
    print(f"  Odoo Version: {odoo_version}")
    print(f"  Mode:         {'local (monorepo)' if local else 'remote (GitHub)'}")
    print(f"  Project Root: {PROJECT_ROOT}")
    print(f"  Configs:      {CONFIGS_DIR}")
    print(f"  Templates:    {TEMPLATES_DIR}")
    print(f"{'=' * 60}")

    success = 0
    failed = 0

    for repo in repos:
        print(f"\n📂 Processing: {Path(repo).name}")
        if setup_single_repo(repo, scope, dry_run, local, force, odoo_version, quiet=True):
            success += 1
            print_step("✅", "Done")
        else:
            failed += 1
            print_step("❌", "Failed")

    print(f"\n{'=' * 60}")
    print(f"✅ Completed: {success}/{len(repos)} repositories")
    if failed > 0:
        print(f"❌ Failed: {failed} repositories")
    print(f"{'=' * 60}\n")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Setup solt-pre-commit in client repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single repo setup
  python setup-repo.py /path/to/solt-budget
  python setup-repo.py /path/to/solt-budget --scope full
  python setup-repo.py /path/to/solt-budget --odoo-version 18.0
  python setup-repo.py /path/to/solt-budget --dry-run

  # Batch setup (multiple repos)
  python setup-repo.py --batch repos.txt
  python setup-repo.py --batch repos.txt --dry-run
  python setup-repo.py --batch repos.txt --scope full

  # Monorepo setup
  python setup-repo.py /path/to/solt-addons --local
        """,
    )

    parser.add_argument(
        "path",
        nargs="?",
        help="Path to the target repository (single mode)",
    )
    parser.add_argument(
        "--batch",
        metavar="FILE",
        help="File with list of repository paths (one per line)",
    )
    parser.add_argument(
        "--scope",
        choices=["changed", "full"],
        default="changed",
        help="Validation scope (default: changed)",
    )
    parser.add_argument(
        "--odoo-version",
        choices=["auto", "17.0", "18.0", "19.0"],
        default="auto",
        help="Odoo version (default: auto)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use local hooks config (for monorepo)",
    )
    parser.add_argument(
        "--no-force",
        action="store_true",
        help="Don't overwrite existing files",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.batch and args.path:
        parser.error("Cannot use both --batch and a single path")
    if not args.batch and not args.path:
        parser.error("Either provide a path or use --batch")

    if args.batch:
        setup_batch(
            repos_file=args.batch,
            scope=args.scope,
            dry_run=args.dry_run,
            local=args.local,
            force=not args.no_force,
            odoo_version=args.odoo_version,
        )
    else:
        setup_single_repo(
            target_path=args.path,
            scope=args.scope,
            dry_run=args.dry_run,
            local=args.local,
            force=not args.no_force,
            odoo_version=args.odoo_version,
        )


if __name__ == "__main__":
    main()
