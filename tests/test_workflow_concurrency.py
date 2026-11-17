# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Which runs of the generated solt-validate.yml share a concurrency group, and so cancel each other.

Real incident: both crons run on the default branch and the group was ref-scoped for them, so every
Monday the 6 AM docstring run cancelled the nightly test run started at 4 AM.

The ``group:`` expression is taken from the template and evaluated here with GitHub's ``&&`` / ``||``
semantics (each returns one of its operands; ``''`` and ``null`` are falsy)."""

import re
from pathlib import Path

import pytest
import yaml

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "github-workflows" / "solt-validate.yml"


def _crons():
    workflow = yaml.safe_load(TEMPLATE.read_text())
    # PyYAML reads the bare ``on:`` key as the boolean True.
    return [entry["cron"] for entry in workflow[True]["schedule"]]


def _evaluate(expression, context):
    """Evaluate a ``||`` of ``&&`` chains of ``path`` or ``path == 'literal'`` operands."""
    assert "(" not in expression and "!" not in expression, "the evaluator does not cover: %s" % expression

    def operand(text):
        text = text.strip()
        comparison = re.fullmatch(r"([\w.]+)\s*==\s*'([^']*)'", text)
        if comparison:
            return context.get(comparison.group(1)) == comparison.group(2)
        assert re.fullmatch(r"[\w.]+", text), "unexpected operand: %s" % text
        return context.get(text)

    value = None
    for chain in expression.split("||"):
        for part in chain.split("&&"):
            value = operand(part)
            if not value:
                break
        if value:
            return value
    return value


def _group(event_name, **context):
    workflow = yaml.safe_load(TEMPLATE.read_text())
    template = workflow["concurrency"]["group"]
    context = {"github.workflow": "Soltein Validation", "github.event_name": event_name, **context}
    return re.sub(r"\$\{\{(.*?)\}\}", lambda match: str(_evaluate(match.group(1), context)), template)


def _scheduled(cron):
    return _group("schedule", **{"github.event.schedule": cron, "github.ref": "refs/heads/19.0", "github.sha": "a1"})


def test_the_crons_never_share_a_group():
    crons = _crons()
    assert len(crons) > 1, "the template no longer has two crons; this test has nothing to compare"
    groups = [_scheduled(cron) for cron in crons]
    assert len(set(groups)) == len(groups), "a cron would cancel another one's run: %s" % dict(zip(crons, groups, strict=True))


@pytest.mark.parametrize("event_name", ["push", "pull_request", "workflow_dispatch"])
def test_no_other_event_cancels_a_scheduled_run(event_name):
    context = {"github.ref": "refs/heads/19.0", "github.sha": "a1"}
    if event_name == "pull_request":
        context["github.ref"] = "refs/pull/7/merge"
    scheduled = {_scheduled(cron) for cron in _crons()}
    assert _group(event_name, **context) not in scheduled


def test_a_newer_push_to_a_pr_cancels_the_previous_run():
    first = _group("pull_request", **{"github.ref": "refs/pull/7/merge", "github.sha": "a1"})
    second = _group("pull_request", **{"github.ref": "refs/pull/7/merge", "github.sha": "b2"})
    assert first == second


def test_a_push_never_cancels_the_previous_push():
    first = _group("push", **{"github.ref": "refs/heads/19.0", "github.sha": "a1"})
    second = _group("push", **{"github.ref": "refs/heads/19.0", "github.sha": "b2"})
    assert first != second
