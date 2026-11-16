# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""A cancelled run stops, and a shard that did not finish fails the run.

Real incident: jobs and steps ran under ``always()``, which also holds on a cancelled run. A
newer push to a PR asked GitHub to cancel the previous run, its shards kept running to the end,
and the new run waited for them to free the concurrency group - up to 35 minutes, every day.

The other half: once a cancelled or timed-out shard stops early it uploads no result, and
Combine read only the results that did arrive - so a shard that never finished turned into a pass.

Runs Combine's own script, as written in the workflow, against shard artifacts laid out the way
the Coverage legs upload them."""

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOWS = sorted((_ROOT / ".github" / "workflows").glob("*.yml")) + sorted(
    (_ROOT / "templates" / "github-workflows").glob("*.yml")
)
_COVERAGE = _ROOT / ".github" / "workflows" / "solt-coverage.yml"


def _conditions(workflow):
    """Every job-level and step-level ``if:`` in ``workflow``, with where it is."""
    for job_name, job in (workflow.get("jobs") or {}).items():
        if "if" in job:
            yield job_name, str(job["if"])
        for step in job.get("steps") or []:
            if "if" in step:
                yield "%s / %s" % (job_name, step.get("name", "?")), str(step["if"])


@pytest.mark.parametrize("path", _WORKFLOWS, ids=lambda path: path.name)
def test_no_condition_survives_a_cancellation(path):
    """``always()`` keeps a job or step running on a cancelled run; ``!cancelled()`` does not."""
    workflow = yaml.safe_load(path.read_text())
    offending = [where for where, condition in _conditions(workflow) if "always()" in condition]
    assert not offending, "%s: use !cancelled() instead of always() in %s" % (path.name, offending)


def _combine_script():
    workflow = yaml.safe_load(_COVERAGE.read_text())
    step = next(step for step in workflow["jobs"]["Combine"]["steps"] if step.get("id") == "combine")
    return re.search(r"<<'PYEOF'\n(.*)\nPYEOF", step["run"], re.S).group(1)


def _combine(tmp_path, shards, coverage_result):
    """Run Combine over ``shards`` ({index: result or None}) and return (exit code, outputs)."""
    for index, result in shards.items():
        shard_dir = tmp_path / "shard-artifacts" / ("shard-data-%d" % index)
        shard_dir.mkdir(parents=True)
        (shard_dir / "modules-tested.txt").write_text("module_%d" % index)
        if result is not None:
            (shard_dir / "result.txt").write_text(result)
    output = tmp_path / "github_output"
    output.write_text("")
    env = dict(os.environ, GITHUB_OUTPUT=str(output), SKIP_IF_ERRORS="", COVERAGE_RESULT=coverage_result)
    completed = subprocess.run(
        ["python3", "-c", _combine_script()], cwd=tmp_path, env=env, capture_output=True, text=True
    )
    outputs = dict(line.split("=", 1) for line in output.read_text().splitlines() if "=" in line)
    return completed.returncode, outputs


def test_every_shard_passing_passes(tmp_path):
    code, outputs = _combine(tmp_path, {0: "0", 1: "0"}, "success")
    assert (code, outputs["test_result"]) == (0, "0")


def test_a_shard_that_left_no_result_fails_the_run(tmp_path):
    code, outputs = _combine(tmp_path, {0: "0", 1: None}, "cancelled")
    assert (code, outputs["test_result"]) == (1, "1")


def test_a_shard_that_uploaded_nothing_fails_the_run(tmp_path):
    """A timed-out shard skips its upload: only the other shard's data reaches Combine."""
    code, outputs = _combine(tmp_path, {0: "0"}, "cancelled")
    assert (code, outputs["test_result"]) == (1, "1")


def test_no_shard_finishing_is_not_a_pass(tmp_path):
    code, outputs = _combine(tmp_path, {}, "failure")
    assert (code, outputs["test_result"]) == (1, "1")


def test_nothing_to_test_still_passes(tmp_path):
    """scope=changed with no matching module: every shard exits early and uploads nothing."""
    code, outputs = _combine(tmp_path, {}, "success")
    assert (code, outputs["test_result"]) == (0, "0")
