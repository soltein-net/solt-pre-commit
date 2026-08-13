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


def get_current_version() -> str:
    """The tag this checkout of solt-pre-commit corresponds to.

    pyproject.toml's version is now dynamic (derived from the git tag via
    setuptools_scm), so there's no static "version = ..." line left to parse
    here - ask git directly instead, which is the same underlying source of
    truth setuptools_scm itself uses. --abbrev=0 matters: plain `git
    describe` appends a "-<n>-g<sha>" suffix when HEAD is past the last tag,
    which would stamp an unresolvable non-existent ref into every consuming
    repo's rev:/@ref pins - --abbrev=0 always returns just the nearest real
    tag name (e.g. "v1.2.0"), matching this function's previous behavior of
    reporting the last released version even mid-development on the next one.
    """
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"Could not determine current version via `git describe --tags` in {PROJECT_ROOT}: {result.stderr.strip()}")
    return result.stdout.strip()


# Current version of solt-pre-commit - always derived from pyproject.toml so
# it can't drift behind actual releases (see CHANGELOG for the v1.1.0 vs
# v1.2.0 drift this replaced).
CURRENT_VERSION = get_current_version()
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
    (TEMPLATES_DIR / "CONTRIBUTING-template.md", "CONTRIBUTING.md", "Contributor guide (dev setup, branch naming, optional AI tooling)"),
]

# Files the repo owns once they exist: seeded from the template on first setup,
# never overwritten afterwards. .solt-hooks.yaml announces itself as the place
# "users can override" the defaults, and copying it with force would silently
# discard exactly the overrides it invites - disabled_checks, protected
# branches, and the sibling_repos declaration CI depends on. Regeneration must
# be able to run on a configured repo without destroying its configuration.
FILES_TO_CREATE_IF_MISSING = [
    (TEMPLATES_DIR / ".solt-hooks.yaml", ".solt-hooks.yaml", "Solt hooks configuration"),
]

