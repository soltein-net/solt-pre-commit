# -*- coding: utf-8 -*-
# Copyright 2026 Soltein SA. de CV.
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl.html)

"""Check whether the current branch has an open GitHub pull request.

Used by `solt-test-changed-modules` (pre-push) to decide whether to actually
run tests: per docs/pipeline-strategy.md's "Pipeline at a glance", the Test
tier fires on "PR opened/updated", not on every push - including the local
Docker instantiation of that tier, not just CI. A push to a branch with no
open PR yet is exempt; once a PR exists, every subsequent push to it runs
the suite before it even leaves the machine.

`gh` (GitHub CLI) is the primary path - it's the tool most developers already
have authenticated, so this needs no token management of its own. Falls back
to the REST API via urllib if a GITHUB_TOKEN/GH_TOKEN is set (e.g. a headless
environment with gh unavailable but a token exported). If neither works,
returns None - the caller's job to decide what "can't tell" should do, not
this module's.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request

_REMOTE_RE = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(\.git)?/?$")


def _current_branch() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        branch = result.stdout.strip()
        return branch or None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _owner_repo_from_remote(remote: str = "origin") -> tuple[str, str] | None:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", remote],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None

    match = _REMOTE_RE.search(result.stdout.strip())
    if not match:
        return None
    return match.group("owner"), match.group("repo")


def _check_via_gh(owner: str, repo: str, branch: str) -> bool | None:
    if not shutil.which("gh"):
        return None
    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                f"{owner}/{repo}",
                "--head",
                branch,
                "--state",
                "open",
                "--json",
                "number",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    if result.returncode != 0:
        # Not authenticated, no network, gh not configured for this host, etc. -
        # fall through to the token-based check rather than guessing.
        return None
    try:
        return len(json.loads(result.stdout or "[]")) > 0
    except json.JSONDecodeError:
        return None


def _check_via_rest_api(owner: str, repo: str, branch: str) -> bool | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        return None

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls?head={owner}:{branch}&state=open"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status != 200:
                return None
            return len(json.loads(response.read())) > 0
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return None


def has_open_pull_request(branch: str | None = None) -> bool | None:
    """Return True/False if an open PR's state could be determined, else None.

    None means "couldn't tell" (no gh CLI session, no token, no network,
    remote isn't GitHub) - callers should fail open (run the tests) rather
    than silently skip on an answer we don't actually have.
    """
    branch = branch or _current_branch()
    if not branch:
        return None

    owner_repo = _owner_repo_from_remote()
    if not owner_repo:
        return None
    owner, repo = owner_repo

    result = _check_via_gh(owner, repo, branch)
    if result is not None:
        return result

    return _check_via_rest_api(owner, repo, branch)
