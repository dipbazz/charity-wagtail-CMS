"""The pre-commit check on branch names (scripts/check_branch_name.py)."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_branch_name.py"
spec = importlib.util.spec_from_file_location("check_branch_name", SCRIPT)
check_branch_name = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_branch_name)


@pytest.mark.parametrize(
    "branch",
    [
        "feat/142-share-gift",
        "fix/9-pledge-total",
        "docs/238-branch-name-check",
        "chore/12-trim-claude-md",
        "perf/7-lazy-images",
        "refactor/30-split-views",
        "test/31-browser-menu",
        "style/32-button-radius",
        "ci/33-cache-uv",
        "feat/142-a",
        "feat/142-v2-share-gift",
        # Branches the docs name another way (releases.md).
        "main",
        "chore/release-0.5.0",
        "patch/0.4.x",
        # Not on a branch: a rebase, a cherry-pick or a checked-out tag.
        "",
    ],
)
def test_accepts(branch):
    assert check_branch_name.problem(branch) is None


@pytest.mark.parametrize(
    "branch",
    [
        "feat/share-gift",
        "feat/142",
        "feat/142-",
        "feat/142share-gift",
        "142-share-gift",
        "feature/142-share-gift",
        "Feat/142-share-gift",
        "feat/142-Share-Gift",
        "feat/142-share_gift",
        "feat/142-share--gift",
        "feat/142-share-gift-",
        "feat/142/share-gift",
        "chore/release-0.5",
        "chore/release-0.5.0-final",
        "patch/0.4",
        "patch/0.4.x-fix",
        "main-2",
        "mainline",
    ],
)
def test_refuses(branch):
    message = check_branch_name.problem(branch)
    assert branch in message
    assert "<type>/<issue-number>-<slug>" in message


def test_the_message_lists_the_types():
    message = check_branch_name.problem("wip")
    for kind in ("feat", "fix", "perf", "refactor", "test", "chore", "docs", "style", "ci"):
        assert kind in message


def git(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git("init", "-q", "-b", "main", cwd=tmp_path)
    git("config", "user.name", "Test", cwd=tmp_path)
    git("config", "user.email", "test@example.com", cwd=tmp_path)
    git("config", "commit.gpgsign", "false", cwd=tmp_path)
    git("commit", "-q", "--allow-empty", "-m", "start", cwd=tmp_path)
    return tmp_path


def run_check(cwd):
    return subprocess.run([sys.executable, str(SCRIPT)], cwd=cwd, capture_output=True, text=True)


def test_the_script_accepts_a_named_branch(repo):
    git("switch", "-q", "-c", "feat/142-share-gift", cwd=repo)
    result = run_check(repo)
    assert result.returncode == 0
    assert result.stderr == ""


def test_the_script_refuses_an_unnumbered_branch(repo):
    git("switch", "-q", "-c", "feat/share-gift", cwd=repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "feat/share-gift" in result.stderr


def test_the_script_accepts_main_and_a_detached_head(repo):
    assert run_check(repo).returncode == 0
    git("checkout", "-q", "--detach", cwd=repo)
    assert run_check(repo).returncode == 0
