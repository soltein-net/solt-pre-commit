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
import yaml

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


class TestPreCommitTemplateConsistency:
    """templates/.pre-commit-config.yaml (standalone client repos) and
    templates/.pre-commit-config-local.yaml (repos, submoduled inside the
    soltein monorepo) wire the solt-pre-commit hooks differently on purpose -
    GitHub-pinned repo vs. `repo: local` against the editable install (see
    setup_repo.PRECOMMIT_REMOTE / PRECOMMIT_LOCAL). But both vendor the SAME
    third-party tools (ruff, pylint-odoo, pre-commit-hooks), and nothing
    enforced those staying in sync - they'd already drifted apart (ruff
    v0.15.10 vs v0.8.4, pylint-odoo v10.0.0 vs v9.3.22, and differing
    `exclude` patterns on the pre-commit-hooks hooks)."""

    SHARED_REPO_URLS = (
        "https://github.com/astral-sh/ruff-pre-commit",
        "https://github.com/OCA/pylint-odoo",
        "https://github.com/pre-commit/pre-commit-hooks",
    )

    @staticmethod
    def _repos_by_url(template_path):
        config = yaml.safe_load(template_path.read_text())
        return {r["repo"]: r for r in config["repos"]}

    def test_shared_third_party_pins_match(self):
        remote = self._repos_by_url(setup_repo.PRECOMMIT_REMOTE[0])
        local = self._repos_by_url(setup_repo.PRECOMMIT_LOCAL[0])

        mismatches = {
            url: (remote[url]["rev"], local[url]["rev"])
            for url in self.SHARED_REPO_URLS
            if remote[url]["rev"] != local[url]["rev"]
        }
        assert mismatches == {}, f"pinned rev drifted between templates: {mismatches}"

    def test_shared_hook_options_match(self):
        remote = self._repos_by_url(setup_repo.PRECOMMIT_REMOTE[0])
        local = self._repos_by_url(setup_repo.PRECOMMIT_LOCAL[0])

        for url in self.SHARED_REPO_URLS:
            remote_hooks = {h["id"]: h for h in remote[url]["hooks"]}
            local_hooks = {h["id"]: h for h in local[url]["hooks"]}
            for hook_id in set(remote_hooks) & set(local_hooks):
                assert remote_hooks[hook_id] == local_hooks[hook_id], (
                    f"hook {hook_id!r} options differ between templates for {url}"
                )

    @staticmethod
    def _solt_hook_ids(template_path):
        """solt-* hook ids wired up in a template, regardless of whether
        they live under the GitHub-pinned repo (remote) or `repo: local`
        (local) block - that block's `repo:` key differs by design, so
        hook id is the only comparable key across the two files."""
        config = yaml.safe_load(template_path.read_text())
        return {
            hook["id"]
            for repo in config["repos"]
            for hook in repo.get("hooks", [])
            if hook["id"].startswith("solt-")
        }

    def test_solt_hooks_match_except_documented_exceptions(self):
        """Every solt-pre-commit hook wired into one template must be wired
        into the other too, unless explicitly allowlisted here as a known,
        intentional difference. Catches exactly the kind of silent gap found
        in the wild: solt-check-branch only in the local template because
        commit 0e0800c ("move branch name check to PR level with
        auto-close") removed it from the remote template alone, without a
        comment explaining why - it read as an oversight, not a decision."""
        # local-only: 0e0800c moved branch-name enforcement for standalone
        # client repos to the PR-level solt-validate.yml workflow (which
        # auto-closes PRs with an invalid branch name), so the remote
        # template no longer needs it as a local commit-time gate. Monorepo
        # submodule repos keep it locally too, on top of that same PR-level
        # check, for faster feedback during day-to-day development.
        known_local_only_hooks = {"solt-check-branch"}
        known_remote_only_hooks = set()

        remote_ids = self._solt_hook_ids(setup_repo.PRECOMMIT_REMOTE[0])
        local_ids = self._solt_hook_ids(setup_repo.PRECOMMIT_LOCAL[0])

        unexplained_local_only = (local_ids - remote_ids) - known_local_only_hooks
        unexplained_remote_only = (remote_ids - local_ids) - known_remote_only_hooks

        assert unexplained_local_only == set(), (
            f"hooks only in the local template, not allowlisted: {unexplained_local_only}"
        )
        assert unexplained_remote_only == set(), (
            f"hooks only in the remote template, not allowlisted: {unexplained_remote_only}"
        )

    def test_every_exported_hook_is_wired_or_documented_opt_in(self):
        """.pre-commit-hooks.yaml is the full menu of hooks solt-pre-commit
        exports to consumers. Any hook missing from BOTH templates must be
        explicitly allowlisted here as intentionally opt-in-only, or it's
        likely just an oversight - exactly what happened to
        solt-test-changed-modules: exported since v1.1.0 (commit dfcc3ba)
        but never wired into either default template."""
        # Deliberately opt-in only: each is a single-file-type subset of
        # solt-check-odoo (which already runs all of them together), meant
        # for repos that want e.g. XML-only validation instead of the full
        # suite - not something every client repo should run by default.
        known_opt_in_only_hooks = {
            "solt-check-xml",
            "solt-check-csv",
            "solt-check-po",
            "solt-check-python",
        }

        exported = yaml.safe_load((setup_repo.PROJECT_ROOT / ".pre-commit-hooks.yaml").read_text())
        exported_ids = {hook["id"] for hook in exported}

        wired_anywhere = self._solt_hook_ids(setup_repo.PRECOMMIT_REMOTE[0]) | self._solt_hook_ids(
            setup_repo.PRECOMMIT_LOCAL[0]
        )

        unwired = exported_ids - wired_anywhere - known_opt_in_only_hooks
        assert unwired == set(), f"hooks exported but wired into neither template, not allowlisted: {unwired}"

    def test_repo_local_hooks_do_not_use_language_python(self):
        """`repo: local` + `language: python` makes pre-commit build a
        throwaway, ISOLATED virtualenv per hook and pip-install only
        `additional_dependencies` into it - it has no way to obtain
        solt_pre_commit itself, since there's no repo checkout for
        pre-commit to pip-install (that's what makes the remote template's
        `language: python` work: pre-commit clones the real repo at the
        pinned rev and installs it into the venv). Caught live: every
        solt-* hook in templates/.pre-commit-config-local.yaml failed with
        `ModuleNotFoundError: No module named 'solt_pre_commit'` despite the
        package being editable-installed in the ambient environment -
        `language: system` is required instead, which skips venv creation
        and runs `entry` directly against whatever's already on PATH."""
        config = yaml.safe_load(setup_repo.PRECOMMIT_LOCAL[0].read_text())
        local_repo = next(r for r in config["repos"] if r["repo"] == "local")

        wrong_language = {
            hook["id"]: hook.get("language")
            for hook in local_repo["hooks"]
            if hook.get("language") != "system"
        }
        assert wrong_language == {}, f"repo:local hooks must use language: system, found: {wrong_language}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
