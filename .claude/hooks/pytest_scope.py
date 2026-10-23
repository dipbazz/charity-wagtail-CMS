"""Stop Claude Code running the whole test suite, which CI runs on every push.

A PreToolUse hook on Bash (.claude/settings.json). It blocks a pytest run that names no path,
node id or -k filter, unless it's --lf with failures recorded or only lists or describes tests
(docs/contributing/testing.md, "Running the tests").
"""

import json
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAST_FAILED = ROOT / ".pytest_cache" / "v" / "cache" / "lastfailed"

# Options whose value is the next word, so the value isn't read as the command or a path.
UV_RUN_VALUE_OPTIONS = {
    "--directory", "--project", "--group", "--only-group", "--no-group", "--extra", "--no-extra",
    "--with", "--with-editable", "--with-requirements", "--python", "-p", "--package",
    "--env-file", "--index", "--default-index", "--index-url", "--extra-index-url",
    "--find-links", "-f", "--config-file", "--cache-dir", "--color",
}  # fmt: skip
PYTEST_VALUE_OPTIONS = {
    "-m", "-p", "-c", "-o", "-W", "--cov", "--cov-report", "--junitxml", "--junit-xml",
    "--ignore", "--ignore-glob", "--deselect", "--rootdir", "--basetemp", "--ds", "--maxfail",
    "--tb", "--durations", "--confcutdir", "--log-level", "--override-ini", "-n", "--dist",
}  # fmt: skip
# Runs that only list or describe tests.
LISTING_OPTIONS = {"--version", "-V", "--help", "-h", "--co", "--collect-only", "--fixtures",
                   "--markers"}  # fmt: skip
PYTHON = re.compile(r"(python[\d.]*|py)(\.exe)?")
REDIRECT = re.compile(r"^\d*[<>]+&?$")
SEPARATOR = re.compile(r"^[;&|()\n]+$")


def strip_wrappers(words):
    """The words from the command a wrapper such as `uv run` or `timeout` runs."""
    while words:
        word = words[0]
        if "=" in word and not word.startswith("-"):  # FOO=bar pytest
            words = words[1:]
        elif word in {"time", "nice", "command", "exec", "env"}:
            words = words[1:]
        elif word == "timeout":
            words = words[1:]
            while words and words[0].startswith("-"):
                words = words[1:]
            words = words[1:]  # the duration
        elif words[:2] == ["uv", "run"]:
            words = words[2:]
            while words and words[0].startswith("-"):
                words = words[2:] if words[0] in UV_RUN_VALUE_OPTIONS else words[1:]
        else:
            return words
    return words


def pytest_arguments(words):
    """The arguments after pytest if this command runs it, else None."""
    words = strip_wrappers(words)
    if not words:
        return None
    name = Path(words[0]).name
    if name in {"pytest", "pytest.exe"}:
        return words[1:]
    if PYTHON.fullmatch(name) and words[1:3] == ["-m", "pytest"]:
        return words[3:]
    return None


def failures_recorded():
    try:
        return bool(json.loads(LAST_FAILED.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False


def runs_whole_suite(arguments):
    arguments = iter(arguments)
    for argument in arguments:
        if argument in LISTING_OPTIONS or argument.startswith("-k"):
            return False
        if argument in {"--lf", "--last-failed"}:
            if failures_recorded():  # otherwise pytest runs everything
                return False
        elif argument in PYTEST_VALUE_OPTIONS:
            next(arguments, None)
        elif not argument.startswith("-") and argument not in {".", "./"}:
            return False  # a path, node id or app
    return True


def commands(line):
    """Each command in a shell line, as words, without its redirects."""
    lexer = shlex.shlex(line.replace("\\\n", " "), posix=True, punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    command = []
    redirect = False
    for word in lexer:
        if SEPARATOR.match(word):
            yield command
            command = []
        elif REDIRECT.match(word):
            redirect = True
        elif redirect:
            redirect = False  # the redirect's file
        else:
            command.append(word)
    yield command


def main():
    line = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    try:
        runs = [pytest_arguments(command) for command in commands(line)]
    except ValueError:  # unbalanced quotes: leave it to the shell
        return 0
    if any(arguments is not None and runs_whole_suite(arguments) for arguments in runs):
        print(
            "Don't run the whole test suite: CI runs it on every push. Run the tests you wrote "
            "or changed and those for the code you touched: name a path or node id, or use -k, "
            'or --lf after a failure (docs/contributing/testing.md, "Running the tests").',
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
