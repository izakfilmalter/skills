# PR Workflow Skills

Composable agent skills that turn bug reports and feature requests into ready-for-review GitHub pull requests.

The collection has four task-facing skills and two reusable workflow primitives:

## Task-facing skills

- [`bug-to-pr`](./skills/engineering/bug-to-pr/SKILL.md) — diagnose a bug, prove it with a red test, fix it, review it, and open a PR.
- [`feature-to-pr`](./skills/engineering/feature-to-pr/SKILL.md) — deliver a feature as tested tracer bullets and open a PR.
- [`slack-bug-to-pr`](./skills/engineering/slack-bug-to-pr/SKILL.md) — run `bug-to-pr` from a Slack thread and report the result back there.
- [`slack-feature-to-pr`](./skills/engineering/slack-feature-to-pr/SKILL.md) — run `feature-to-pr` from a Slack thread and report the result back there.

## Reusable references

- [`request-to-pr`](./skills/references/request-to-pr/SKILL.md) — shared repository, evidence, review-remediation, PR, and final-response gates.
- [`slack-to-pr`](./skills/references/slack-to-pr/SKILL.md) — shared Slack intake, work-state, thread-update, and preview gates.

The reference skills are model-invoked primitives. The four task-facing skills compose them by name, following the same primitive/wrapper pattern used by `grilling` and `grill-me`.

## Install with skills.sh

Install the collection into a supported coding agent:

```bash
npx skills@latest add izakfilmalter/skills
```

Install all six skills when prompted. The task-facing skills depend on the reference skills in this repository.

## Install as a Claude Code plugin

Inside Claude Code:

```text
/plugin marketplace add izakfilmalter/skills
/plugin install izakfilmalter-skills@izakfilmalter
```

Or from a shell:

```bash
claude plugin marketplace add izakfilmalter/skills
claude plugin install izakfilmalter-skills@izakfilmalter
```

The plugin installs the complete skill stack, including both reference skills.

## Requirements

- Node.js 22.20 or newer when installing with the current `skills` CLI.
- A Git repository with a GitHub remote.
- An authenticated [`gh`](https://cli.github.com/) session with permission to push branches and create pull requests.
- The repository's normal development and test toolchain.
- For Slack workflows, a connected Slack integration that can read threads, post replies, and manage reactions. Reaction removal and deployment-preview posting degrade gracefully when unavailable.

Subagents improve separation between research, implementation, and review but are optional. Each skill specifies a direct-execution fallback for harnesses without subagents. Cross-skill references use the compact `/skill-name` notation from the Agent Skills ecosystem; harnesses that namespace plugin skills should resolve the installed skill by its native qualified name.

## Development

```bash
npm test
claude plugin validate . --strict
```

`npm test` checks skill metadata, docs, plugin coverage, cross-skill references, and version consistency.

## License

[MIT](./LICENSE)
