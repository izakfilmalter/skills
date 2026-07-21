# Repository conventions

Skills live under `skills/engineering/` and `skills/references/`. Both are promoted buckets: every skill in either bucket must appear in the top-level `README.md`, its bucket `README.md`, `.claude-plugin/plugin.json`, and the matching `docs/<bucket>/<skill-name>.md` page.

Every skill directory must contain `SKILL.md` and `agents/openai.yaml`. Skill frontmatter `name` must match the directory name.

`request-to-pr` and `slack-to-pr` are model-invoked primitives. Task-facing skills compose them with `/request-to-pr` and `/slack-to-pr` references. Keep shared behavior in the primitive rather than duplicating it in callers.

All skills are model-invoked. Descriptions must state the capability and a concrete invocation trigger. Keep each `SKILL.md` under 100 lines and references one level deep.

Keep `package.json` and `.claude-plugin/plugin.json` versions synchronized. Run `npm test` and `claude plugin validate . --strict` after changing skills or manifests.
