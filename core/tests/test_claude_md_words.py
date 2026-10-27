"""The pre-commit word limit on CLAUDE.md (scripts/check_claude_md_words.py)."""

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_claude_md_words.py"
spec = importlib.util.spec_from_file_location("check_claude_md_words", SCRIPT)
check_claude_md_words = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_claude_md_words)


def test_accepts_the_limit():
    assert check_claude_md_words.problem(" ".join(["word"] * 600)) is None


def test_refuses_one_word_over():
    message = check_claude_md_words.problem(" ".join(["word"] * 601))
    assert "601" in message
    assert "600" in message


def test_the_repository_claude_md_is_within_the_limit():
    text = (SCRIPT.parents[1] / "CLAUDE.md").read_text(encoding="utf-8")
    assert check_claude_md_words.problem(text) is None


def run_check(cwd, words):
    (cwd / "CLAUDE.md").write_text(" ".join(["word"] * words), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "CLAUDE.md"], cwd=cwd, capture_output=True, text=True
    )


def test_the_script_refuses_a_long_file(tmp_path):
    result = run_check(tmp_path, 601)
    assert result.returncode == 1
    assert "601" in result.stderr


def test_the_script_accepts_a_short_file(tmp_path):
    result = run_check(tmp_path, 600)
    assert result.returncode == 0
    assert result.stderr == ""
