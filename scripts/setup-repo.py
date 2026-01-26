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

Usage (update version only):
    python setup-repo.py --update-only /path/to/odoo-repo
    python setup-repo.py --update-only --batch repos.txt
    python setup-repo.py --update-only --batch repos.txt --version v1.0.1

Usage (pre-commit maintenance):
    python setup-repo.py --clean                    # Clean global pre-commit cache
    python setup-repo.py --reinstall-hooks /path/to/repo
    python setup-repo.py --reinstall-hooks --batch repos.txt
    python setup-repo.py --autoupdate /path/to/repo
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# PATH CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
# Script can be in:
#   - /solt-pre-commit/setup-repo.py (root)
#   - /solt-pre-commit/scripts/setup-repo.py (scripts folder)
# All templates:   /solt-pre-commit/templates/
SCRIPT_DIR = Path(__file__).parent.absolute()

# Detect if script is in scripts/ subdirectory or root
if SCRIPT_DIR.name == "scripts":
    PROJECT_ROOT = SCRIPT_DIR.parent
else:
    PROJECT_ROOT = SCRIPT_DIR

TEMPLATES_DIR = PROJECT_ROOT / "templates"

# Current version of solt-pre-commit
CURRENT_VERSION = "v1.0.1"
SOLT_REPO_URL = "https://github.com/soltein-net/solt-pre-commit"

# ─────────────────────────────────────────────────────────────────────────────
# FILE MAPPINGS (source -> destination)
# ─────────────────────────────────────────────────────────────────────────────
# All source files are in templates/ directory
# Destination files use dot prefix for hidden files
FILES_TO_COPY = [
    # (source_path, destination_relative_path, description)
    (TEMPLATES_DIR / ".pylintrc", ".pylintrc", "Pylint configuration"),
    (TEMPLATES_DIR / "pyproject.toml", "pyproject.toml", "Python project configuration"),
    (TEMPLATES_DIR / ".solt-hooks.yaml", ".solt-hooks.yaml", "Solt hooks configuration"),
]

# Pre-commit config (depends on --local flag)
PRECOMMIT_REMOTE = (TEMPLATES_DIR / ".pre-commit-config.yaml", ".pre-commit-config.yaml", "Pre-commit config (GitHub)")
PRECOMMIT_LOCAL = (
    TEMPLATES_DIR / ".pre-commit-config-local.yaml",
    ".pre-commit-config.yaml",
    "Pre-commit config (local/monorepo)",
)

# GitHub workflow
WORKFLOW_FILE = (
    TEMPLATES_DIR / "github-workflows" / "solt-validate.yml",
    ".github/workflows/solt-validate.yml",
    "GitHub Actions workflow",
)

# Files to remove (old configs consolidated into new structure)
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


