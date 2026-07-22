# Repository conventions

Skills live under `skills/engineering/`, `skills/references/`, and `skills/media/`. All are promoted buckets: every skill must appear in the top-level `README.md`, its bucket `README.md`, `.claude-plugin/plugin.json`, and the matching `docs/<bucket>/<skill-name>.md` page.

Every skill directory must contain `SKILL.md` and `agents/openai.yaml`. Skill frontmatter `name` must match the directory name.

`request-to-pr` and `slack-to-pr` are model-invoked primitives. Task-facing skills compose them with `/request-to-pr` and `/slack-to-pr` references. Keep shared behavior in the primitive rather than duplicating it in callers.

All skills are model-invoked. Descriptions must state the capability and a concrete invocation trigger. Keep each `SKILL.md` under 100 lines and references one level deep.

Bundled scripts must resolve relative to the installed skill directory rather than a harness-specific global path. Keep them dependency-light, declare runtime prerequisites, and write artifacts only to an explicit writable directory or a new operating-system temporary directory.

Keep `package.json` and `.claude-plugin/plugin.json` versions synchronized. Run `npm test` and `claude plugin validate . --strict` after changing skills or manifests.
