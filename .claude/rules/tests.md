---
paths: ["**/tests/**", "**/conftest.py"]
---

# Tests

Read `docs/contributing/testing.md` before writing or moving a test. The rules that are missed
most:

- A module's own logic is tested in its own file (`test_mail.py` tests `core/mail.py`); a caller
  tests its use of it in the caller's files, and a regression test goes with the behaviour it
  tests.
- Addresses are reserved domains, one per role: `brightwell.example` for the charity,
  `example.org` / `example.com` for third parties, `localhost` only where the site runs locally.
- Test editors' powers as `editor`, never `admin_client`.
- Run tests by path, node id or `--lf`; CI runs the whole suite.
