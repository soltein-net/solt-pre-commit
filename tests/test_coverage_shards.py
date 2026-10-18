# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Regression test for solt-coverage.yml's shard split: the Coverage legs divide the
modules between them, each module tested by exactly one leg.

Real incident: for scope='changed' Plan sizes the matrix from the changed-module count,
but each leg read SHARDS from inputs.shards ('1' for every caller), so every leg kept the
whole module list - solt-suite PRs touching 16+ modules ran the same suite on 2-4 legs
until the 90-minute timeout cancelled them all.

Runs the workflow's own Plan script and narrowing block, as written in the file, with the
leg's SHARDS expression resolved the way GitHub Actions resolves it."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

_WORKFLOW_PATH = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "solt-coverage.yml"
_NARROWING_START = 'if [ "$SHARDS" -gt 1 ]; then'


def _load_workflow():
    return yaml.safe_load(_WORKFLOW_PATH.read_text())


def _plan_legs(workflow, scope, shards_input, matched_count, tmp_path):
    """The matrix legs Plan's own script lays out."""
    plan_step = next(step for step in workflow["jobs"]["Plan"]["steps"] if step.get("id") == "plan")
    output_path = tmp_path / "plan_output"
    env = dict(
        os.environ,
        SCOPE=scope,
        SHARDS=shards_input,
        MATCHED_COUNT=str(matched_count),
        GITHUB_OUTPUT=str(output_path),
    )
    subprocess.run(["bash", "-c", plan_step["run"]], env=env, check=True)
    shard_line = next(line for line in output_path.read_text().splitlines() if line.startswith("shard-list="))
    return json.loads(shard_line.split("=", 1)[1])


def _narrowing_block(test_step):
    """The block of the test step that keeps this leg's share of MODULES_CSV."""
    script_lines = test_step["run"].splitlines()
    start = script_lines.index(_NARROWING_START)
    end = next(index for index in range(start, len(script_lines)) if script_lines[index] == "fi")
    return "\n".join(script_lines[start : end + 1])


def _resolve_shards(expression, legs, shards_input):
    """What GitHub Actions puts in the leg's SHARDS for the expressions this step may use."""
    resolved = {"${{ strategy.job-total }}": str(len(legs)), "${{ inputs.shards }}": shards_input}
    assert expression in resolved, f"unexpected SHARDS expression in the test step: {expression}"
    return resolved[expression]


class TestCoverageShardSplit:
    @pytest.mark.parametrize("module_count", [3, 18, 51])
    def test_changed_modules_are_split_between_the_legs(self, module_count, tmp_path):
        workflow = _load_workflow()
        test_step = next(step for step in workflow["jobs"]["Coverage"]["steps"] if step.get("id") == "test")
        modules = [f"solt_module_{index:02d}" for index in range(module_count)]
        legs = _plan_legs(workflow, "changed", "1", module_count, tmp_path)
        tested = []
        for leg in legs:
            env = dict(
                os.environ,
                MODULES_CSV=",".join(modules),
                SHARD_INDEX=str(leg),
                SHARDS=_resolve_shards(test_step["env"]["SHARDS"], legs, "1"),
            )
            script = _narrowing_block(test_step) + '\necho "$MODULES_CSV"'
            leg_run = subprocess.run(["bash", "-c", script], env=env, check=True, capture_output=True, text=True)
            tested += leg_run.stdout.strip().splitlines()[-1].split(",")
        assert len(tested) == module_count, f"{len(tested)} module runs on {len(legs)} legs for {module_count} modules"
        assert sorted(tested) == modules