# Directories copied wholesale (source_path, destination_relative_path, description).
# Only .claude/skills is copied under .claude/ (not the whole .claude/ tree) so a
# repo's own .claude/agents, .claude/commands, or settings are never touched.
# Deliberately NOT distributing addyosmani/agent-skills here (removed - see
# CHANGELOG): that's a third-party AI-agent tooling product with its own
# install path (Claude Code's `/plugin marketplace add` + `/plugin install`),
# not something an Odoo-module CI/QA tool should be vendoring and keeping in
# sync. GitNexus (unrelated, this repo's own code-intelligence skill) still
# ships via the entry below.
DIRECTORIES_TO_COPY = [
    (TEMPLATES_DIR / ".claude" / "skills", ".claude/skills", "GitNexus skill"),
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


def copy_tree(src: Path, dest: Path, dry_run: bool = False, force: bool = True) -> bool:
    """Copy a directory tree to destination, preserving symlinks."""
    if not src.exists():
        print_step("⚠️ ", f"Source not found: {src}")
        return False

    if dest.exists() and not force:
        print_step("⏭️ ", f"Skipped (exists): {dest}")
        return False

    action = "overwrite" if dest.exists() else "create"

    if dry_run:
        print_step("📁", f"Would {action} directory: {dest}")
        return True

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest, dirs_exist_ok=True, symlinks=True)
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
            print_step("✅", output.split("\n")[0] if output else "Updated")
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

    # Pattern 1: rev: vX.Y.Z, but only the rev line immediately under the
    # solt-pre-commit repo entry - .pre-commit-config.yaml has other repos
    # (ruff-pre-commit, pylint-odoo, pre-commit-hooks, ...) each with their
    # own unrelated "rev: vX.Y.Z" line that must NOT be touched here.
    content = re.sub(
        r"(- repo:\s*https://github\.com/soltein-net/solt-pre-commit\s*\n\s*rev:\s*)v\d+\.\d+\.\d+",
        rf"\g<1>{new_version}",
        content,
    )

    # Pattern 2: @vX.Y.Z, but only on a soltein-net/solt-pre-commit reference
    # (workflow `uses:` clause) - other actions/reusable workflows pinned by
    # @vX.Y.Z in the same file are a different project's version, not ours.
    content = re.sub(
        r"(soltein-net/solt-pre-commit(?:/[\w./-]+)?@)v\d+\.\d+\.\d+",
        rf"\g<1>{new_version}",
        content,
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

    # Never with `force`, and refreshed rather than replaced when it already
    # exists: see FILES_TO_CREATE_IF_MISSING.
    for src, dest_rel, _description in FILES_TO_CREATE_IF_MISSING:
        dest = target / dest_rel
        existed = dest.exists()
        if src.exists() and copy_file(src, dest, dry_run, force=False):
            copied += 1
        elif existed and src.exists():
            refresh_solt_hooks(dest, src.read_text(), dry_run)

    # Copy directory trees (agent skills)
    for src, dest_rel, _description in DIRECTORIES_TO_COPY:
        dest = target / dest_rel

        if copy_tree(src, dest, dry_run, force):
            copied += 1
        else:
            failed += 1

    # Stamp the current solt-pre-commit version onto the just-copied config,
    # in case the template's own hardcoded rev (templates/.pre-commit-config.yaml)
    # has drifted behind CURRENT_VERSION since it was last edited.
    update_version_single(str(target), CURRENT_VERSION, dry_run, quiet=True)

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

    # NEW in v1.1.0: Auto-detect modules and generate workflow
    if not quiet:
        print_step("🔍", "Detecting modules and dependencies...")

    detected_modules = detect_modules(target)
    detected_odoo_version = (
        odoo_version if odoo_version != "auto" else detect_odoo_version_from_branch(repo_path=target)
    )
    detected_sibling_repos = detect_sibling_repos(detected_modules, target)  # Pass repo_path, not version

    if not quiet and detected_modules:
        print_step("✅", f"Found {len(detected_modules)} module(s): {', '.join(sorted(detected_modules.keys()))}")
        if detected_sibling_repos:
            print_step("📦", f"External repos: {len(detected_sibling_repos)}")

    # Generate workflow file
    if generate_workflow_file(target, detected_modules, detected_odoo_version, detected_sibling_repos, dry_run):
        copied += 1
    else:
        failed += 1

    # Inject/create badges in README
    github_org = "soltein-net"  # TODO: detect from git remote
    inject_badges_to_readme(
        target,
        target.name,
        github_org=github_org,
        odoo_version=detected_odoo_version,
        dry_run=dry_run,
    )

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


# ─────────────────────────────────────────────────────────────────────────────
# MODULE & DEPENDENCY DETECTION (NEW in v1.1.0)
# ─────────────────────────────────────────────────────────────────────────────


def detect_modules(repo_path: Path) -> dict[str, dict]:
    """Scan repository for Odoo modules and return {module_name: info}."""
    modules = {}
    repo_path = Path(repo_path).resolve()

    for manifest_file in repo_path.rglob("__manifest__.py"):
        module_dir = manifest_file.parent
        module_name = module_dir.name

        if module_name.startswith(".") or module_name in ("__pycache__",):
            continue

        try:
            import ast

            manifest_data = ast.literal_eval(manifest_file.read_text())
            if isinstance(manifest_data, dict):
                modules[module_name] = {
                    "path": module_dir,
                    "version": manifest_data.get("version"),
                    "depends": manifest_data.get("depends", []),
                    "summary": manifest_data.get("summary", module_name),
                    "external_dependencies": manifest_data.get("external_dependencies", {}),
                }
        except (SyntaxError, ValueError):
            pass

    return modules


def detect_odoo_version_from_branch(branch_name: str | None = None, repo_path: Path | None = None) -> str:
    """Detect Odoo version from branch name or manifest."""
    if branch_name:
        match = re.search(r"(\d+\.\d+)", branch_name)
        if match:
            return match.group(1)

    if repo_path:
        modules = detect_modules(repo_path)
        for module_info in modules.values():
            version_str = module_info.get("version", "")
            match = re.search(r"(\d+\.\d+)", version_str)
            if match:
                return match.group(1)

    return "17.0"


def get_python_version(odoo_version: str) -> str:
    """Map Odoo version to the Python version we actually build/test against.

    Not Odoo's documented *minimum* (17.0-19.0's minimum is 3.10) - that
    minimum maps to gevent's "Jammy" pin in Odoo's own requirements.txt,
    which no longer builds on current GitHub-hosted runners (ubuntu-latest
    moved to Noble/24.04). 3.10 also isn't what any real environment here
    runs. Testing at the documented minimum instead of the version we deploy
    buys no real coverage and reliably breaks CI on an unrelated toolchain
    mismatch, so this maps to what's actually deployed.

    19.0 is on 3.13. Two reasons it is not lower: below Python 3.12 Odoo's own
    requirements.txt holds cryptography at 3.4.8 and pyOpenSSL at 21.0.0, both
    from 2021, so generating CI under that boundary validates every build
    against a cryptography nothing deploys - silently, until the day an addon
    needs a modern one. And 3.13 costs nothing over 3.12 in coverage: checked
    by evaluating every marker in Odoo 19's requirements.txt, both resolve 44
    of 47 packages, the difference being Odoo's own PyPDF2 -> pypdf swap at the
    3.13 boundary plus a Windows-only entry. Nothing is left without a version.
    """
    mapping = {
        "17.0": "3.11",
        "18.0": "3.11",
        "19.0": "3.13",
        "20.0": "3.13",  # Above its 3.12 minimum: nothing is deployed yet to override with, so
                         # it follows 19.0 rather than sitting a Python version behind the release
                         # before it - which is the shape that reads as a mistake and eventually is one.
    }
    if odoo_version not in mapping:
        raise ValueError(
            f"No known Python version for Odoo {odoo_version!r}. Add it to "
            "get_python_version()'s mapping in setup-repo.py before generating "
            "a workflow/README for this version - silently guessing here would "
            "bake a possibly-wrong Python version into generated CI, and the "
            "mismatch wouldn't surface until a full, expensive CI run fails on "
            "what looks like an unrelated dependency error."
        )
    return mapping[odoo_version]


def get_git_branch(repo_path: Path) -> str:
    """Get current git branch of repo, for use as the sibling-repos ref.

    Returns:
    - Feature/hotfix branches (feature/17.0-..., hotfix/17.0-...) → extract version (17.0)
    - Version branches (17.0, 18.0) → return exact branch
    - Fallback → extract from manifest

    Scope note: this is ONLY for per-module PR/branch CI (this repo's own
    solt-validate.yml, testing "does my branch work against sibling repos'
    version branch"). It intentionally does NOT special-case release tags:
    - Release tags (17.0-2026.07.17-00) are created only on the `soltein`
      super-repo, never on individual module repos - so `git describe --tags`
      here will never match one; there is nothing to special-case.
    - Even if it could match, falling back to the version branch would be
      WRONG: a super-repo release pins each submodule to whatever commit SHA
      it happened to have checked out (e.g. an unmerged hotfix branch), not
      necessarily anything reachable from that module's version branch.
    Release/regression testing of "exactly what a release pins" is a
    different problem, solved at the super-repo level (checkout the release
    tag with `submodules: recursive` - that alone reproduces the exact pinned
    commits, no branch/tag guessing needed). See docs/RELEASE-TAG-STRATEGY.md.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()

            # If on a feature/release branch, extract version
            # Examples: 'feature/17.0-first-test' → '17.0', 'hotfix/17.0-xyz' → '17.0'
            if "/" in branch:
                match = re.search(r"(\d+\.\d+)", branch)
                if match:
                    return match.group(1)

            # Otherwise use exact branch name ('17.0', '18.0', etc.)
            return branch
    except (subprocess.TimeoutExpired, Exception):
        pass

    # Fallback: extract from manifest
    return detect_odoo_version_from_branch(repo_path)


def generate_module_table(modules: dict[str, dict]) -> str:
    """Generate markdown table rows for modules."""
    if not modules:
        return "| (none detected) | – |"

    rows = []
    for name in sorted(modules.keys()):
        summary = modules[name].get("summary", name)
        rows.append(f"| `{name}` | {summary} |")

    return "\n".join(rows)


def generate_dependencies_string(modules: dict[str, dict]) -> str:
    """Extract external dependencies from modules."""
    odoo_core = {
        "base",
        "crm",
        "sale",
        "purchase",
        "account",
        "stock",
        "hr",
        "web",
        "website",
        "project",
        "mail",
        "calendar",
        "digest",
        "survey",
        "sale_crm",
        "web_editor",
    }

    all_deps = set()
    for module_info in modules.values():
        all_deps.update(module_info.get("depends", []))

    # Filter out core Odoo and local modules
    external = [d for d in sorted(all_deps) if d not in odoo_core and d not in modules]
    return ", ".join(external) if external else "base"





def _remote_org_repo(repo_dir: Path) -> str | None:
    """Resolve "<org>/<repo>" from a checkout's own origin remote."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", result.stdout.strip())
    return match.group(1) if match else None


def discover_workspace_repos(repo_path: Path) -> dict[str, Path]:
    """Find the checkouts sitting alongside this one, as {org/repo: path}.

    Two layouts exist and they cannot be probed the same way.

    A repo checked out as a **git submodule** has a superproject, and that
    superproject's .gitmodules holds each sibling's real remote URL and the
    path it belongs at - authoritative, and it also states which checkouts are
    part of the set rather than merely nearby.

    A **flat workspace** - sibling directories under a plain folder, no git
    relationship between them - has no such record. `--show-superproject-working-tree`
    answers nothing there, which is why the detection this replaced silently
    found no siblings at all in exactly the layout it was being run in. The
    only source left is each directory's own origin remote.

    Used to *seed* a declaration a human then reviews, never to generate the
    workflow directly: whatever is found depends on what happens to be cloned,
    and that is acceptable in a file under review and not in one that is
    committed and shared.
    """
    found: dict[str, Path] = {}

    superproject = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-superproject-working-tree"],
            cwd=repo_path, capture_output=True, text=True, check=True,
        )
        superproject = Path(result.stdout.strip()) if result.stdout.strip() else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        superproject = None

    if superproject and (superproject / ".gitmodules").is_file():
        try:
            result = subprocess.run(
                ["git", "config", "--file", str(superproject / ".gitmodules"), "--get-regexp", r"^submodule\..*\.(path|url)$"],
                capture_output=True, text=True, check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            result = None
        if result:
            paths, urls = {}, {}
            for line in result.stdout.splitlines():
                key, _, value = line.partition(" ")
                name = key[len("submodule."):].rsplit(".", 1)[0]
                (paths if key.endswith(".path") else urls)[name] = value
            for name, rel in paths.items():
                match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", urls.get(name, ""))
                candidate = superproject / rel
                if match and candidate.is_dir() and candidate.resolve() != repo_path.resolve():
                    found[match.group(1)] = candidate
        return found

    for candidate in sorted(repo_path.parent.iterdir()):
        if not candidate.is_dir() or candidate.resolve() == repo_path.resolve():
            continue
        if not (candidate / ".git").exists():
            continue
        org_repo = _remote_org_repo(candidate)
        if org_repo:
            found[org_repo] = candidate
    return found



def _yaml_block(text: str, key: str) -> tuple[int, int] | None:
    """Locate a top-level key's lines, comments immediately above included.

    The comments come along because they are the reason the value is what it
    is - a repo that annotates why it declares a sibling loses the annotation
    if only the value travels, and the next person to read the refreshed file
    sees a bare entry with no explanation.
    """
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.startswith(f"{key}:"):
            continue
        start = index
        while start and (lines[start - 1].lstrip().startswith("#") or not lines[start - 1].strip()):
            if not lines[start - 1].strip():
                break
            start -= 1
        end = index + 1
        while end < len(lines) and (lines[end].startswith((" ", "\t", "-")) or not lines[end].strip()):
            if not lines[end].strip():
                break
            end += 1
        return start, end
    return None



def refresh_solt_hooks(config_file: Path, template_text: str, dry_run: bool = False) -> None:
    """Bring an existing config up to the current template, keeping its answers.

    Neither of the two obvious behaviours is right. Overwriting discards
    exactly the overrides the file invites - it announces itself as the place
    "users can override", and a full setup used to silently reset every one of
    them. Never touching it freezes the file at whatever template version
    created it, so new settings and the documentation explaining them never
    reach a repo that is already configured, and the only way to see them is to
    delete the file and diff.

    So: the template supplies the structure and the prose, the repo supplies
    the answers. Every key whose value differs from the template default is
    carried across verbatim, with its comments.
    """
    try:
        import yaml
    except ImportError:
        return

    current_text = config_file.read_text()
    try:
        current = yaml.safe_load(current_text) or {}
        defaults = yaml.safe_load(template_text) or {}
    except yaml.YAMLError as exc:
        print_step("⚠️ ", f"Leaving {config_file.name} alone, it does not parse: {exc}")
        return

    overrides = [key for key in current if current.get(key) != defaults.get(key)]
    if template_text == current_text:
        return

    merged = template_text
    carried, lost = [], []
    for key in overrides:
        source = _yaml_block(current_text, key)
        target = _yaml_block(merged, key)
        if not source:
            continue
        block = "".join(current_text.splitlines(keepends=True)[source[0]:source[1]])
        if target:
            lines = merged.splitlines(keepends=True)
            merged = "".join(lines[:target[0]]) + block + "".join(lines[target[1]:])
        else:
            merged = merged.rstrip() + "\n\n" + block
        carried.append(key)

    lost = [key for key in overrides if key not in carried]
    if dry_run:
        print_step("📄", f"Would refresh {config_file.name}, keeping: {', '.join(carried) or 'nothing'}")
        return

    config_file.write_text(merged)
    print_step("🔄", f"Refreshed {config_file.name}" + (f", kept: {', '.join(carried)}" if carried else ""))
    for key in lost:
        print_step("⚠️ ", f"Could not carry over '{key}' - check it by hand")



def detect_sibling_repos(modules: dict[str, dict], repo_path: Path) -> list[str]:
    """The external repos CI must clone, deduced from what this repo depends on.

    Transitively, because of an incident that must not repeat: a repo depended
    on a module in a second repo whose own manifest depended on a module in a
    third. Cloning only the first hop gets that repo checked out and then fails
    installing it, in a real CI run rather than here.

    A dependency satisfied by a module of this repo is never a sibling. The
    hand-written table this replaced got that wrong most visibly, listing the
    same modules as local and external in one generated file - it described the
    17.0 topology, where the addons live in separate repos, and was applied
    unchanged to 19.0, where they were consolidated into one. It also kept a
    list of client repo names inside a public repository.

    What is found depends on what is cloned beside this repo, so a workspace
    missing a checkout yields a workflow missing that repo. That is visible in
    the diff of the regenerated file, which is the review this relies on.
    """
    workspace = discover_workspace_repos(repo_path)
    provider: dict[str, str] = {}
    depends_of: dict[str, list[str]] = {}
    for org_repo, path in workspace.items():
        for name, info in detect_modules(path).items():
            provider.setdefault(name, org_repo)
            depends_of.setdefault(name, info.get("depends", []))

    seen: set[str] = set()
    worklist = [dep for info in modules.values() for dep in info.get("depends", [])]
    while worklist:
        dep = worklist.pop()
        if dep in seen or dep in modules:
            continue
        seen.add(dep)
        worklist.extend(depends_of.get(dep, []))

    target_ref = get_git_branch(repo_path)
    needed = sorted({provider[dep] for dep in seen if dep in provider})
    return [f"{repo}@{target_ref}:{repo.split('/')[-1]}" for repo in needed]


# Postgres extension -> service image that provides it. vchord's image is
# listed first and used whenever present since VectorChord's own extension
# install CASCADEs into pgvector - one image then covers both requirements.
POSTGRES_EXTENSION_IMAGES = {
    "vchord": "tensorchord/vchord-postgres:pg15-v1.1.1",
    "vector": "pgvector/pgvector:pg15",
}
DEFAULT_POSTGRES_IMAGE = "postgres:15"


def detect_postgres_image(modules: dict[str, dict]) -> str:
    """Pick the CI Postgres service image from modules' declared needs.

    Single source of truth is each module's own manifest, same as
    solt-check-requirements does for Python deps: a module that needs a
    Postgres extension (e.g. llm_pgvector needing `vector`) declares it under
    `external_dependencies.postgresql`, and this picks the image that
    provides it - instead of a hand-edited workflow line that regeneration
    would otherwise silently overwrite back to the plain default.
    """
    extensions = set()
    for module_info in modules.values():
        extensions.update(module_info.get("external_dependencies", {}).get("postgresql", []))

    for extension, image in POSTGRES_EXTENSION_IMAGES.items():
        if extension in extensions:
            return image

    return DEFAULT_POSTGRES_IMAGE


def generate_workflow_file(
    repo_path: Path,
    modules: dict[str, dict],
    odoo_version: str,
    sibling_repos: list[str],
    dry_run: bool = False,
) -> bool:
    """Generate .github/workflows/solt-validate.yml from template."""
    workflow_dest = repo_path / ".github" / "workflows" / "solt-validate.yml"
    workflow_template = TEMPLATES_DIR / "github-workflows" / "solt-validate.yml"

    if not workflow_template.exists():
        print_step("⚠️ ", f"Template not found: {workflow_template}")
        return False

    try:
        content = workflow_template.read_text()

        # Replace placeholders
        python_version = get_python_version(odoo_version)
        module_names = " ".join(sorted(modules.keys()))

        replacements = {
            "{{ MODULES }}": module_names or "unknown",
            "{{ SIBLING_REPOS }}": " ".join(sibling_repos) if sibling_repos else "",
            "{{ ODOO_VERSION }}": odoo_version,
            "{{ PYTHON_VERSION }}": python_version,
            "{{ SOLT_VERSION }}": CURRENT_VERSION,
            "{{ POSTGRES_IMAGE }}": detect_postgres_image(modules),
        }

        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)

        if dry_run:
            print_step("📄", f"Would create: {workflow_dest}")
            return True

        workflow_dest.parent.mkdir(parents=True, exist_ok=True)
        workflow_dest.write_text(content)
        print_step("✅", f"Generated: {workflow_dest}")
        return True

    except Exception as e:
        print_step("❌", f"Error generating workflow: {e}")
        return False


