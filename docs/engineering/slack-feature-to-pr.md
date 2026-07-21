# slack-feature-to-pr

```bash
npx skills add izakfilmalter/skills --skill slack-feature-to-pr slack-to-pr feature-to-pr bug-to-pr request-to-pr
```

[`slack-feature-to-pr`](../../skills/engineering/slack-feature-to-pr/SKILL.md) is a thin Slack adapter around `feature-to-pr`. It captures the complete Slack thread, marks work in progress, hands the resulting brief to the ordinary feature workflow, and reports the reviewed pull request back to the source thread.

It composes [`slack-to-pr`](../references/slack-to-pr.md), [`feature-to-pr`](./feature-to-pr.md), and—when classification changes—[`bug-to-pr`](./bug-to-pr.md).
