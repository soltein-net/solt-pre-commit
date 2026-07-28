# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Regression test for update_version_in_file (scripts/setup-repo.py):
it must only touch the solt-pre-commit repo's own version pin, never a
sibling hook's unrelated `rev:`/`@vX.Y.Z` reference in the same file.

Real incident: running setup-repo.py against solt-llm's
.pre-commit-config.yaml rewrote ruff-pre-commit's v0.8.4, OCA/pylint-odoo's
v9.3.22, and pre-commit-hooks' v6.0.0 all to v1.1.0 - the regex had no scope
to the solt-pre-commit repo block, so it matched every `rev: vX.Y.Z` line
in the file."""

import importlib.util
from pathlib import Path

import pytest

_SETUP_REPO_PATH = Path(__file__).resolve().parent.parent / "scripts" / "setup-repo.py"
_spec = importlib.util.spec_from_file_location("setup_repo", _SETUP_REPO_PATH)
setup_repo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(setup_repo)


class TestUpdateVersionInFile:
    def test_only_updates_the_solt_pre_commit_rev_not_sibling_hooks(self, tmp_path):
        config = tmp_path / ".pre-commit-config.yaml"
        config.write_text(
            "  - repo: https://github.com/soltein-net/solt-pre-commit\n"
            "    rev: v1.0.1\n"
            "    hooks:\n"
            "      - id: solt-check-branch\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    rev: v0.8.4\n"
            "    hooks:\n"
            "      - id: ruff\n"
            "  - repo: https://github.com/OCA/pylint-odoo\n"
            "    rev: v9.3.22\n"
            "    hooks:\n"
            "      - id: pylint_odoo\n"
            "  - repo: https://github.com/pre-commit/pre-commit-hooks\n"
            "    rev: v6.0.0\n"
        )
        changed = setup_repo.update_version_in_file(config, "v1.1.0", dry_run=False)
        content = config.read_text()

        assert changed is True
        assert "https://github.com/soltein-net/solt-pre-commit\n    rev: v1.1.0" in content
        assert "rev: v0.8.4" in content
        assert "rev: v9.3.22" in content
        assert "rev: v6.0.0" in content

    def test_updates_solt_pre_commit_reusable_workflow_refs_not_other_actions(self, tmp_path):
        workflow = tmp_path / "solt-validate.yml"
        workflow.write_text(
            "  Lint:\n"
            "    uses: soltein-net/solt-pre-commit/.github/workflows/solt-validate.yml@v1.0.1\n"
            "  Test:\n"
            "    uses: soltein-net/solt-pre-commit/.github/workflows/solt-coverage.yml@v1.0.1\n"
            "  Checkout:\n"
            "    uses: actions/checkout@v4.1.0\n"
        )
        setup_repo.update_version_in_file(workflow, "v1.1.0", dry_run=False)
        content = workflow.read_text()

        assert "solt-validate.yml@v1.1.0" in content
        assert "solt-coverage.yml@v1.1.0" in content
        assert "actions/checkout@v4.1.0" in content

    def test_dry_run_does_not_write_the_file(self, tmp_path):
        config = tmp_path / ".pre-commit-config.yaml"
        original = "  - repo: https://github.com/soltein-net/solt-pre-commit\n    rev: v1.0.1\n"
        config.write_text(original)
        setup_repo.update_version_in_file(config, "v1.1.0", dry_run=True)
        assert config.read_text() == original

    def test_returns_false_when_nothing_matches(self, tmp_path):
        config = tmp_path / ".pre-commit-config.yaml"
        config.write_text("  - repo: https://github.com/astral-sh/ruff-pre-commit\n    rev: v0.8.4\n")
        assert setup_repo.update_version_in_file(config, "v1.1.0", dry_run=True) is False

    def test_missing_file_returns_false(self, tmp_path):
        missing = tmp_path / "does_not_exist.yaml"
        assert setup_repo.update_version_in_file(missing, "v1.1.0") is False


class TestFilesToCopy:
    """Regression guard for what setup-repo.py distributes into consumer
    repos - catches exactly the kind of drift this suite exists to prevent
    (a file that's copied but shouldn't be, or should be but isn't)."""

    def test_does_not_distribute_the_agent_skills_lockfile(self):
        # Removed deliberately - solt-pre-commit doesn't vendor/distribute
        # third-party AI-agent tooling (addyosmani/agent-skills has its own
        # install path via Claude Code's own plugin system).
        destinations = [dest for _src, dest, _desc in setup_repo.FILES_TO_COPY]
        assert "skills-lock.json" not in destinations

    def test_distributes_a_contributing_md_from_the_template(self):
        matches = [
            (src, dest) for src, dest, _desc in setup_repo.FILES_TO_COPY if dest == "CONTRIBUTING.md"
        ]
        assert len(matches) == 1
        (src, _dest) = matches[0]
        assert src.name == "CONTRIBUTING-template.md"

    def test_does_not_distribute_the_addyosmani_agents_directory(self):
        destinations = [dest for _src, dest, _desc in setup_repo.DIRECTORIES_TO_COPY]
        assert ".agents" not in destinations


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
