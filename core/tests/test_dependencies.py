import ast
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent
FEATURE_APPS = {"home", "campaigns", "news", "contact", "search"}


def imported_packages(path):
    packages = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            packages |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            packages.add(node.module.split(".")[0])
    return packages


def test_core_code_does_not_import_feature_apps():
    """Feature apps build on core, so core must work without any of them installed.

    Core's tests are exempt: core has no page types, so they render pages from feature apps.
    """
    offenders = {
        str(path.relative_to(CORE)): sorted(imported_packages(path) & FEATURE_APPS)
        for path in CORE.rglob("*.py")
        if "tests" not in path.relative_to(CORE).parts
    }

    assert {path: apps for path, apps in offenders.items() if apps} == {}
