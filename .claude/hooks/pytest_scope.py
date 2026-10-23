"""Stop Claude Code running the whole test suite, which CI runs on every push.

A PreToolUse hook on Bash (.claude/settings.json). It blocks a pytest run that names no path,
node id or -k filter and isn't --lf or --sw (docs/contributing/testing.md, "Running the tests").
"""

import json
import os
import re
import shlex
import sys

# uv run options that take a value, so the value isn't read as the command.
UV_RUN_VALUE_OPTIONS = {"--group", "--with", "--python", "-p", "--extra", "--package", "--env-file"}
NARROWING_OPTIONS = {"--lf", "--last-failed", "--sw", "--stepwise", "-k"}
SEPARATOR = re.compile(r"^[;&|()]+$")


def pytest_arguments(words):
    """The arguments after pytest if this command runs it, else None."""
    while words and "=" in words[0] and not words[0].startswith("-"):
        words = words[1:]  # FOO=bar pytest
    if words[:2] == ["uv", "run"]:
        words = words[2:]
        while words and words[0].startswith("-"):
            words = words[2:] if words[0] in UV_RUN_VALUE_OPTIONS else words[1:]
    if not words:
        return None
    if os.path.basename(words[0]) in {"pytest", "pytest.exe"}:
        return words[1:]
    if re.fullmatch(r"python[\d.]*(\.exe)?", os.path.basename(words[0])) and words[1:3] == [
        "-m",
        "pytest",
    ]:
        return words[3:]
    return None


def runs_whole_suite(arguments):
    for argument in arguments:
        if argument in NARROWING_OPTIONS or argument.startswith(("-k", "--lf", "--sw")):
            return False
        if argument.startswith("-"):
            continue
        if "::" in argument or "/" in argument or argument.endswith(".py"):
            return False
        if os.path.exists(argument):  # an app, such as `pytest news`
            return False
    return True


def commands(line):
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    command = []
    for word in lexer:
        if SEPARATOR.match(word):
            yield command
            command = []
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
            "or changed and those for the code you touched: name a path or node id, or use "
            '-k, --lf or --sw (docs/contributing/testing.md, "Running the tests").',
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
