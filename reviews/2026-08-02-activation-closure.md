# Activation Closure Review

## Artifact

- Base HEAD: `2ee3dc417cebc30db84fedf5d1affb4af2a3c661`
- Branch: `codex/windows-rebuild`
- Latest reviewed files: 65 changed or untracked regular files
- Latest composite SHA-256: `2B1F345F6764C67A477DA9C48BA0EA2A6F2EA7C171787B6DEB4D1BD4F8CFD200`
- Local verification: `335 passed`; real Hugo 0.164 RSS test included

## Full Review

- Session: `1c7377a2-4d35-4a59-8271-a300f4ca238b`
- Result UUID: `823d720c-dae8-4183-955e-cc5e2b2423c1`
- Duration: `813773 ms`
- Requested and resolved model: `claude-opus-5`
- Effort: `xhigh`
- Result: Critical 0, High 0, Medium 5, Low 9, PASS

`modelUsage` contained only `claude-opus-5`. The review used only Read, Grep,
and Glob in plan permission mode, with no session persistence. The tree digest
was unchanged after the review.

## Accepted Medium Disposition

| Finding | Disposition |
|---|---|
| Zero-article days failed validation before reaching the hold policy | Fixed: orchestration now returns `held` immediately after an explicit empty generation result. |
| Battery defaults could suppress Prepare, Publish, and Alert | Fixed: all task settings allow battery start and continuation. |
| Publish could commit locally before rejecting a non-main push | Fixed: `publish.run` rejects non-main before computing or promoting the write-set. |
| A hard kill during promote left a fail-closed dirty write-set without an operator procedure | Documented: the operations guide identifies the exact date-scoped paths and tracked/untracked recovery split. |
| Hugo had no wall-clock bound | Fixed: Hugo is bounded to 300 seconds and timeout returns a failed build. |

## Targeted Closure Review

- Session: `e4cb7603-f5d4-47c8-b435-936a7fff16f3`
- Result UUID: `3c221c30-1339-4492-90d1-b699d49f0dd8`
- Duration: `262277 ms`
- Requested and resolved model: `claude-opus-5`
- Effort: `xhigh`
- Result: Critical 0, High 0, all five Medium findings CLOSED, PASS

`modelUsage` again contained only `claude-opus-5`. The targeted reviewer found
no gating regression. The latest composite digest was recomputed after review
and remained unchanged.

## Residual Low Items

- The manual hard-kill recovery text does not spell out the staged-added but
  not-yet-committed variant; the next run still fails closed.
- A `--no-commit` preview from a feature branch is now rejected. This is not a
  supported Windows scheduled entrypoint and avoids mutating content there.
- The battery regression test is static rather than a live battery-state test.
- Existing non-gating backlog from the full review remains recorded for later
  hardening; it does not trigger another review round.

## Gate

Critical = 0 and High = 0 on the latest corrected artifact. The code and review
gate passes. Live publication still requires main integration, a validated
Prepare checkpoint, and successful external-state checks.

## Live Prepare Regression Closure

The first real Prepare generated 33 articles but Hugo rejected three model
outputs with one leading space before `date:`. The shared generation seam now
normalizes ASCII front-matter keys to column zero; the body remains unchanged.

- Parent HEAD: `321e6058309a675e355c2dd2d4980dd74bc815ec`
- Reviewed files: `nbs/generate.py`, `tests/test_generate.py`
- Composite SHA-256: `57B95B8F35EC8201CF89DBCB9C542A4D091F775B8EB25F56775EBC96BAC40C10`
- Session: `68c6b6b0-f4d4-43d0-89d9-bae4e16b7047`
- Result UUID: `57ded6d9-177e-4e9f-9379-926442cd4360`
- Duration: `277251 ms`
- Requested and resolved model: `claude-opus-5`
- Effort: `xhigh`
- Result: Critical 0, High 0, issue CLOSED, PASS

`modelUsage` contained only `claude-opus-5`. After mechanically applying the
same normalization to the ignored staging files, Hugo rendered all 33 articles
and the home RSS contained only daily item link/guid targets. The reviewer left
two Low follow-ups: add a standalone non-title indentation test, and share the
article duplicate-key guard with derived documents. Neither is gating.
