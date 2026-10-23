"""The Claude Code hooks in .claude/hooks/ (docs/decisions.md, "Claude Code hooks ...")."""

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def load(name):
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pytest_scope = load("pytest_scope")
check_stylesheet = load("check_stylesheet")


def run_hook(hook, tool_input, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_input": tool_input})))
    return hook.main()


@pytest.fixture
def no_failures_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(pytest_scope, "LAST_FAILED", tmp_path / "lastfailed", raising=False)


@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest",
        "uv run pytest -q",
        'uv run pytest -m "not browser"',
        "python -m pytest",
        "py -m pytest",
        "uv run pytest -x; ls",
        "uv run pytest .",
        "uv run pytest --cov charity",
        "uv run pytest --junitxml out/report.xml",
        "uv run pytest > C:/tmp/out.txt",
        "echo start\nuv run pytest",
        "uv run pytest \\\n  -q",
        "uv run --directory . pytest",
        "uv run --only-group test pytest",
        "timeout 900 uv run pytest",
        "env X=1 pytest",
        "uv run pytest --sw",
        "uv run pytest --lf",
    ],
)
def test_a_whole_suite_run_is_blocked(command, no_failures_recorded, monkeypatch):
    assert run_hook(pytest_scope, {"command": command}, monkeypatch) == 2


@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest news",
        "uv run pytest core/tests/test_mail.py::test_send",
        "uv run pytest -k gift",
        'uv run pytest -m "not browser" core/tests',
        "uv run pytest --cov=core core/tests",
        "cd core && uv run pytest tests",
        "uv run pytest --version",
        "uv run pytest --co -q",
        "uv run pytest --fixtures",
        "git grep pytest",
        "echo 'uv run pytest'",
        "uv run ruff check .",
    ],
)
def test_a_narrowed_or_harmless_command_is_allowed(command, no_failures_recorded, monkeypatch):
    assert run_hook(pytest_scope, {"command": command}, monkeypatch) == 0


def test_last_failed_is_allowed_when_tests_failed_last_time(tmp_path, monkeypatch):
    last_failed = tmp_path / "lastfailed"
    last_failed.write_text(json.dumps({"core/tests/test_mail.py::test_send": True}))
    monkeypatch.setattr(pytest_scope, "LAST_FAILED", last_failed)

    assert run_hook(pytest_scope, {"command": "uv run pytest --lf"}, monkeypatch) == 0


def fake_test_run(monkeypatch, **result):
    calls = []

    def run(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, **{"stdout": "", "stderr": "", **result})

    monkeypatch.setattr(check_stylesheet.subprocess, "run", run)
    return calls


@pytest.mark.parametrize(
    "path",
    [
        check_stylesheet.ROOT / "README.md",
        # test_stylesheet.py checks only the stylesheets directly in the folder.
        check_stylesheet.CSS / "pages" / "gift.css",
    ],
)
def test_the_stylesheet_test_runs_only_for_a_stylesheet_it_checks(path, monkeypatch):
    calls = fake_test_run(monkeypatch, returncode=0)

    assert run_hook(check_stylesheet, {"file_path": str(path)}, monkeypatch) == 0
    assert calls == []


def test_a_failing_stylesheet_is_reported_to_claude(monkeypatch, capsys):
    fake_test_run(monkeypatch, returncode=1, stdout="FAILED max-width")

    exit_code = run_hook(
        check_stylesheet, {"file_path": str(check_stylesheet.CSS / "charity.css")}, monkeypatch
    )

    assert exit_code == 2
    assert "FAILED max-width" in capsys.readouterr().err


def test_a_test_that_cannot_run_is_not_reported_as_a_failing_stylesheet(monkeypatch, capsys):
    fake_test_run(monkeypatch, returncode=2, stderr="error: Failed to spawn: `pytest`")

    exit_code = run_hook(
        check_stylesheet, {"file_path": str(check_stylesheet.CSS / "charity.css")}, monkeypatch
    )

    err = capsys.readouterr().err
    assert exit_code == 1  # shown to the person, without waking Claude
    assert "Failed to spawn" in err
    assert "fails after this change" not in err
