---
name: bug-to-pr
description: Bug-to-PR workflow. Use when existing or promised behavior produces the wrong result; route presentation-only corrections directly and substantial bugs through a regression test, evidence-backed implementation, adversarial review, and a GitHub pull request.
argument-hint: "[bug context]"
---

# Bug to PR

The finish line is a ready-for-review pull request. Invoke the installed `/request-to-pr` skill through the harness's native skill mechanism for shared intake, project evidence, remediation, PR, and response gates. If a parent workflow supplied context, preserve that parent and return the PR to it for completion.

## 1. Establish the bug brief

A bug is existing or promised behavior producing the wrong result. If the request asks for net-new or intentionally changed behavior, invoke `/feature-to-pr` with the same context and parent lifecycle. Ask one focused question only if expected behavior remains consequentially ambiguous after inspecting the request and code.

Add actual behavior, expected behavior, reproduction clues, and affected users to the request brief.

**Complete when:** request intake passes and the actual/expected distinction and bug classification are explicit.

## 2. Reconnaissance and sizing

Run the project evidence gate. Add exact candidate files and symbols, analogous patterns, targeted and broader validation commands, and a size recommendation.

- **Tiny:** an explicit localized copy, color, spacing, position, or similarly mechanical presentation correction with no state, data flow, logic, API, schema, permissions, reusable abstraction, cross-package behavior, or uncertain cause.
- **Substantial:** everything else. Choose substantial when uncertain.

For a substantial bug, also enumerate the execution path, rank root-cause hypotheses with evidence, and identify the narrowest behavior-level test seam.

**Complete when:** the evidence packet and sizing decision are justified and every substantial claim maps to an execution path and test seam or is explicitly unresolved.

## 3A. Tiny correction

Implement only the localized correction. Inspect the integrated diff and run mandatory checks plus concrete visual or runtime verification.

**Complete when:** the defect is visibly corrected and the diff contains no incidental refactor. Continue at Step 6.

## 3B. Make a substantial bug red

Use a fresh implementation worker when supported; otherwise work directly. Write the smallest regression test through a public or user-visible seam. Follow the repository's test patterns, change no production code, and prove the test fails for the reported symptom rather than a nearby failure.

If no faithful automated seam exists, stop before fixing and request the missing artifact, access, or clarification.

**Complete when:** the regression test reliably fails for the reported behavior and would pass only when that behavior is corrected.

## 4. Fix with tracer bullets

Treat the regression test as the first red-green tracer bullet. Add another vertical bullet only for another observable behavior. For each bullet, implement only enough to turn its behavior-level test green, then run neighboring checks. Preserve existing red tests and avoid unrelated files.

**Complete when:** the original regression test remains unchanged and green, the symptom no longer reproduces, and each bullet records its test path, exact red and green commands/results, and neighboring-check result.

## 5. Prove and review

Inspect the diff. Run the targeted regression test and required lint, type, broader test, runtime, or end-to-end checks. Then conduct two independent read-only reviews, in parallel when supported:

- **Correctness:** try to falsify every claim, verify the pre-fix red evidence and real test seam, and check that the cause—not only the symptom—is fixed.
- **Minimality:** compare every hunk with cited project patterns and find unnecessary code, test overreach, duplication, or scope creep.

Run the review-remediation gate.

**Complete when:** observable evidence proves the fix, required checks are green, and both review axes have no unresolved blocking findings.

## 6. Open the pull request

Run the pull-request gate. Add the reported behavior and fix to the body; for substantial bugs include root cause and regression-test seam, and for tiny bugs include visual or runtime evidence. Run the final-response gate unless a parent workflow owns completion.

**Complete when:** the ready-for-review pull request exists and its URL reaches the direct response or parent workflow.
