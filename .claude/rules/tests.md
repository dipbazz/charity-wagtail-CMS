---
paths: ["**/tests/**/*.py", "**/conftest.py"]
---

# Tests

Read `docs/contributing/testing.md` before writing or moving a test. The rules missed most, each
written once in the docs:

- Where a test goes: testing.md, "Where tests live".
- Addresses: the reserved domains in `docs/contributing/demo-content.md`, "The charity is
  fictional".
- Editors' powers are tested as `editor`, never `admin_client`: testing.md, "How to write them".
- Run tests by path, node id or `--lf`: testing.md, "Running the tests".
