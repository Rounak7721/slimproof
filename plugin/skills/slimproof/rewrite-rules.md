# Rewrite rules

Goal: the shortest description that still says **what the tool does, when to pick it over similar tools, and any non-obvious constraint**.

## Never change
- Tool names, parameter names, types, `required`, `enum`, `default`, `const`, `examples`.
- Anything other than `description` and `title`. `compare` rejects every other change.
- The meaning. Never add a fact that isn't in the original, even a likely one.
- Hard constraints: allowed characters, limits, units, formats, error cases. Shorten their wording, never drop them.

## Keep
- The action and what it acts on: "Read a file", not "File tool".
- What makes this tool different from similar tools on the same server.
- Constraints the schema can't express: side effects, limits, auth, units, formats.

## Cut (IDs match slimproof's findings)
| Rule | Cut | Before → after |
|---|---|---|
| SP001 | Filler openers | "This tool allows you to read a file." → "Read a file." |
| SP002 | Repeating the tool name | "read_file: reads a file" → "Read a file." |
| SP003 | Restating a parameter's type | "path (string): the path string" → "File path, relative to the root." |
| SP004 | Prose that only lists enum values | "One of: asc, desc." → remove it; the schema already has the enum |
| SP005 | Markup and extra whitespace | headings, bullets, `**bold**`, blank lines → plain sentences |
| SP006 | Over-long descriptions (> 1000 chars) | tutorials, long examples, changelogs → one sentence each for purpose, choice, constraints |
| SP007 | Boilerplate repeated across tools | the same disclaimer or intro on every tool → keep it once; a constraint that applies to each tool stays on each |
| SP008 | Near-identical descriptions | **don't shorten**: add what makes each tool different |