---
name: slack-feature-to-pr
description: Turn a Slack feature thread into researched, tested, reviewed behavior in a GitHub pull request and report the result back in the thread. Use when Slack requests net-new or intentionally changed behavior.
argument-hint: "[Slack URL]"
---

# Slack Feature to PR

1. Run the `/slack-to-pr` intake gate with the supplied Slack permalink.
2. Run `/feature-to-pr` with the resulting brief as its complete request context. This workflow owns completion, so receive the pull-request URL and evidence back from it.
3. Run the `/slack-to-pr` thread-update gate with the pull-request URL and a concise plain-language summary of the behavior added or changed.
4. Run the `/slack-to-pr` preview and final-response gates.

If feature classification routes to `/bug-to-pr`, retain this Slack lifecycle and use the bug explanations required by `/slack-bug-to-pr` in the thread update.
If any step exits without a pull-request URL, run the `/slack-to-pr` blocked-exit gate before responding.

**Complete when:** the ready-for-review PR and Slack lifecycle are complete and the final line is the exact GitHub pull-request URL.
