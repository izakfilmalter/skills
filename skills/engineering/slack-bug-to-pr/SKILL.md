---
name: slack-bug-to-pr
description: Turn a Slack bug thread into a diagnosed, tested, reviewed GitHub pull request and report the result back in the thread. Use when Slack reports existing or promised behavior producing the wrong result.
argument-hint: "[Slack URL]"
---

# Slack Bug to PR

1. Run the `/slack-to-pr` intake gate with the supplied Slack permalink.
2. Run `/bug-to-pr` with the resulting brief as its complete request context. This workflow owns completion, so receive the pull-request URL and evidence back from it.
3. Run the `/slack-to-pr` thread-update gate. Include:
   - the pull-request URL and a one-sentence summary;
   - a plain-language explanation of what users experienced and what is now fixed;
   - a technical explanation of the failure mechanism, root cause, and correction.
4. Run the `/slack-to-pr` preview and final-response gates.

If bug classification routes to `/feature-to-pr`, retain this Slack lifecycle and use a feature summary in the thread update.
If any step exits without a pull-request URL, run the `/slack-to-pr` blocked-exit gate before responding.

**Complete when:** the ready-for-review PR and Slack lifecycle are complete and the final line is the exact GitHub pull-request URL.
