#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)
"""Generate a README.md template for Soltein Odoo repositories.

Usage:
    python generate-readme.py <repo-name> <odoo-version> "<description>" [options]

Examples:
    python generate-readme.py solt-hr 17.0 "Odoo HR modules for payroll and attendance"
    python generate-readme.py solt-fc 18.0 "Financial consolidation modules" --org SolteinCorp
    python generate-readme.py solt-base 19.0 "Core base modules" --output /path/to/README.md
    python generate-readme.py solt-web 17.0 "Web UI enhancements" --dry-run
"""

import argparse
import sys
from pathlib import Path

GIST_OWNER_DEFAULT = "SolteinCorp"
GIST_ID_DEFAULT = "147d543a086f6735d1ffa02172766e86"
GITHUB_ORG_DEFAULT = "soltein-net"

TEMPLATE = """\
[![Docstring Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/{gist_owner}/{gist_id}/raw/{repo}-{version}-docstrings.json)](https://github.com/{org}/{repo}/actions/workflows/solt-validate.yml)
[![Validation Status](https://github.com/{org}/{repo}/actions/workflows/solt-validate.yml/badge.svg?branch={version})](https://github.com/{org}/{repo}/actions/workflows/solt-validate.yml)

<!-- /!\\ do not modify above this line -->
# {repo}
{description}

## Modules

| Module | Description |
|--------|-------------|
| `module_name` | Brief description of the module |

## Requirements

- Odoo {version}
- Python {python_version}+
- Dependencies: `base`

## Installation

1. Clone this repository into your Odoo addons path:
   ```bash
   git clone https://github.com/{org}/{repo}.git
   ```
2. Add the path to your Odoo configuration `addons_path`
3. Restart Odoo and update the apps list
4. Install the desired modules from the Apps menu

## Configuration

No additional configuration required after installation.

## Usage

Describe the main workflow and how to use the modules.

## Development

This repository uses [solt-pre-commit](https://github.com/soltein-net/solt-pre-commit) for code quality validation.

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

### Branch Naming

All branches must include the Odoo version prefix (`<type>/<version>-description`):

| Type | Description | Example |
|------|-------------|---------|
| `feature` | New functionality | `feature/{version}-add-invoice-export` |
| `fix` | Bug fix | `fix/{version}-correct-tax-calc` |
| `hotfix` | Urgent production fix | `hotfix/{version}-urgent-fix` |
| `bugfix` | Non-urgent bug fix | `bugfix/{version}-missing-field` |
| `imp` / `improvement` | Enhancement to existing feature | `imp/{version}-optimize-query` |
| `refactor` | Code restructuring | `refactor/{version}-split-model` |
| `perf` | Performance improvement | `perf/{version}-cache-reports` |
| `security` | Security patch | `security/{version}-sanitize-input` |
| `docs` | Documentation only | `docs/{version}-update-readme` |
| `test` | Test additions or fixes | `test/{version}-add-invoice-tests` |
| `style` | Code style / formatting | `style/{version}-pep8-cleanup` |
| `ux` / `ui` | User experience / interface | `ux/{version}-improve-wizard` |
| `chore` | Maintenance tasks | `chore/{version}-update-deps` |
| `ci` / `build` | CI/CD or build changes | `ci/{version}-add-workflow` |
| `deps` / `config` | Dependencies or config | `deps/{version}-upgrade-lib` |
| `infra` / `ops` | Infrastructure / operations | `infra/{version}-docker-setup` |
| `migration` | Version migration | `migration/{version}-from-16` |
| `revert` | Revert a previous change | `revert/{version}-undo-export` |
| `release` | Release branch | `release/{version}.1.0` |
| `release-candidate` | Pre-release validation | `release-candidate/{version}.1.0-rc1` |

### Commit Messages

```
[TAG] module_name: brief description

Detailed explanation if needed.
```

Tags: `[ADD]` new feature, `[FIX]` bugfix, `[IMP]` improvement, `[REF]` refactor, `[REM]` removal, `[DOC]` documentation

## License

This project is licensed under [LGPL-3.0-or-later](https://www.gnu.org/licenses/lgpl-3.0).

## Credits

**[Soltein SA de CV](https://soltein.mx)**
"""

PYTHON_VERSIONS = {
    "17.0": "3.10",
    "18.0": "3.10",
    "19.0": "3.12",
}


def main():
    """Parse arguments and generate README.md."""
    parser = argparse.ArgumentParser(
        description="Generate a README.md template for Soltein Odoo repos",
    )
    parser.add_argument("repo", help="Repository name (e.g. solt-hr)")
    parser.add_argument("version", help="Odoo version (e.g. 17.0, 18.0, 19.0)")
    parser.add_argument("description", help="Short repo description in English")
    parser.add_argument(
        "--org", default=GITHUB_ORG_DEFAULT,
        help=f"GitHub organization/user (default: {GITHUB_ORG_DEFAULT})",
    )
    parser.add_argument(
        "--gist-id", default=GIST_ID_DEFAULT,
        help="Gist ID for docstring badge",
    )
    parser.add_argument(
        "--gist-owner", default=GIST_OWNER_DEFAULT,
        help=f"Gist owner username (default: {GIST_OWNER_DEFAULT})",
    )
    parser.add_argument(
        "--output", default="README.md",
        help="Output file path (default: ./README.md)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print to stdout instead of writing file",
    )

    args = parser.parse_args()

    python_version = PYTHON_VERSIONS.get(args.version, "3.12")

    content = TEMPLATE.format(
        gist_owner=args.gist_owner,
        gist_id=args.gist_id,
        repo=args.repo,
        version=args.version,
        org=args.org,
        description=args.description,
        python_version=python_version,
    )

    if args.dry_run:
        sys.stdout.write(content)
        return

    output = Path(args.output)
    output.write_text(content)
    print(f"Generated: {output}")
    print(f"  Repo:    {args.org}/{args.repo}")
    print(f"  Version: {args.version}")
    print(f"  Badges:  docstrings + validation status")


if __name__ == "__main__":
    main()
