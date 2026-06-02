# Project guidance for Claude Code

This repository's coding rules live in `.cursor/rules/` (Cursor's `.mdc`
format). Read those files instead of duplicating their content here, so the
user only maintains one set.

## Rule loading protocol

Each rule file has YAML frontmatter:

```
---
description: <selection hint>
alwaysApply: true | false
---
```

Before any non-trivial code change, **enumerate every rule file** with
`Glob ".cursor/rules/*.mdc"` — never rely on a hard-coded list, since files are
added, renamed, and removed over time. For each file found:

1. Read its YAML frontmatter (`description` + `alwaysApply`).
2. If `alwaysApply: true` — read the whole file and follow it for the rest of
   the session.
3. If `alwaysApply: false` — judge from the `description` whether it applies to
   the current task. If yes, read the whole file before continuing. If unsure,
   read it anyway — a brief read is cheaper than a missed rule.

This way new rule files added by the user take effect immediately without
requiring an edit to `CLAUDE.md`.

## Conflicts

If a rule conflicts with a direct user instruction in the current session, the
user wins. Flag the conflict so they can decide whether to update the rule.

If two rules conflict, the more specific one wins (e.g. a language- or
domain-specific rule over a language-agnostic one).
