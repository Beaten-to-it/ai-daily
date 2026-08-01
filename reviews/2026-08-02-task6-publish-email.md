# Task 6 Publish and Daily Email Adversarial Review

## Artifact

- Base commit: `2ee3dc417cebc30db84fedf5d1affb4af2a3c661`
- Branch: `codex/windows-rebuild`
- Reviewed-scope composite SHA-256: `BC3C6AF4C5AB33DABE7EF4DCEC1F0695B5765DD2973665D6869950ABF89324DF`
- Valid review session: `c0ebe706-e590-4d6b-ae6c-939eb2ad307d`
- Result UUID: `2c9d8bc9-094e-4411-95f9-c953eb1d9cc7`
- Requested and resolved model: `claude-opus-5`
- Effort: `xhigh`
- Duration: `563077 ms`
- Mode: read-only `Read,Grep,Glob`, plan permission mode, no session persistence

`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` was set. `modelUsage` contained only
`claude-opus-5`; no fallback or auxiliary model occurred. The composite digest
was rechecked after review and remained unchanged.

An earlier session (`f2accf0b-e2ef-49dd-942a-f3b8db27f816`, result UUID
`fae7f282-f637-4fa2-a00a-37fc52d0f69e`) is invalid and is not counted: its
`modelUsage` included `claude-haiku-4-5-20251001` in addition to Opus 5. The
valid retry changed the execution contract by disabling nonessential traffic.

## Gate Result

- Critical: 0
- High: 0
- Medium: 2
- Low: 6
- Gate: passed

The reviewer confirmed that legacy `posts/news/ax/usecase` paths are absent
from the new date write set and promotion flow, the 0 / 1-9 / 10+ publication
policy is correct, default email reads only committed `daily`, Windows secret
paths and POSIX permission guards are separated, and Task 5 findings F1, F2,
F3, F5, F7, and F9 are closed.

## Findings and Independent Disposition

| ID | Severity | Finding | Independent disposition |
|---|---|---|---|
| M1 | Medium | `nbs.schedule._writeset` still checks legacy routes, so its early preflight misses dirty new-route files. | Accepted for Task 7, which owns scheduler entrypoints. The correct `publish.preflight_clean(date_writeset(gen))` still fails before promotion, so this is wasted collection/model work rather than an integrity bypass. Task 7 must migrate or remove the duplicate write-set before its review. |
| M2 | Medium | Front-matter fence detection uses an unanchored substring search and permits unknown keys, allowing validators to see a truncated prefix while Hugo may interpret later keys such as `aliases`. | Reproduced locally: `validate_blog_output` returned no errors and `parse_frontmatter_strict` stopped at `pad: a --- b`, hiding a later duplicate `source_url` and `aliases`. Hugo alias impact is not live-verified because Hugo is unavailable. Accepted as mandatory pre-shadow hardening in Task 8; no live publish may be enabled before an anchored fence parser, key allow-list, and Hugo regression pass. |
| L1 | Low | CI smoke build checks only legacy fixtures. | Task 8 operations and end-to-end gate. Add new route assertions before shadow acceptance. |
| L2 | Low | Home RSS is not demonstrably daily-only from `mainSections`. | Task 8. Add a daily-scoped RSS template and rendered-feed check if live Hugo confirms the default mix. |
| L3 | Low | `source_health_warnings` is read by publish but never propagated into `generation.json`. | Task 7 checkpoint/manifest work should carry the warning summary forward; collect's `source_health.json` remains the current durable evidence. |
| L4 | Low | Direct `stage.run` accepts an unvalidated date. | Carried Task 5 F4; Task 7 CLI validation owns this boundary. Tighten date regexes to ASCII digits at the same seam. |
| L5 | Low | Homepage and README prose still describe the retired structure. | Task 8 documentation cleanup. |
| L6 | Low | `build_verify` hardcodes `/ai-daily/` instead of deriving the base path. | Task 8 Hugo hardening; current mismatch fails closed. |

Medium and Low findings do not trigger an automatic correction or another
Task 6 review round. M1 and L4 are Task 7 acceptance items. M2 is a hard gate
before any live shadow/publish authorization in Task 8.

## Residual Risks

- Hugo is absent from Windows PATH, so real route rendering, RSS membership,
  alias behavior, and PaperMod integration remain unverified. A real publish
  currently fails closed and rolls back.
- A manual edit during the interval between publish preflight and rollback can
  still be overwritten; orchestrated runs are lock-protected and operations
  must preserve the no-manual-edit window.
- Email idempotency depends on the external local CSV ledger; a lost ledger or
  send-success/record-failure interval can resend a day.
- A forced empty rerun can overwrite the local recovery manifest for an
  already-published date while leaving committed content intact.
- Windows token ACL guidance remains an operations-document requirement.

## Verification

- Task 6 targeted tests: `141 passed`
- Affected content tests: `70 passed`
- Full suite before and after review: `303 passed`
- `python -m compileall -q nbs scripts`: passed
- Three JSON schemas parsed successfully
- Task 6 legacy-route scan: clean
- `git diff --check`: passed (line-ending conversion warnings only)
- Hugo executable was not available on Windows PATH; no live Hugo result is claimed
- No content, commit, push, email, scheduler, or publication action occurred
