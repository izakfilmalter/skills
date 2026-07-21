# slack-bug-to-pr

```bash
npx skills add izakfilmalter/skills --skill slack-bug-to-pr slack-to-pr bug-to-pr feature-to-pr request-to-pr
```

[`slack-bug-to-pr`](../../skills/engineering/slack-bug-to-pr/SKILL.md) is a thin Slack adapter around `bug-to-pr`. It captures the complete Slack thread, marks work in progress, hands the resulting brief to the ordinary bug workflow, and reports the reviewed pull request back to the source thread with both plain-language and technical explanations.

It composes [`slack-to-pr`](../references/slack-to-pr.md), [`bug-to-pr`](./bug-to-pr.md), and—when classification changes—[`feature-to-pr`](./feature-to-pr.md).
