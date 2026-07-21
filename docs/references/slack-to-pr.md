# slack-to-pr

```bash
npx skills add izakfilmalter/skills --skill slack-to-pr request-to-pr
```

[`slack-to-pr`](../../skills/references/slack-to-pr/SKILL.md) is the model-invoked Slack lifecycle primitive shared by both Slack adapters. It owns complete-thread intake, root-message work-state reactions, verified PR replies, optional reaction cleanup, and deployment-preview reporting.

It supplies request context to a task-facing workflow, which uses [`request-to-pr`](./request-to-pr.md) for repository work, then resumes the Slack lifecycle after the PR opens.
