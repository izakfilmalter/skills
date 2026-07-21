---
name: slack-to-pr
description: Adapt a Slack thread into request context and report a completed pull request back to that thread. Use when another skill owns implementation but needs shared Slack intake, work-state, reply, and preview gates.
---

# Slack to PR

This is the Slack lifecycle primitive. The calling skill owns classification and implementation. Preserve its lifecycle while routing between bug and feature workflows.

## Slack intake gate

Use the connected Slack integration to read the permalink's message, root message, complete thread, and relevant attachments or linked artifacts. If required context is inaccessible, ask the user for it and stop rather than inferring a request from the URL.

Before repository work, add `hourglass_flowing_sand` to the root message and verify it. Build a request brief containing the Slack URL, requested outcome, affected surface, constraints, target repository, base branch, participants' acceptance statements, and unresolved ambiguity.

Pass that brief to the task-facing skill as its complete request context. The task-facing skill should use `/request-to-pr` for repository gates and return the resulting PR URL to this parent workflow rather than ending the conversation.

**Complete when:** the full Slack context is captured, the hourglass is verified on the root, and the caller has the request brief.

## Thread-update gate

After the pull request opens, reply in the original thread with its URL and the task-specific summary required by the caller. Read the thread back and verify the reply contains the correct URL.

Add `white_check_mark` to the root and verify it. If the connected integration can remove the agent's own reaction, remove `hourglass_flowing_sand` and verify the swap. Otherwise leave the verified green check in place and record that the hourglass could not be removed; never use unverified credentials or remove another user's reaction.

**Complete when:** the thread visibly contains the correct PR URL and summary, the green check is present, and the reaction-removal outcome is recorded.

## Preview gate

When the repository publishes deployment previews, wait for checks on the pull request's current head SHA. Prefer a successful preview check's URL. If a check links only to a CI run, inspect that run and logs for the emitted preview URL; never guess one or use a deployment from another commit.

After an initial 60 seconds, poll pending preview checks every 20 seconds for at most five minutes. On success, post and verify a second thread reply with the preview URL. On failure or timeout, post the status and check/run URL. If the repository has no preview integration, record that and skip this gate.

**Complete when:** the applicable preview URL or failure status is visible in the source thread, or absence of preview integration is established.

## Blocked-exit gate

Run this gate on every exit that does not produce a pull-request URL. Reply in the original thread with the exact blocker, completed evidence, and resumable branch or next action, then read back and verify the reply. Add `warning` to the root message. If authenticated reaction removal is available, remove the agent's `hourglass_flowing_sand`; otherwise record the limitation.

**Complete when:** the source thread visibly explains the blocked state, preserves the resumption point, and no longer presents an unexplained in-progress marker.

## Final-response gate

Return a concise completion summary and make the exact GitHub pull-request URL the final line.

**Complete when:** Slack lifecycle gates are done and the response ends with the ready-for-review PR URL.