def inject_badges_to_readme(
    repo_path: Path,
    repo_name: str,
    github_org: str = "soltein-net",
    gist_owner: str = "SolteinCorp",
    gist_id: str = "147d543a086f6735d1ffa02172766e86",
    odoo_version: str = "17.0",
    dry_run: bool = False,
) -> bool:
    """Inject badges into README or create minimal README if none exists."""
    readme_path = repo_path / "README.md"
    badges_template = TEMPLATES_DIR / "BADGES-TEMPLATE.md"

    if not badges_template.exists():
        print_step("⚠️ ", f"Badge template not found: {badges_template}")
        return False

    try:
        badges_content = badges_template.read_text()

        # Replace badge placeholders
        badge_replacements = {
            "{{ GITHUB_ORG }}": github_org,
            "{{ REPO_NAME }}": repo_name,
            "{{ GIST_OWNER }}": gist_owner,
            "{{ GIST_ID }}": gist_id,
            "{{ ODOO_VERSION }}": odoo_version,
        }

        for placeholder, value in badge_replacements.items():
            badges_content = badges_content.replace(placeholder, value)

        if readme_path.exists():
            # Inject badges into existing README
            content = readme_path.read_text()

            # Check if badges already exist
            if "SOLTEIN_BADGES_START" in content:
                # Replace existing badges
                import re

                content = re.sub(
                    r"<!-- SOLTEIN_BADGES_START -->.*?<!-- SOLTEIN_BADGES_END -->",
                    badges_content,
                    content,
                    flags=re.DOTALL,
                )
            else:
                # Prepend badges to top
                content = badges_content + "\n\n" + content

            if dry_run:
                print_step("📄", f"Would update: {readme_path}")
                return True

            readme_path.write_text(content)
            print_step("✅", f"Updated: {readme_path}")
        else:
            # Create minimal README from template
            minimal_template = TEMPLATES_DIR / "README-REPO-template.md"
            if minimal_template.exists():
                content = minimal_template.read_text()

                # Fill placeholders
                modules = detect_modules(repo_path)
                module_table = generate_module_table(modules)
                dependencies = generate_dependencies_string(modules)
                python_version = get_python_version(odoo_version)

                readme_replacements = {
                    "{{ GITHUB_ORG }}": github_org,
                    "{{ REPO_NAME }}": repo_name,
                    "{{ REPO_DESCRIPTION }}": f"Odoo {odoo_version} modules",
                    "{{ MODULE_TABLE }}": module_table,
                    "{{ ODOO_VERSION }}": odoo_version,
                    "{{ PYTHON_VERSION }}": python_version,
                    "{{ DEPENDENCIES }}": dependencies,
                    "{{ GIST_OWNER }}": gist_owner,
                    "{{ GIST_ID }}": gist_id,
                }

                for placeholder, value in readme_replacements.items():
                    content = content.replace(placeholder, value)

                # Prepend badges
                content = badges_content + "\n\n" + content

                if dry_run:
                    print_step("📄", f"Would create: {readme_path}")
                    return True

                readme_path.write_text(content)
                print_step("✅", f"Created: {readme_path}")
            else:
                # Just inject badges if no template
                if dry_run:
                    print_step("📄", f"Would create: {readme_path}")
                    return True

                readme_path.write_text(badges_content + "\n\n# Your Repository\n\nAdd content here.\n")
                print_step("✅", f"Created minimal: {readme_path}")

        return True

    except Exception as e:
        print_step("❌", f"Error with badges/README: {e}")
        return False


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

    # New in v1.1.0: Auto-detection and generation
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Regenerate workflow file from detected modules (with --update-only)",
    )
    parser.add_argument(
        "--badge-only",
        action="store_true",
        help="Only inject/create badges in README (no other setup)",
    )
    parser.add_argument(
        "--inject-badges",
        action="store_true",
        help="Inject badges into existing README",
    )
    parser.add_argument(
        "--gist-id",
        default="147d543a086f6735d1ffa02172766e86",
        help="GitHub Gist ID for badges (default: SolteinCorp gist)",
    )
    parser.add_argument(
        "--gist-owner",
        default="SolteinCorp",
        help="GitHub Gist owner (default: SolteinCorp)",
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
        if args.regenerate:
            # Update-only with regenerate: update version AND regenerate workflow
            if args.batch:
                for repo_line in Path(args.batch).read_text().splitlines():
                    repo = repo_line.strip()
                    if repo and not repo.startswith("#"):
                        repo_path = Path(repo).resolve()
                        modules = detect_modules(repo_path)
                        odoo_version = detect_odoo_version_from_branch(repo_path=repo_path)
                        sibling_repos = detect_sibling_repos(modules, repo_path)  # Pass repo_path, not version
                        generate_workflow_file(repo_path, modules, odoo_version, sibling_repos, args.dry_run)
                        update_version_single(repo, args.version, args.dry_run)
                        print_step("✅", f"Regenerated: {repo}")
            elif args.path:
                repo_path = Path(args.path).resolve()
                modules = detect_modules(repo_path)
                odoo_version = detect_odoo_version_from_branch(repo_path=repo_path)
                sibling_repos = detect_sibling_repos(modules, repo_path)  # Pass repo_path, not version
                generate_workflow_file(repo_path, modules, odoo_version, sibling_repos, args.dry_run)
                update_version_single(args.path, args.version, args.dry_run)
                print_step("✅", f"Regenerated: {args.path}")
            else:
                parser.error("--update-only --regenerate requires a path or --batch")
        else:
            # Standard update-only (just version pins)
            if args.batch:
                update_version_batch(args.batch, args.version, args.dry_run)
            elif args.path:
                update_version_single(args.path, args.version, args.dry_run)
            else:
                parser.error("--update-only requires a path or --batch")
        return

    # Handle badge-only mode (NEW in v1.1.0)
    if args.badge_only or args.inject_badges:
        if args.path:
            inject_badges_to_readme(
                Path(args.path),
                Path(args.path).name,
                github_org="soltein-net",
                gist_owner=args.gist_owner,
                gist_id=args.gist_id,
                odoo_version=detect_odoo_version_from_branch(repo_path=Path(args.path)),
                dry_run=args.dry_run,
            )
            print_step("✅", "Badges processed")
        else:
            parser.error("--badge-only/--inject-badges requires a path")
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
