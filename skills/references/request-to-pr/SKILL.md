---
name: request-to-pr
description: Provide reusable repository intake, evidence, review-remediation, pull-request, and response gates. Use when another skill needs to turn a request into a ready-for-review GitHub pull request.
---

# Request to PR

This is the workflow primitive behind the task-facing PR skills. A caller may supply the request context and own the final response; otherwise use the invocation prompt and complete the response yourself.

Maintain one shared state object: request brief, repository, base branch, work branch, evidence packet, validation evidence, and pull-request URL. Give that state to every later worker.

## Intake gate

Record the requested outcome, affected surface, constraints, target repository, and base branch. Resolve the repository from the workspace, links, remotes, or project metadata. Ask one focused question only when required context is missing or multiple targets remain plausible.

Inspect Git status and the current branch before edits. Preserve user changes. Create or switch to a dedicated work branch; use an isolated worktree when unrelated changes would contaminate the pull request.

**Complete when:** the brief, target, base branch, and isolated work branch are explicit.

## Project evidence gate

Use a read-only reconnaissance worker when the harness supports one; otherwise inspect directly. Record exact paths and findings for every applicable source:

1. Scoped `AGENTS.md` or `CLAUDE.md` instructions and configured project references.
2. Context documents, ADRs, contribution rules, coding standards, and test configuration.
3. The nearest analogous implementation and tests.
4. Local reference repositories when present and relevant, without treating them as the edit target.
5. Current official documentation when project sources do not establish a library contract.

Later workers must receive the brief and evidence packet and cite the patterns they followed. Delegated workers may edit or review as assigned, but the main agent alone commits, pushes, and opens the pull request.

**Complete when:** every evidence category names inspected paths and findings or an evidence-backed reason it does not apply.

## Review-remediation gate

Disposition every review finding. Apply accepted findings and record evidence for rejected findings. After code or test changes, rerun the workflow's full validation and repeat an affected review when the patch changed materially.

**Complete when:** no blocking finding remains and the final integrated patch has passed full validation.

## Pull-request gate

Inspect `git status`, the full diff, recent commits, and the base-branch diff. Remove artifacts and unrelated changes; stage only intended files. Rerun required validation on the final tree. Commit, push the branch, and use `gh` to open a non-draft pull request using the repository template when present.

The body must summarize the outcome and implementation, list exact validation commands and results, disclose limitations, and include facts required by the calling skill.

**Complete when:** the pull request exists remotely and its URL is known. If credentials or permissions block creation, preserve the ready branch and report the exact failing command and error.

## Final-response gate

When called directly, return a concise completion summary and make the exact GitHub pull-request URL the final line. When a parent workflow owns completion, return the URL and evidence to that workflow instead.

**Complete when:** the direct response ends with the ready-for-review PR URL, or the parent receives the same URL and evidence.
