---
paths: ["**/*.css", "**/templates/**"]
---

# Styles and layout markup

Load the `mobile-first` skill (`.claude/skills/mobile-first/SKILL.md`) before changing this file:
semantic markup first, then a 320px phone with no media query, then `min-width` queries in `rem`.
After a change to a stylesheet, a hook runs `core/tests/test_stylesheet.py` and reports a failure.
