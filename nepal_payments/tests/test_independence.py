"""The package stands alone, so any Python project can install it and it can move to its own
repository unchanged: its code imports only the standard library and itself."""

import ast
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
ALLOWED = set(sys.stdlib_module_names) | {"nepal_payments"}
# Tests may also use pytest.
ALLOWED_IN_TESTS = ALLOWED | {"pytest"}


def imported_modules(path):
    """The top-level name of every module a file imports, leaving out relative imports."""
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield node.module.partition(".")[0]


@pytest.mark.parametrize(
    "path", sorted(PACKAGE.rglob("*.py")), ids=lambda path: str(path.relative_to(PACKAGE))
)
def test_imports_only_the_standard_library_and_itself(path):
    allowed = ALLOWED_IN_TESTS if "tests" in path.relative_to(PACKAGE).parts else ALLOWED

    assert set(imported_modules(path)) - allowed == set()
