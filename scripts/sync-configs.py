#!/usr/bin/env python3
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Sync configuration files to multiple client repositories.

Usage:
    python sync-configs.py repos.txt
    python sync-configs.py repos.txt --dry-run
    python sync-configs.py repos.txt --files .pylintrc .solt-hooks.yaml
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# In flat structure, all files are in the same directory as the script
SCRIPT_DIR = Path(__file__).parent.absolute()

# Default files to sync
DEFAULT_SYNC_FILES = [
    ".pylintrc",
    "pyproject.toml",
    ".solt-hooks.yaml",
    ".pre-commit-config.yaml",
]

# Files to remove (consolidated into pyproject.toml)
FILES_TO_REMOVE = [
    "ruff.toml",
]

# Map filenames to their source files (flat structure with _ prefix)
FILE_SOURCE_MAP = {
    ".pylintrc": SCRIPT_DIR / "_pylintrc",
    "pyproject.toml": SCRIPT_DIR / "pyproject-base.toml",
    ".solt-hooks.yaml": SCRIPT_DIR / "_solt-hooks.yaml",
    ".pre-commit-config.yaml": SCRIPT_DIR / "_pre-commit-config.yaml",
    ".pre-commit-config-local.yaml": SCRIPT_DIR / "_pre-commit-config-local.yaml",
}


def get_source_path(filename: str) -> Path | None:
    """Get source path for a config file."""
    if filename in FILE_SOURCE_MAP:
        src = FILE_SOURCE_MAP[filename]
        if src.exists():
            return src

    # Fallback: search in same directory with _ prefix
    candidate_with_prefix = SCRIPT_DIR / f"_{filename.lstrip('.')}"
    if candidate_with_prefix.exists():
        return candidate_with_prefix

    # Fallback: search without prefix
    candidate = SCRIPT_DIR / filename
    if candidate.exists():
        return candidate

    return None


def sync_file(src: Path, dest: Path, dry_run: bool = False) -> bool:
    """Sync a single file to destination."""
    if not src.exists():
        print(f"  ⚠️  Source not found: {src}")
        return False

    action = "update" if dest.exists() else "create"

    if dry_run:
        print(f"  📄 Would {action}: {dest.name}")
        return True

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)

    icon = "🔄" if action == "update" else "✅"
    print(f"  {icon} {'Updated' if action == 'update' else 'Created'}: {dest.name}")
    return True


def remove_old_files(repo_path: Path, dry_run: bool = False) -> None:
    """Remove old config files that are now consolidated."""
    for filename in FILES_TO_REMOVE:
        filepath = repo_path / filename
        if filepath.exists():
            if dry_run:
                print(f"  🗑️  Would remove (now in pyproject.toml): {filename}")
            else:
                filepath.unlink()
                print(f"  🗑️  Removed (now in pyproject.toml): {filename}")


def sync_to_repo(
    repo_path: str,
    files: list,
    dry_run: bool = False,
    create_pr: bool = False,
) -> bool:
    """Sync config files to a single repository."""
    repo = Path(repo_path).absolute()

    if not repo.exists():
        print(f"  ❌ Repository not found: {repo}")
        return False

    print(f"\n📂 Syncing to: {repo.name}")

    # Remove old files first
    remove_old_files(repo, dry_run)

    # Sync new files
    for filename in files:
        src = get_source_path(filename)
        if src:
            dest = repo / filename
            sync_file(src, dest, dry_run)
        else:
            print(f"  ⚠️  Source file not found: {filename}")

    if create_pr and not dry_run:
        create_pull_request(repo)

    return True


def create_pull_request(repo_path: Path) -> None:
    """Create a PR with the config changes using GitHub CLI."""
    branch_name = "chore/sync-solt-pre-commit-config"

    try:
        # Check if gh is available
        subprocess.run(["gh", "--version"], capture_output=True, check=True)

        # Create branch
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Add and commit
        subprocess.run(
            ["git", "add", "."],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        subprocess.run(
            ["git", "commit", "-m", "chore: sync solt-pre-commit configuration"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Push and create PR
        subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--title",
                "chore: sync solt-pre-commit configuration",
                "--body",
                "Automated sync of solt-pre-commit configuration files.\n\n"
                "Changes:\n"
                "- Updated pyproject.toml (ruff, black, isort, pytest config)\n"
                "- Updated .pylintrc\n"
                "- Updated .solt-hooks.yaml\n"
                "- Updated .pre-commit-config.yaml\n"
                "- Removed ruff.toml (consolidated into pyproject.toml)",
            ],
            cwd=repo_path,
            check=True,
        )

        print(f"  ✅ Created PR in {repo_path.name}")

    except subprocess.CalledProcessError as e:
        print(f"  ⚠️  Failed to create PR: {e}")
    except FileNotFoundError:
        print("  ⚠️  GitHub CLI (gh) not found")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync configuration files to multiple repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync to all repos in list
  python sync-configs.py repos.txt

  # Preview changes
  python sync-configs.py repos.txt --dry-run

  # Sync specific files only
  python sync-configs.py repos.txt --files .pylintrc pyproject.toml

  # Create PRs automatically
  python sync-configs.py repos.txt --create-pr
        """,
    )

    parser.add_argument(
        "repos_file",
        help="File containing list of repository paths (one per line)",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        default=DEFAULT_SYNC_FILES,
        help=f"Files to sync (default: {DEFAULT_SYNC_FILES})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--create-pr",
        action="store_true",
        help="Create pull requests for each repository",
    )

    args = parser.parse_args()

    repos_file = Path(args.repos_file)
    if not repos_file.exists():
        print(f"❌ Repos file not found: {repos_file}")
        sys.exit(1)

    repos = [
        line.strip()
        for line in repos_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

    print(f"\n{'=' * 60}")
    print(f"🔄 Syncing to {len(repos)} repositories")
    print(f"   Files: {', '.join(args.files)}")
    if args.dry_run:
        print("   Mode: DRY RUN")
    print(f"{'=' * 60}")

    success = 0
    for repo in repos:
        if sync_to_repo(repo, args.files, args.dry_run, args.create_pr):
            success += 1

    print(f"\n{'=' * 60}")
    print(f"✅ Synced to {success}/{len(repos)} repositories")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
