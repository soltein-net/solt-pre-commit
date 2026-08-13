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


class TestSiblingRepos:
    """Deduced from the workspace, transitively, and never from a table.

    The mapping this replaced was a hand-written module -> repo dict applied to
    every Odoo version. It described the 17.0 topology, where the addons live in
    separate repos; on 19.0, where they were consolidated into one, it named
    repos that do not exist for that version - and listed the same modules as
    local and external in the same generated file. It also kept client repo
    names in a public repository.
    """

    def _repo(self, path, modules):
        path.mkdir(parents=True, exist_ok=True)
        for name, depends in modules.items():
            module = path / name
            module.mkdir(parents=True, exist_ok=True)
            (module / "__manifest__.py").write_text(repr({"name": name, "depends": depends}))
        return path

    def test_reaches_a_repo_two_hops_away(self, tmp_path, monkeypatch):
        """The incident: hop 1 gets cloned, hop 2 is missing, install fails."""
        self._repo(tmp_path / "solt-crm", {"solt_crm_landing_quoter": ["sale", "solt_base"]})
        self._repo(tmp_path / "solt-base", {"solt_base": ["base"]})
        repo_path = self._repo(tmp_path / "solt-llm", {"llm_crm": ["solt_crm_landing_quoter"]})
        monkeypatch.setattr(setup_repo, "discover_workspace_repos",
                            lambda p: {"org/solt-crm": tmp_path / "solt-crm", "org/solt-base": tmp_path / "solt-base"})
        monkeypatch.setattr(setup_repo, "get_git_branch", lambda p: "19.0")

        result = setup_repo.detect_sibling_repos(setup_repo.detect_modules(repo_path), repo_path)

        assert result == ["org/solt-base@19.0:solt-base", "org/solt-crm@19.0:solt-crm"]

    def test_a_module_of_this_repo_is_never_a_sibling(self, tmp_path, monkeypatch):
        """It cannot be both, and cloning it again duplicates it."""
        self._repo(tmp_path / "solt-suite", {"solt_base": ["base"]})
        repo_path = self._repo(tmp_path / "the-repo", {"solt_base": ["base"], "solt_thing": ["solt_base"]})
        monkeypatch.setattr(setup_repo, "discover_workspace_repos", lambda p: {"org/solt-suite": tmp_path / "solt-suite"})
        monkeypatch.setattr(setup_repo, "get_git_branch", lambda p: "19.0")

        assert setup_repo.detect_sibling_repos(setup_repo.detect_modules(repo_path), repo_path) == []

    def test_a_self_contained_repo_declares_none(self, tmp_path, monkeypatch):
        """Odoo core is not a sibling, and neither is anything else unfound."""
        repo_path = self._repo(tmp_path / "the-repo", {"solt_thing": ["base", "mail", "stock"]})
        monkeypatch.setattr(setup_repo, "discover_workspace_repos", lambda p: {})
        monkeypatch.setattr(setup_repo, "get_git_branch", lambda p: "19.0")

        assert setup_repo.detect_sibling_repos(setup_repo.detect_modules(repo_path), repo_path) == []


class TestRefreshSoltHooks:
    """An existing config is neither overwritten nor frozen.

    Overwriting discards the overrides the file exists to hold - it announces
    itself as the place users configure, and a full setup used to reset every
    answer in it. Never touching it freezes the file at the template version
    that created it, so new settings and the prose explaining them never reach
    a repo that is already set up.

    Template supplies the structure, repo supplies the answers.
    """

    def _write(self, tmp_path, template_text, current_text):
        """The template arrives as text, already rendered for the repo's Odoo
        version - its worked examples name the version reading them."""
        config = tmp_path / ".solt-hooks.yaml"
        config.write_text(current_text)
        return config, template_text

    def test_new_template_content_reaches_a_configured_repo(self, tmp_path):
        config, template = self._write(
            tmp_path,
            "odoo_version: auto\n\n# A setting added after this repo was set up.\nnew_setting: false\n",
            "odoo_version: auto\n",
        )

        setup_repo.refresh_solt_hooks(config, template)

        assert "new_setting: false" in config.read_text()

    def test_an_answer_survives_with_the_comment_explaining_it(self, tmp_path):
        """The comment travels because it is the reason the value is what it is."""
        config, template = self._write(
            tmp_path,
            "# Repos CI must clone.\nsibling_repos: [ ]\n",
            "# Not detectable: a theme is installed, never declared in depends.\nsibling_repos:\n  - org/themes\n",
        )

        setup_repo.refresh_solt_hooks(config, template)

        result = config.read_text()
        assert "  - org/themes" in result
        assert "Not detectable: a theme is installed" in result

    def test_a_file_that_does_not_parse_is_left_alone(self, tmp_path):
        """Rewriting from a half-read config would lose answers it could not see."""
        config, template = self._write(tmp_path, "odoo_version: auto\n", "odoo_version: [unclosed\n")

        setup_repo.refresh_solt_hooks(config, template)

        assert config.read_text() == "odoo_version: [unclosed\n"




class TestDetectPostgresImage:
    """detect_postgres_image() must read the postgres-image need straight
    from a module's own manifest (external_dependencies.postgresql), the
    same single-source-of-truth pattern solt-check-requirements uses for
    Python deps - so a hand-edited workflow line isn't the only way to
    keep the CI Postgres service in sync, and regeneration can't silently
    revert it back to the plain default.
    """

    def test_no_modules_need_an_extension_keeps_default(self):
        modules = {"solt_crm": {"external_dependencies": {"python": ["requests"]}}}
        assert setup_repo.detect_postgres_image(modules) == setup_repo.DEFAULT_POSTGRES_IMAGE

    def test_module_declaring_vector_extension_picks_pgvector_image(self):
        modules = {
            "llm_pgvector": {"external_dependencies": {"python": ["pgvector"], "postgresql": ["vector"]}},
        }
        assert setup_repo.detect_postgres_image(modules) == setup_repo.POSTGRES_EXTENSION_IMAGES["vector"]

    def test_module_declaring_vchord_extension_wins_over_plain_vector(self):
        """vchord's image already CASCADEs pgvector in, so when both are
        declared across a repo's modules (llm_pgvector + llm_vectorchord,
        as in solt-llm), the vchord image alone satisfies both - no need to
        pick one arbitrarily or run two separate Postgres images."""
        modules = {
            "llm_pgvector": {"external_dependencies": {"postgresql": ["vector"]}},
            "llm_vectorchord": {"external_dependencies": {"postgresql": ["vchord"]}},
        }
        assert setup_repo.detect_postgres_image(modules) == setup_repo.POSTGRES_EXTENSION_IMAGES["vchord"]

    def test_module_with_no_external_dependencies_key_is_tolerated(self):
        modules = {"solt_base": {}}
        assert setup_repo.detect_postgres_image(modules) == setup_repo.DEFAULT_POSTGRES_IMAGE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
