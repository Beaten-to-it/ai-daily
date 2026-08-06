# 2026-08-07 Publish Reliability Review

## Artifact

- Base HEAD: `ac25eb2171b83f06d1a600d68f97606a1d1e0c3a`
- Branch: `codex/fix-daily-publish-reliability`
- Reviewed working-diff SHA-256: `e502e8ee3c952831f6f4f9c759bac14908becbd55ad50a70d642596db9b7e9fa`
- Review session: `3c1c2025-34fa-458f-b973-337fe04b3c2b`
- Result UUID: `0e4252e5-fe09-47f9-843b-35f45fe4378f`
- Requested and resolved model: `claude-opus-5`
- Effort: `xhigh`
- Duration: `279581 ms`
- Mode: read-only `Read,Grep,Glob`, plan permission mode, no session persistence

`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` was set. `modelUsage` contained only
`claude-opus-5`; there was no fallback or auxiliary model. The working-diff
digest was recomputed after review and remained unchanged.

## Gate Result

- Critical: 0
- High: 0
- Medium: 2
- Low: 4
- Gate: passed

The reviewer confirmed that identical-only decision collapse does not mask
conflicting decisions or incomplete coverage, and that the daily recipient
change behaves as intended.

## Findings and Disposition

| Severity | Finding | Disposition |
|---|---|---|
| Medium | The new default recipient also inherits missed-publish alert mail through `nbs.schedule._send_alert`. | Accepted. Daily delivery and its failure alert intentionally share the same operator recipient list. |
| Medium | Identical decision collapse has no separate telemetry. | Deferred. The raw `last-message.json` retains the original model output, and adding a new warning channel is not required for this reliability fix. |
| Low | The JSON result reported four Low findings without expanding them in its final envelope. | No automatic action; Low findings do not gate this slice. |

## Verification

- Red phase: the duplicate-decision and new-recipient tests both failed before implementation.
- Focused regression: `2 passed`.
- Affected tests: `87 passed`.
- Full suite before review: `336 passed`.
- `python -m compileall -q nbs scripts`: passed.
- Three JSON schemas parsed successfully.
- `git diff --check`: passed with line-ending conversion warnings only.
- No publication, push, email, scheduler, or credential action occurred during review.