def run_precommit_clean(dry_run: bool = False) -> bool:
    """Run pre-commit clean to clear global cache.

    This is a global operation, not per-repo.
    """
    if dry_run:
        print_step("📄", "Would run: pre-commit clean")
        return True

    try:
        print_step("🧹", "Cleaning pre-commit cache...")
        result = subprocess.run(
            ["pre-commit", "clean"],
            check=True,
            capture_output=True,
            text=True,
        )
        print_step("✅", "Pre-commit cache cleaned")
        if result.stdout.strip():
            print(f"      {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print_step("❌", f"Failed to clean cache: {e}")
        return False
    except FileNotFoundError:
        print_step("⚠️ ", "pre-commit not found. Install with: pip install pre-commit")
        return False


def run_precommit_autoupdate(target: Path, repo_url: str = SOLT_REPO_URL, dry_run: bool = False) -> bool:
    """Run pre-commit autoupdate for a specific repo.

    Args:
        target: Path to the repository
        repo_url: URL of the repo to update (default: solt-pre-commit)
        dry_run: If True, only show what would be done
    """
    if dry_run:
        print_step("📄", f"Would run: pre-commit autoupdate --repo {repo_url}")
        return True

    try:
        result = subprocess.run(
            ["pre-commit", "autoupdate", "--repo", repo_url],
            cwd=target,
            check=True,
            capture_output=True,
            text=True,
        )
        # Parse output to show version change
        output = result.stdout.strip()
        if "updating" in output.lower():
            print_step("✅", output.split('\n')[0] if output else "Updated")
        elif "already up to date" in output.lower():
            print_step("✓ ", "Already up to date")
        else:
            print_step("✅", "Autoupdate completed")
        return True
    except subprocess.CalledProcessError as e:
        print_step("❌", f"Autoupdate failed: {e.stderr or e}")
        return False
    except FileNotFoundError:
        print_step("⚠️ ", "pre-commit not found. Install with: pip install pre-commit")
        return False


def reinstall_hooks_single(target_path: str, dry_run: bool = False, quiet: bool = False) -> bool:
    """Reinstall pre-commit hooks in a repository.

    Runs: pre-commit install --install-hooks

    Args:
        target_path: Path to the repository
        dry_run: If True, only show what would be done
        quiet: If True, suppress output
    """
    target = Path(target_path).absolute()

    if not target.exists():
        print_step("❌", f"Target not found: {target}")
        return False

    if not (target / ".pre-commit-config.yaml").exists():
        print_step("⏭️ ", f"No .pre-commit-config.yaml in {target.name}")
        return False

    if dry_run:
        if not quiet:
            print_step("📄", f"Would run: pre-commit install --install-hooks in {target.name}")
        return True

    try:
        subprocess.run(
            ["pre-commit", "install", "--install-hooks"],
            cwd=target,
            check=True,
            capture_output=True,
            text=True,
        )
        if not quiet:
            print_step("✅", f"Hooks reinstalled in {target.name}")
        return True
    except subprocess.CalledProcessError as e:
        print_step("❌", f"Failed to reinstall hooks: {e.stderr or e}")
        return False
    except FileNotFoundError:
        print_step("⚠️ ", "pre-commit not found. Install with: pip install pre-commit")
        return False


def reinstall_hooks_batch(repos_file: str, dry_run: bool = False) -> None:
    """Reinstall pre-commit hooks in multiple repositories."""
    repos_path = Path(repos_file)

    if not repos_path.exists():
        print(f"❌ Repos file not found: {repos_path}")
        sys.exit(1)

    repos = [line.strip() for line in repos_path.read_text().splitlines() if line.strip() and not line.startswith("#")]

    mode_str = "DRY RUN - " if dry_run else ""
    print(f"\n{'=' * 60}")
    print(f"🔄 {mode_str}Reinstalling hooks in {len(repos)} repositories")
    print(f"{'=' * 60}")

    success = 0
    failed = 0

    for repo in repos:
        print(f"\n📂 {Path(repo).name}")
        if reinstall_hooks_single(repo, dry_run, quiet=True):
            success += 1
            print_step("✅", "Done")
        else:
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"✅ Completed: {success}/{len(repos)} repositories")
    if failed > 0:
        print(f"❌ Failed: {failed} repositories")
    print(f"{'=' * 60}\n")


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


def update_version_in_file(filepath: Path, new_version: str, dry_run: bool = False) -> bool:
    """Update solt-pre-commit version in a file.

    Handles multiple version patterns:
    - rev: vX.Y.Z
    - @vX.Y.Z
    """
    if not filepath.exists():
        return False

    content = filepath.read_text()
    original = content

    # Pattern 1: rev: vX.Y.Z (pre-commit config)
    content = re.sub(
        r'(rev:\s*)v\d+\.\d+\.\d+',
        rf'\g<1>{new_version}',
        content
    )

    # Pattern 2: @vX.Y.Z (workflow uses clause)
    content = re.sub(
        r'(@)v\d+\.\d+\.\d+',
        rf'\g<1>{new_version}',
        content
    )

    if content != original:
        if not dry_run:
            filepath.write_text(content)
            print_step("✏️ ", f"Version updated to {new_version} in {filepath.name}")
        else:
            print_step("📄", f"Would update version to {new_version} in {filepath.name}")
        return True

    return False


def update_version_single(
    target_path: str,
    new_version: str = CURRENT_VERSION,
    dry_run: bool = False,
    quiet: bool = False,
) -> bool:
    """Update solt-pre-commit version in a single repository.

    Only updates version references, doesn't copy files.
    """
    target = Path(target_path).absolute()

    if not target.exists():
        print_step("❌", f"Target not found: {target}")
        return False

    files_to_update = [
        target / ".pre-commit-config.yaml",
        target / ".github" / "workflows" / "solt-validate.yml",
    ]

    updated = False
    for filepath in files_to_update:
        if update_version_in_file(filepath, new_version, dry_run):
            updated = True

    if not updated and not quiet:
        print_step("⏭️ ", "No version references found to update")

    return updated


def update_version_batch(
    repos_file: str,
    new_version: str = CURRENT_VERSION,
    dry_run: bool = False,
) -> None:
    """Update solt-pre-commit version in multiple repositories."""
    repos_path = Path(repos_file)

    if not repos_path.exists():
        print(f"❌ Repos file not found: {repos_path}")
        sys.exit(1)

    repos = [line.strip() for line in repos_path.read_text().splitlines() if line.strip() and not line.startswith("#")]

    mode_str = "DRY RUN - " if dry_run else ""
    print(f"\n{'=' * 60}")
    print(f"🔄 {mode_str}Updating version to {new_version} in {len(repos)} repositories")
    print(f"{'=' * 60}")

    success = 0
    skipped = 0

    for repo in repos:
        print(f"\n📂 {Path(repo).name}")
        if update_version_single(repo, new_version, dry_run, quiet=True):
            success += 1
            print_step("✅", f"Updated to {new_version}")
        else:
            skipped += 1
            print_step("⏭️ ", "No changes needed")

    print(f"\n{'=' * 60}")
    print(f"✅ Updated: {success}/{len(repos)} repositories")
    if skipped > 0:
        print(f"⏭️  Skipped: {skipped} repositories (already up to date)")
    print(f"{'=' * 60}\n")


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

    repos = [line.strip() for line in repos_path.read_text().splitlines() if line.strip() and not line.startswith("#")]

    mode_str = "DRY RUN - " if dry_run else ""
    print(f"\n{'=' * 60}")
    print(f"🔄 {mode_str}Batch setup for {len(repos)} repositories")
    print(f"{'=' * 60}")
    print(f"  Scope:        {scope}")
    print(f"  Odoo Version: {odoo_version}")
    print(f"  Mode:         {'local (monorepo)' if local else 'remote (GitHub)'}")
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


