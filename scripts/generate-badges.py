#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2025 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Generate documentation coverage badges for README.

Usage:
    python scripts/generate-badges.py reports/doc-coverage.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def get_badge_color(percentage: float, metric: str = "coverage") -> str:
    """Get badge color based on percentage and metric type."""
    if metric == "coverage":
        if percentage >= 80:
            return "brightgreen"
        elif percentage >= 60:
            return "green"
        elif percentage >= 40:
            return "yellow"
        elif percentage >= 20:
            return "orange"
        else:
            return "red"
    elif metric == "errors":
        if percentage == 0:
            return "brightgreen"
        elif percentage <= 5:
            return "yellow"
        else:
            return "red"


def generate_shields_url(
    label: str,
    message: str,
    color: str,
    logo: str = "",
    logo_color: str = "white",
) -> str:
    """Generate shields.io badge URL."""
    base = "https://img.shields.io/badge"
    label_encoded = label.replace(" ", "%20").replace("-", "--")
    message_encoded = message.replace(" ", "%20").replace("-", "--").replace("%", "%25")

    url = f"{base}/{label_encoded}-{message_encoded}-{color}"

    if logo:
        url += f"?logo={logo}&logoColor={logo_color}"

    return url


def generate_markdown_badges(data: dict) -> str:
    """Generate markdown badges from coverage data."""
    summary = data.get("summary", {})

    # Docstring coverage badge
    doc_coverage = summary.get("methods", {}).get("coverage", 0)
    doc_badge = generate_shields_url(
        label="docstrings",
        message=f"{doc_coverage:.1f}%",
        color=get_badge_color(doc_coverage),
        logo="python",
    )

    # Standards badge (passing if doc_coverage >= 10%)
    doc_passing = doc_coverage >= 10

    standards_badge = generate_shields_url(
        label="Documentation Standards",
        message="passing" if doc_passing else "review needed",
        color="brightgreen" if doc_passing else "yellow",
        logo="github",
    )

    # Generate markdown - exactly 2 badges as shown in image
    badges = [
        f"![Docstrings]({doc_badge})",
        f"![Documentation Standards]({standards_badge})",
    ]

    return " ".join(badges)


def generate_html_badges(data: dict) -> str:
    """Generate HTML badges (for more control)."""
    summary = data.get("summary", {})

    doc_coverage = summary.get("methods", {}).get("coverage", 0)
    string_coverage = summary.get("fields", {}).get("string_coverage", 0)
    help_coverage = summary.get("fields", {}).get("help_coverage", 0)
    overall_score = summary.get("overall_score", 0)

    html = f"""
<div align="center">
  <img src="{generate_shields_url("docstrings", f"{doc_coverage:.1f}%", get_badge_color(doc_coverage), "python")}" alt="Docstrings">
  <img src="{generate_shields_url("field strings", f"{string_coverage:.1f}%", get_badge_color(string_coverage), "odoo")}" alt="Field Strings">
  <img src="{generate_shields_url("field help", f"{help_coverage:.1f}%", get_badge_color(help_coverage), "odoo")}" alt="Field Help">
  <img src="{generate_shields_url("doc score", f"{overall_score:.0f}%", get_badge_color(overall_score), "readthedocs")}" alt="Doc Score">
</div>
"""
    return html.strip()


def update_readme_badges(readme_path: Path, badges_markdown: str) -> bool:
    """Update badges section in README."""
    if not readme_path.exists():
        print(f"README not found: {readme_path}")
        return False

    content = readme_path.read_text()

    # Look for badge section markers
    start_marker = "<!-- BADGES:START -->"
    end_marker = "<!-- BADGES:END -->"

    if start_marker not in content or end_marker not in content:
        print("Badge markers not found in README")
        print("Add the following markers to your README:")
        print(start_marker)
        print(end_marker)
        return False

    # Replace content between markers
    start_idx = content.index(start_marker) + len(start_marker)
    end_idx = content.index(end_marker)

    new_content = content[:start_idx] + "\n" + badges_markdown + "\n" + content[end_idx:]

    readme_path.write_text(new_content)
    print(f"✅ Updated badges in {readme_path}")
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate documentation coverage badges")
    parser.add_argument(
        "report_file",
        help="Path to JSON coverage report",
    )
    parser.add_argument(
        "--readme",
        help="Update badges in README file",
        default=None,
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "html"],
        default="markdown",
        help="Output format",
    )
    parser.add_argument(
        "--output",
        help="Output file (default: stdout)",
        default=None,
    )

    args = parser.parse_args()

    # Load report
    report_path = Path(args.report_file)
    if not report_path.exists():
        print(f"Error: Report file not found: {report_path}", file=sys.stderr)
        sys.exit(1)

    with open(report_path) as f:
        data = json.load(f)

    # Generate badges
    if args.format == "markdown":
        output = generate_markdown_badges(data)
    else:
        output = generate_html_badges(data)

    # Output
    if args.output:
        Path(args.output).write_text(output)
        print(f"✅ Badges written to {args.output}")
    else:
        print(output)

    # Update README if requested
    if args.readme:
        update_readme_badges(Path(args.readme), output)


if __name__ == "__main__":
    main()
