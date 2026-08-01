# Task 7 Checkpoint and Windows Scheduler Adversarial Review

## Artifact

- Base commit: `2ee3dc417cebc30db84fedf5d1affb4af2a3c661`
- Branch: `codex/windows-rebuild`
- Reviewed-scope files: 46
- Reviewed-scope composite SHA-256: `D47480BA79308083EE65608731FD671692EC31C1A0096680D548F873220BCACA`
- Valid review session: `eb34167e-5854-42cd-b788-6bd14248f2ce`
- Result UUID: `e05f1607-5087-4413-838a-4a9f37ea36bb`
- Requested and resolved model: `claude-opus-5`
- Effort: `xhigh`
- Duration: `700969 ms`
- Mode: read-only `Read,Grep,Glob`, plan permission mode, no session persistence

`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` was set. `modelUsage` contained
only `claude-opus-5`; no fallback or auxiliary model occurred. The composite
digest and Git HEAD were rechecked after review and remained unchanged. No
scheduled tasks existed before or after the review.

## Gate Result

- Critical: 0
- High: 0
- Medium: 6
- Low: 7
- Gate: passed

The reviewer confirmed that prepare-only cannot reach publish, push, or email;
publish-only binds date/version/validation, input bytes, Git HEAD, and a fresh
completeness check; CLI exit codes are defined; Windows scripts have no WSL
runtime coupling; and Task 6 M1 is closed. Task 6 L3 and L4 are only partially
closed as detailed below.

## Findings and Independent Disposition

| ID | Severity | Finding | Independent disposition |
|---|---|---|---|
| F1 | Medium | Prepare/shadow validation does not run Hugo, so a green checkpoint does not prove rendered routes or feeds. | Reproduced by code trace and consistent with the current missing-Hugo WhatIf result. Accepted as a mandatory Task 8 shadow-gate item. Publishing still runs Hugo before commit and fails closed. |
| F2 | Medium | All scheduled tasks use `Interactive`, so none run or alert while the user is logged off. | Accepted operational constraint. Task 8 must document the always-logged-on requirement and avoid claiming unattended logged-off coverage. Separate alert credentials/principal are deferred unless the user requests them. |
| F3 | Medium | After publish commits and push fails, retrying `--publish-only` rejects the checkpoint because HEAD changed, making push-only recovery unreachable from the scheduler. | Accepted as a Task 8 release-blocking recovery fix. There is no integrity loss, but the advertised retry path does not recover a transient post-commit push failure. Add a populated end-to-end regression before fixing. |
| F4 | Medium | `-Apply` registers the three tasks enabled, while the transition plan describes a later activation step. | Accepted documentation/installer mismatch. No tasks were registered. Task 8 must make activation semantics explicit before any authorized `-Apply`; live installation remains a separate approval gate. |
| F5 | Medium | Tests do not prove that Task Scheduler restarts an action solely because its process returns non-zero. | Accepted target-host validation gate. Static cmdlet construction is correct, but live retry behavior remains unverified because scheduler mutation was not authorized. Do not claim retry acceptance until a throwaway or shadow task is explicitly approved and observed. |
| F6 | Medium | Under PowerShell 7 native-error behavior, `$ErrorActionPreference='Stop'` can collapse Python exit 2/3/4 to wrapper exit 1. | Confirmed relevant only to an optional `pwsh` entry point; the installed task explicitly uses Windows PowerShell 5.1. Carry as Task 8 portability hardening or document `powershell.exe` as the supported shell. |
| F7 | Low | Source-health warnings reach `generation.json` and `publish.json`, but not checkpoint/run manifests used by shadow diagnosis. | Task 6 L3 is partially closed. Accepted for Task 8 manifest completion. |
| F8 | Low | Windows PowerShell stderr merging can make `codex login status` fail closed despite exit 0. | Unreproduced with the installed Codex on this host (`login status` exited 0). Carry as fail-closed installer hardening. |
| F9 | Low | Direct `collect` and `select` CLIs do not validate the date before constructing the run path. | Task 6 L4 is partially closed. Scheduled/orchestrated paths are guarded, but direct CLIs are supported diagnostics, so Task 8 should apply the shared ASCII date guard. |
| F10 | Low | Task times and default date use the host time zone while pipeline filtering uses KST. | Current host is Asia/Seoul/KST. Task 8 must assert or document the KST host requirement rather than add conversion machinery. |
| F11 | Low | `-Force` overwrites existing tasks with the same names without a pre-existing-task report. | No matching tasks currently exist. Add an apply-time collision check only if scheduler installation is authorized. |
| F12 | Low | PowerShell tests are mostly static and checkpoint fixtures are empty, reducing confidence in staged-tree hashing and wrapper behavior. | Accepted for Task 8 end-to-end coverage. CLI not-ready/flag tests were added before this review; populated staging and post-commit recovery remain. |
| F13 | Low | Checkpoint hash excludes dirty Hugo configuration/layout/theme files not represented by Git HEAD. | Accepted for Task 8 clean-tree/shadow gate. These files cannot enter the content-only publish commit, so impact is validation mismatch rather than silent deployment. |

Medium and Low findings do not trigger an automatic Task 7 correction or
another review round. F3 is mandatory before live scheduling because it breaks
the intended retry recovery. F1, F7, F12, and F13 are folded into the Task 8
shadow/evidence slice. F2, F4, F5, F6, F8, F10, and F11 are installation and
operations gates.

## Task 6 Carry-over Closure

- M1: closed. Scheduler write sets use `articles/daily/guides/executive`.
- L3: partially closed. Source health reaches generation and publish, but not
  the checkpoint/run manifest.
- L4: partially closed. Orchestrate, stage, publish, and PowerShell validate
  ASCII dates; direct collect/select still need the same guard.

## Verification

- Task 7 targeted tests after CLI coverage: `138 passed`
- Full suite immediately before review: `314 passed`
- `python -m compileall -q nbs tests`: passed
- `git diff --check`: passed (line-ending conversion warnings only)
- PowerShell parser checks: passed
- Installer WhatIf: printed the intended three tasks and failed closed on
  missing Hugo
- Task Scheduler state: `0` matching `AI Daily *` tasks before and after
- Legacy-route scan in Task 7 production/scripts: clean
- No content, commit, push, email, scheduler, or publication action occurred

## Residual Risks

- Hugo is absent, so no live render or RSS evidence exists.
- Scheduler retry semantics and logged-off behavior are not live-tested.
- The existing external email ledger still has a send-success/record-failure
  window.
- Task 6 front-matter fence/key hardening remains mandatory before any live
  shadow or publish authorization.
