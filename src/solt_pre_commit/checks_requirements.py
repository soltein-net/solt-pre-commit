# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Verify (or update) a repo's root requirements.txt against its addons' manifests.

The packages come from every installable addon's `__manifest__.py`
`external_dependencies["python"]`, read with manifestoo
(https://github.com/acsone/manifestoo) - the declaration Odoo itself checks,
version specifier included, before installing or upgrading a module.
requirements.txt lists each of those packages once and is where their
versions are set:

- a package a manifest declares without a version may carry any version in
  requirements.txt;
- a package a manifest declares with a version carries exactly that one;
- a line for a package no manifest declares is accepted when it states a
  version - a pin on a dependency of a dependency, such as one lifting a
  version Odoo's own requirements lock - and is out of sync without one.

`--fix` adds the declared packages that are missing, drops the unversioned
lines nobody declares, and keeps every version requirements.txt sets, along
with the comment on its line.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

HEADER = (
    "# Packages come from the addon manifests' external_dependencies.python;"
    " their versions are set here.\n"
    "# Run `solt-check-requirements --fix` after changing a manifest - it keeps these versions.\n"
)

INLINE_COMMENT = re.compile(r"(^|\s+)#.*$")


class RequirementsConflictError(Exception):
    """Two addons in the same repo declare incompatible constraints for the same package."""

    def __init__(self, conflicts):
        self.conflicts = conflicts
        message = "; ".join(f"{name}: {a!r} vs {b!r}" for name, a, b in conflicts)
        super().__init__(message)


def _repo_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


def _manifestoo_external_dependencies(repo_root: Path) -> list[str]:
    """Raw, one-per-line `python` external_dependencies for every installable
    addon manifestoo finds under repo_root, exactly as declared (not yet
    deduped/normalized - two addons may legitimately declare the same
    package with different specifiers)."""
    result = subprocess.run(
        [
            "manifestoo",
            "-d",
            str(repo_root),
            "--select-found",
            "list-external-dependencies",
            "python",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _canonical_name(name: str) -> str:
    return name.lower().replace("_", "-")


def normalize(raw_lines: list[str]) -> list[str]:
    """Dedupe declarations by canonical package name, sorted for a stable diff.

    Raises RequirementsConflictError if two addons declare different, non-empty
    version specifiers for the same package - that needs a human to resolve,
    not a silent pick.
    """
    by_name: dict[str, str] = {}
    conflicts = []
    for line in raw_lines:
        try:
            req = Requirement(line)
        except InvalidRequirement:
            # Not a real PEP 508 requirement (e.g. a bare binary/tool name
            # manifestoo still listed) - keep it verbatim, keyed on itself.
            by_name.setdefault(line, line)
            continue

        key = _canonical_name(req.name)
        existing = by_name.get(key)
        if existing is None:
            by_name[key] = line
            continue
        if existing == line:
            continue

        existing_req = Requirement(existing)
        if existing_req.specifier == req.specifier:
            pass  # same constraint (including "both bare") - nothing to reconcile
        elif not existing_req.specifier:
            by_name[key] = line  # existing was bare, this one is more informative
        elif not req.specifier:
            pass  # this one is bare, existing already has a specifier - keep it
        else:
            conflicts.append((key, existing, line))

    if conflicts:
        raise RequirementsConflictError(conflicts)

    return sorted(by_name.values(), key=str.lower)


def render(lines: list[str]) -> str:
    body = "\n".join(lines)
    return HEADER + "\n" + body + "\n" if lines else HEADER


def _requirement_lines(text: str) -> list[tuple[str, str, Requirement | None]]:
    """Return (line, line without its comment, parsed requirement or None) for each
    requirement line of a requirements.txt, skipping blank and comment-only lines.
    The comment is what pip ignores: a `#` at the start or after whitespace."""
    requirement_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        bare_line = INLINE_COMMENT.sub("", line).strip()
        if not bare_line:
            continue
        try:
            requirement = Requirement(bare_line)
        except InvalidRequirement:
            requirement = None
        requirement_lines.append((line, bare_line, requirement))
    return requirement_lines


def parse_requirement_set(text: str) -> set[str]:
    """Reduce a requirements.txt's content to a comparable set of canonical
    `name<specifier>` entries - ignoring comments, blank lines, and line
    order, so an existing hand-written file with a different header/ordering
    still compares equal when its actual dependencies already match."""
    entries = set()
    for _line, bare_line, requirement in _requirement_lines(text):
        if requirement is None:
            entries.add(bare_line.lower())
        else:
            entries.add(f"{_canonical_name(requirement.name)}{requirement.specifier}")
    return entries


def reconcile(declared_lines: list[str], existing_text: str) -> list[str]:
    """Return the lines requirements.txt should hold, given the normalized
    manifest declarations and the file's current content.

    Each declared package gets one line: the one the file already has for it,
    unless the declaration states a version that line does not. Lines for
    packages nobody declares are kept when they state a version. Sorted for a
    stable diff.
    """
    existing_by_name = {}
    for line, _bare_line, requirement in _requirement_lines(existing_text):
        if requirement is not None:
            existing_by_name[_canonical_name(requirement.name)] = (line, requirement)

    reconciled_lines = []
    declared_names = set()
    for declared_line in declared_lines:
        try:
            declared_requirement = Requirement(declared_line)
        except InvalidRequirement:
            reconciled_lines.append(declared_line)
            continue
        name = _canonical_name(declared_requirement.name)
        declared_names.add(name)
        existing_line, existing_requirement = existing_by_name.get(name, (None, None))
        keeps_existing_line = existing_requirement is not None and (
            not declared_requirement.specifier or existing_requirement.specifier == declared_requirement.specifier
        )
        reconciled_lines.append(existing_line if keeps_existing_line else declared_line)

    for name, (existing_line, existing_requirement) in existing_by_name.items():
        if name not in declared_names and existing_requirement.specifier:
            reconciled_lines.append(existing_line)

    return sorted(reconciled_lines, key=str.lower)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Update requirements.txt in place instead of just checking it, keeping the versions it sets.",
    )
    parser.add_argument(
        "--path",
        default=".",
        help="Directory inside the repo to check (default: cwd). The repo root is "
        "resolved from here via `git rev-parse --show-toplevel`.",
    )
    args = parser.parse_args()

    start = Path(args.path).resolve()
    try:
        repo_root = _repo_root(start)
    except subprocess.CalledProcessError:
        print(f"{start} is not inside a git repository", file=sys.stderr)
        sys.exit(1)

    try:
        raw_declarations = _manifestoo_external_dependencies(repo_root)
    except FileNotFoundError:
        print(
            "manifestoo not found - install it (pip install manifestoo) to run this check",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"manifestoo failed:\n{exc.stderr}", file=sys.stderr)
        sys.exit(1)

    try:
        declared_lines = normalize(raw_declarations)
    except RequirementsConflictError as exc:
        print(
            "Conflicting external_dependencies across addons in this repo - resolve manually:",
            file=sys.stderr,
        )
        for name, a, b in exc.conflicts:
            print(f"  {name}: {a!r} vs {b!r}", file=sys.stderr)
        sys.exit(1)

    requirements_path = repo_root / "requirements.txt"
    existing_text = requirements_path.read_text(encoding="utf-8") if requirements_path.exists() else ""
    content = render(reconcile(declared_lines, existing_text))

    existing_entries = parse_requirement_set(existing_text)
    expected_entries = parse_requirement_set(content)
    if existing_entries == expected_entries:
        sys.exit(0)

    if args.fix:
        requirements_path.write_text(content, encoding="utf-8")
        print(f"Updated {requirements_path}")
        sys.exit(0)

    print(f"{requirements_path} is out of sync with addon manifests' external_dependencies:", file=sys.stderr)
    for entry in sorted(expected_entries - existing_entries):
        print(f"  + {entry}", file=sys.stderr)
    for entry in sorted(existing_entries - expected_entries):
        print(f"  - {entry}", file=sys.stderr)
    print(
        "Run `solt-check-requirements --fix` to update it; it keeps the versions requirements.txt sets.",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