def autoupdate_single(target_path: str, dry_run: bool = False, quiet: bool = False) -> bool:
    """Run pre-commit autoupdate for solt-pre-commit in a single repo."""
    target = Path(target_path).absolute()

    if not target.exists():
        print_step("❌", f"Target not found: {target}")
        return False

    if not (target / ".pre-commit-config.yaml").exists():
        print_step("⏭️ ", f"No .pre-commit-config.yaml in {target.name}")
        return False

    return run_precommit_autoupdate(target, SOLT_REPO_URL, dry_run)


def autoupdate_batch(repos_file: str, dry_run: bool = False) -> None:
    """Run pre-commit autoupdate in multiple repositories."""
    repos_path = Path(repos_file)

    if not repos_path.exists():
        print(f"❌ Repos file not found: {repos_path}")
        sys.exit(1)

    repos = [line.strip() for line in repos_path.read_text().splitlines() if line.strip() and not line.startswith("#")]

    mode_str = "DRY RUN - " if dry_run else ""
    print(f"\n{'=' * 60}")
    print(f"🔄 {mode_str}Running autoupdate in {len(repos)} repositories")
    print(f"{'=' * 60}")

    success = 0
    failed = 0

    for repo in repos:
        print(f"\n📂 {Path(repo).name}")
        if autoupdate_single(repo, dry_run, quiet=True):
            success += 1
        else:
            failed += 1

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
  # Full setup (single repo)
  python setup-repo.py /path/to/solt-budget
  python setup-repo.py /path/to/solt-budget --scope full
  python setup-repo.py /path/to/solt-budget --odoo-version 18.0
  python setup-repo.py /path/to/solt-budget --dry-run

  # Full setup (batch)
  python setup-repo.py --batch repos.txt
  python setup-repo.py --batch repos.txt --dry-run

  # Update version only (doesn't copy files)
  python setup-repo.py --update-only /path/to/solt-budget
  python setup-repo.py --update-only --batch repos.txt
  python setup-repo.py --update-only --batch repos.txt --version v1.0.1

  # Pre-commit maintenance
  python setup-repo.py --clean                           # Clean global cache
  python setup-repo.py --reinstall-hooks /path/to/repo   # Reinstall hooks
  python setup-repo.py --reinstall-hooks --batch repos.txt
  python setup-repo.py --autoupdate /path/to/repo        # Run autoupdate
  python setup-repo.py --autoupdate --batch repos.txt

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

    # Update-only mode
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="Only update version references (don't copy files)",
    )
    parser.add_argument(
        "--version",
        default=CURRENT_VERSION,
        help=f"Version to set (default: {CURRENT_VERSION})",
    )

    # Pre-commit maintenance
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean global pre-commit cache",
    )
    parser.add_argument(
        "--reinstall-hooks",
        action="store_true",
        help="Reinstall pre-commit hooks",
    )
    parser.add_argument(
        "--autoupdate",
        action="store_true",
        help="Run pre-commit autoupdate for solt-pre-commit",
    )

    args = parser.parse_args()

    # Handle global clean (no path required)
    if args.clean:
        run_precommit_clean(args.dry_run)
        return

    # Handle reinstall-hooks
    if args.reinstall_hooks:
        if args.batch:
            reinstall_hooks_batch(args.batch, args.dry_run)
        elif args.path:
            reinstall_hooks_single(args.path, args.dry_run)
        else:
            parser.error("--reinstall-hooks requires a path or --batch")
        return

    # Handle autoupdate
    if args.autoupdate:
        if args.batch:
            autoupdate_batch(args.batch, args.dry_run)
        elif args.path:
            autoupdate_single(args.path, args.dry_run)
        else:
            parser.error("--autoupdate requires a path or --batch")
        return

    # Handle update-only mode
    if args.update_only:
        if args.batch:
            update_version_batch(args.batch, args.version, args.dry_run)
        elif args.path:
            update_version_single(args.path, args.version, args.dry_run)
        else:
            parser.error("--update-only requires a path or --batch")
        return

    # Validate arguments for setup mode
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
