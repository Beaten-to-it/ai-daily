# Task 8 Final Integration Adversarial Review

## Artifact

- Base commit and HEAD: `2ee3dc417cebc30db84fedf5d1affb4af2a3c661`
- Branch: `codex/windows-rebuild`
- Reviewed-scope files: 68
- Reviewed-scope composite SHA-256: `A9BE97F0BA5773FB2D74F4EF379A64953CBDF06E4F0B563FA06EFD8ADC6C697E`
- Valid review session: `f1d57431-55b7-4baa-9b5d-d36764f2bfd7`
- Result UUID: `b8209535-8f34-4339-9c31-da79456510ff`
- Requested and resolved model: `claude-opus-5`
- Effort: `xhigh`
- Duration: `705500 ms`
- Mode: read-only `Read,Grep,Glob`, plan permission mode, no session persistence

`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` was set. `modelUsage` contained
only `claude-opus-5`; there was no fallback or auxiliary model. The composite
digest and HEAD were rechecked after review and remained unchanged.

## Gate Result

- Critical: 0
- High: 0
- Medium: 6
- Low: 9
- Gate: passed

The reviewer found no supported integrity-gate bypass. Git-state reads,
completeness checks, rollback, push classification, and independent email
publication checks fail closed. Passing this code gate does not authorize live
shadow or activation; the blockers below remain.

## Findings and Independent Disposition

| ID | Severity | Finding | Independent disposition |
|---|---|---|---|
| M1 | Medium | `build_verify` scans the whole RSS XML for non-daily route strings, while `smoke_build.sh` checks only `<link>` elements. An escaped daily summary may legitimately contain article URLs and trigger a false failure. | Accepted as the first real-Hugo gate. Static inspection makes the false-positive plausible, but Hugo is unavailable so it is not claimed reproduced. Scope the production check to RSS item link/guid elements if the first render confirms it. |
| M2 | Medium | A model-authored YAML block-scalar title can make an indented provenance-looking line appear as a key to the stdlib parser while Hugo treats it as title text. | Accepted value-layer hardening backlog. Local generation/result provenance remains authoritative and no route or credential boundary is crossed. Reject block-scalar titles before live activation if real-model output demonstrates the form. |
| M3 | Medium | `StartWhenAvailable` catch-up tasks compute their dates independently; a late login crossing midnight can prepare one date and publish the next. | Accepted release blocker for catch-up operation. Normal 06:00/07:00 KST runs are consistent. Pin a cycle date or define a checkpoint-date adoption rule before relying on catch-up. |
| M4 | Medium | Push does not require the configured publish branch, so enabling tasks on the current feature branch could fast-forward `origin/main`. | Accepted release blocker. No tasks exist and operations require review/commit first, but the activation checklist must require merge/switch to `main` or a code-level publish-branch assertion. |
| M5 | Medium | Staging `--contentDir` excludes legacy content and section indexes, so shadow cannot prove the documented legacy-RSS exclusion; production/CI still can. | Accepted documentation/evidence mismatch. Do not claim legacy-feed coverage from staging shadow; verify it in a full real Hugo build before activation. |
| M6 | Medium | Installer discovers and prints an absolute Python but the task later re-resolves bare `python`; it also does not test imports. | Current interpreter independently imports `feedparser`, `requests`, and `googleapiclient`, so this host is ready now. Pin the interpreter and dependency probe before activation to prevent PATH/venv drift. |
| L1 | Low | Completeness does not repeat duplicate-key and long-copy checks performed during generation. | Defense-in-depth backlog. The staged bytes are hash-bound and normal generation already applies both checks. |
| L2 | Low | Site-tree cleanliness does not detect an uninitialized theme or section-index drift. | Theme is independently confirmed uninitialized (`git submodule status` begins `-`). This is an explicit live-shadow blocker; `git submodule update --init --recursive` is required. Hugo absence also fails closed. |
| L3 | Low | Synthetic E2E stubs Hugo and article rendering. | Accepted and documented. It proves orchestration and no external mutation, not real rendering. A real-Hugo test is mandatory after installation. |
| L4 | Low | Legacy WSL/Claude shell scripts remain beside Windows scripts. | They are outside the supported Windows entrypoints and retained for rollback history. Operators must use only the documented `.ps1` commands until WSL retirement is separately approved. |
| L5 | Low | No orchestration wall-clock cap guarantees prepare finishes by 07:00. | Source/model operations have local timeouts and retries cover bounded delay, but 3-5 shadow days must measure completion time. |
| L6 | Low | A correct zero-article hold exits 2 and therefore consumes publish retries. | Accepted conservative behavior: 0 articles must not publish. Task-history noise is preferable to accidental success until scheduler semantics are empirically verified. |
| L7 | Low | Email has a second, looser front-matter stripper. | Current daily content is locally constructed and cannot contain a delimiter line. Reuse the shared parser as later cleanup. |
| L8 | Low | Checkpoint contains less diagnostic detail than `run.json`. | Accepted; the run manifest is the diagnostic artifact and the checkpoint is the minimal resume authority. |
| L9 | Low | Email ledger can resend after ledger loss or a send-success/record-failure crash. | Carried residual risk. The external ledger and origin publication check reduce but do not remove the ambiguity. |

Medium and Low findings do not trigger an automatic correction or another
review round. M1, M3, M4, M5, and M6 are explicit live-shadow/activation
decisions. M2 is content-fidelity hardening rather than an integrity gate.

## Prior Finding Closure

- Task 6 M2: anchored fences and article/derived exact key allow-lists are
  closed; M2 above is a narrower value-layer limitation.
- Task 7 F1, F2, F3, F4, F6, F7, F8, F9, and F10: closed.
- Task 7 F5: deliberately open pending target-host retry evidence.
- Task 7 F12: partially closed by a populated synthetic E2E; real Hugo remains.
- Task 7 F13: partially closed by the clean site-tree gate; uninitialized theme
  and section indexes remain outside that check.

## Verification

- Full suite: `326 passed`
- Synthetic end-to-end: `1 passed`
- Python compileall: passed
- PowerShell parser checks: passed
- `git diff --check`: passed (line-ending conversion warnings only)
- Missing-checkpoint PowerShell wrapper: exit `4`
- Installer WhatIf: exit `1` on missing Hugo; scheduled task count stayed `0`
- Current Python dependency imports: passed for `feedparser`, `requests`, and
  `googleapiclient`
- Theme submodule: not initialized
- Hugo: absent from Windows PATH
- No content publication, commit, push, email, task registration, Hugo install,
  or WSL timer change occurred

## Live Shadow and Activation Blockers

1. User-approved Hugo Extended installation or an approved existing binary.
2. Initialize the PaperMod submodule and run a real full/staging Hugo build.
3. Resolve M1 using the rendered RSS, then prove daily-only home feed.
4. Review/commit the implementation, merge or switch to the approved publish
   branch, and close M4.
5. Pin task interpreter/dependencies and define cross-midnight catch-up date
   behavior (M3/M6).
6. Observe Task Scheduler retry behavior on the target host.
7. Complete 3-5 consecutive shadow days with no commit/push/email.
8. Obtain separate approvals for task registration, activation, first live
   publish/email, and WSL timer shutdown.
