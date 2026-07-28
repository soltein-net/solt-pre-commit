# Contributing

This repo uses [solt-pre-commit](https://github.com/soltein-net/solt-pre-commit)
for validation, testing, and CI. This doc covers what that means day to
day - see that repo's own docs for the full detail.

## Development Setup

```bash
git clone <this repo's URL>
pip install pre-commit
pre-commit install
```

That installs the git hooks defined in `.pre-commit-config.yaml` - branch
name validation and Odoo module checks (XML, CSV, PO, Python) run
automatically on every commit.

## Branch Naming

Branch names must include an Odoo version - this is enforced automatically
(`solt-check-branch`), not just a suggestion:

```
[OK] feature/17.0-SOLT-123-add-invoice-report   (version + ticket, recommended)
[OK] fix/18.0-correct-tax-calculation            (version only)
[OK] 17.0-hotfix-urgent-fix                      (version-type format)
[X]  feature/add-invoice-report                  (missing version - rejected)
```

## Running Tests Locally

```bash
solt-test-module <module_name>          # e.g. solt-test-module sale_extension
solt-test-module mod_a,mod_b            # multiple modules
```

Needs a local Odoo + Postgres environment already available (a devcontainer,
or your own setup) - it creates a disposable scratch database, runs the
module's own tests with coverage, and cleans up after itself. If you push
without running this, `solt-test-changed-modules` (the pre-push hook) runs
it for you automatically for whatever modules your push actually touched -
but only once this branch has an open PR; the first push before a PR exists
is exempt.

## Pull Request Process

1. Push your branch, open a PR
2. CI runs lint + tests automatically
3. Address any blocking issues (errors block; warnings/info don't, by default)
4. Get it reviewed and merged per this repo's own branch protection rules

## AI Agent Tooling (Optional)

If you use Claude Code and want AI-agent skills for this kind of work
(test-driven development, spec-driven development, planning/task
breakdown, and more), install them directly from their own source -
solt-pre-commit does not bundle, vendor, or otherwise distribute this:

```
/plugin marketplace add addyosmani/agent-skills
/plugin install agent-skills@addy-agent-skills
```

That gives you the skills themselves (invokable by name, e.g.
`/test-driven-development`) plus the short-form commands documented in
that project's own README (`/spec`, `/build`, `/ship`, etc.). Entirely
optional, and unrelated to anything solt-pre-commit's own checks enforce.
