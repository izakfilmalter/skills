---
name: feature-to-pr
description: Feature-to-PR workflow. Use when a request adds net-new or intentionally changed behavior; route presentation-only changes directly and substantial work through researched tracer bullets, behavioral validation, adversarial review, and a GitHub pull request.
argument-hint: "[feature context]"
---

# Feature to PR

The finish line is a ready-for-review pull request. Invoke the installed `/request-to-pr` skill through the harness's native skill mechanism for shared intake, project evidence, remediation, PR, and response gates. If a parent workflow supplied context, preserve that parent and return the PR to it for completion.

## 1. Establish the feature brief

A feature adds net-new behavior or intentionally changes existing behavior. If the request reports behavior failing its current promise, invoke `/bug-to-pr` with the same context and parent lifecycle. Ask one focused question only if the desired behavior remains consequentially ambiguous after inspecting the request and code.

Add the user-visible outcome and acceptance behaviors to the request brief.

**Complete when:** request intake passes and the outcome, acceptance behaviors, and feature classification are explicit.

## 2. Reconnaissance and sizing

Run the project evidence gate. Add exact candidate files and symbols, reusable patterns, acceptance-to-test mapping, dependencies, risks, validation commands, and a size recommendation.

- **Tiny:** a localized copy, color, spacing, position, or similarly mechanical presentation change with no new state, data flow, API, schema, permissions, reusable abstraction, or cross-package behavior.
- **Substantial:** everything else. Choose substantial when uncertain.

**Complete when:** the evidence packet is complete, every acceptance behavior maps to an edit and test surface, and sizing is justified.

## 3A. Tiny change

Implement only the localized change. Inspect the integrated diff and run mandatory checks plus concrete visual or runtime verification.

**Complete when:** the requested change is observable and the diff contains no incidental refactor. Continue at Step 5.

## 3B. Substantial tracer bullets

Turn acceptance behaviors into ordered vertical tracer bullets. For each bullet, use a fresh implementation worker when supported; otherwise work directly. Follow cited patterns, write one behavior-level test, prove red while the behavior is absent, implement only enough to turn it green, and run neighboring checks. Reuse existing modules instead of copying internals.

A substantial frontend feature requires an end-to-end test of its primary user journey. If the existing harness cannot exercise it, ask whether to add the support or accept a named alternative.

**Complete when:** every acceptance behavior is green through a public or user-visible seam and each bullet records its test path, exact red and green commands/results, and neighboring-check result.

## 4. Prove and review

Inspect the integrated diff. Run focused behavior tests and required lint, type, broader test, runtime, or end-to-end checks. Then conduct two independent read-only reviews, in parallel when supported:

- **Acceptance:** try to falsify every acceptance behavior and find missing journeys, wrong semantics, weak tests, or unrequested behavior.
- **Minimality:** compare every hunk with cited project patterns and find unnecessary abstractions, duplication, scope creep, or smaller idiomatic solutions.

Run the review-remediation gate.

**Complete when:** every acceptance behavior has observable evidence, required checks are green, and both review axes have no unresolved blocking findings.

## 5. Open the pull request

Run the pull-request gate. Add acceptance behaviors and adversarial-review status to the body. Run the final-response gate unless a parent workflow owns completion.

**Complete when:** the ready-for-review pull request exists and its URL reaches the direct response or parent workflow.
