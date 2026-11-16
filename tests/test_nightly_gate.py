"""The nightly gate of the generated solt-validate.yml: a quiet night skips the tests, unless the last night that tested did not pass.

The step's shell is taken out of the template and run for real in a throwaway git repo, with a stub ``gh``
(the GitHub API) on the PATH: no network.
"""

import os
import re
import stat
import time
import subprocess
from pathlib import Path

import pytest
import yaml

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "github-workflows" / "solt-validate.yml"

GH_STUB = r"""#!/usr/bin/env bash
# Stub of the three `gh api` calls the gate makes. The answers come from the environment:
#   GH_FAIL=1            every call fails (API error)
#   GH_RUNS="11 12"      ids of the completed scheduled runs, newest first
#   GH_JOBS_11="skipped" the conclusions of that run's NightlyTest jobs (space separated)
[ -z "${GH_FAIL:-}" ] || exit 1
url="$2"
case "$url" in
  *"/actions/runs/${GITHUB_RUN_ID}") echo 99 ;;
  */actions/workflows/*) for run in ${GH_RUNS:-}; do echo "$run"; done ;;
  */actions/runs/*/jobs*)
    run="${url#*/actions/runs/}"; run="${run%%/*}"
    var="GH_JOBS_${run}"
    echo "$(echo "${!var:-}" | tr ' ' '\n' | grep -v '^skipped$' | grep -v '^$' | sort -u | tr '\n' ' ' | sed 's/ $//')"
    ;;
esac
"""


def _gate_script():
    text = TEMPLATE.read_text()
    text = re.sub(r"\{\{ ODOO_VERSION \}\}", "19.0", text)
    text = re.sub(r"\{\{ [A-Z_]+ \}\}", "x", text)
    steps = yaml.safe_load(text)["jobs"]["NightlyGate"]["steps"]
    return next(step["run"] for step in steps if step.get("id") == "check")


def _run_gate(tmp_path, commit_age_days, **env):
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    when = f"{int(time.time()) - commit_age_days * 86400} +0000"
    git_env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "c", "--date", when]):
        subprocess.run(["git", *args], cwd=repo, check=True, env={**git_env, "GIT_COMMITTER_DATE": when})
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(GH_STUB)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    output = tmp_path / "out"
    output.write_text("")
    run_env = {
        **os.environ, **env, "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GITHUB_OUTPUT": str(output), "GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": "100",
    }
    result = subprocess.run(["bash", "-e", "-c", _gate_script()], cwd=repo, env=run_env, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return output.read_text().strip(), result.stdout


def test_new_commits_run_the_tests(tmp_path):
    value, _ = _run_gate(tmp_path, 0, GH_RUNS="11", GH_JOBS_11="success")
    assert value == "value=true"


def test_a_quiet_night_after_a_passing_one_skips_the_tests(tmp_path):
    value, log = _run_gate(tmp_path, 5, GH_RUNS="12 11", GH_JOBS_12="skipped", GH_JOBS_11="success success")
    assert value == "value=false"
    assert "run 11" in log, "the skipped night is passed over to the last one that tested"


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", "success failure"])
def test_a_quiet_night_after_a_failed_one_runs_the_tests_again(tmp_path, conclusion):
    value, _ = _run_gate(tmp_path, 5, GH_RUNS="12 11", GH_JOBS_12="skipped", GH_JOBS_11=conclusion)
    assert value == "value=true"


def test_a_failed_night_is_not_hidden_by_the_skipped_ones_after_it(tmp_path):
    value, _ = _run_gate(tmp_path, 5, GH_RUNS="14 13 12", GH_JOBS_14="skipped", GH_JOBS_13="skipped", GH_JOBS_12="failure")
    assert value == "value=true"


def test_a_quiet_night_with_no_tested_night_to_go_by_runs_the_tests(tmp_path):
    value, _ = _run_gate(tmp_path, 5, GH_RUNS="12", GH_JOBS_12="skipped")
    assert value == "value=true"
    value, _ = _run_gate(tmp_path / "b", 5, GH_RUNS="")
    assert value == "value=true"


def test_a_quiet_night_the_api_cannot_answer_runs_the_tests(tmp_path):
    value, _ = _run_gate(tmp_path, 5, GH_FAIL="1")
    assert value == "value=true"
