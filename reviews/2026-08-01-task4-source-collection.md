# Task 4 Source Collection and Health Adversarial Review

## Artifact

- Base commit: `2ee3dc417cebc30db84fedf5d1affb4af2a3c661`
- Branch: `codex/windows-rebuild`
- Valid review session: `4c4a99a3-61e8-4313-888d-f3d273905704`
- Requested and resolved primary model: `claude-opus-5`
- Effort: `xhigh`
- Duration: `517860 ms`
- Mode: read-only, `Read,Grep,Glob`, no session persistence, prompt suggestions disabled
- Invalid prior session: `972264e8-81ce-4ce3-ae30-1be7172789af`; discarded because `modelUsage` included an auxiliary `claude-haiku-4-5-20251001` prompt-suggestion call.

`modelUsage` in the valid session contained only `claude-opus-5`; no fallback or auxiliary model occurred.

| File | SHA-256 before and after valid review |
|---|---|
| `nbs/sources.py` | `DE3DF61BEF587A77DEE5BECE6E8CB973FD41807355FD4094AF9C5688CEDE79DC` |
| `nbs/collect.py` | `AFDF051B2251CB92B9DE89AED2CD2525FE9C01DED6F01248EEF363259C79A9D3` |
| `nbs/models.py` | `3DD766586F2C39B400813415E71DEEFA617EC9CB029AD5E6AE5A10AE15752381` |
| `nbs/fetch.py` | `D165B71819B5448E961726A12F4F753364AD31C8A4483951982B5F99A07D45A3` |
| `nbs/schedule.py` | `157B40E3E294234B5A008CE5ACE2BB391FB39131AB14C456FDD2E63C95322F23` |
| `nbs/select.py` | `803EEC64524676CC4DCC92A80BA953BB0D127D14F0E36839FD3265A9AAB05165` |
| `nbs/stage.py` | `C1B339BC788C838E9FBFAB4A141A82EE376E8DC51406C2B108FD2002599DD779` |
| `nbs/orchestrate.py` | `58ADB65B3498C25258D2E7F36D3915B2BF3E27CD1C7352AB211AF1B682432B66` |
| `nbs/config.py` | `EB34FBEBA8DF34BF0F5329C105075649E6E6957449E92129A258465AF7B2FE59` |
| `tests/test_sources.py` | `85849469C4F5F55B8D3C0EDC0416990BA7F1A0DDF43B192868645073DD3EAE90` |
| `tests/test_collect.py` | `375320BF3E61AC8BFEB7B99F7E1B8BA725E2DCA6AB02D88E24C66B71B1D1D5FF` |
| `tests/test_source_health.py` | `B236D355402AE6406724ADEA7C7B640CD22E7A2ADD9D39B90C6B27EFDE55469E` |
| `tests/test_schedule.py` | `4E44642B5B9DC4AAD9D562FEEF8D4D35CE070D6C6A7F40EACD5B9AB362F53B17` |
| `tests/test_fetch.py` | `DEFDEFF5676975588523DB95FFA7E89ED3E207168FF4B340AB51189FA5ECED0B` |
| `tests/test_models.py` | `91BE9974220AB26B76477F4C10242523DDE9C30E3986DE1E371C6B225EFA06AB` |
| `tests/test_select.py` | `D40D7A32B6DAC5767BE925B7AF9044546B50E9832B240C67906B1524613D6A7D` |
| `tests/test_hardening.py` | `00F275886216B132218FFAACFC615A051E8DEA64EDDB775D8EA055C9FC5FADEC` |
| `docs/superpowers/specs/2026-08-01-codex-windows-publisher-design.md` | `0F7BC8F4856EDE1ECDA23034C2FFB699B97AE3BE3ACB59B3F461E6D7E827692A` |
| `docs/superpowers/plans/2026-08-01-codex-windows-publisher.md` | `2B4E99F206920E948DFA404A7FCCF053EC6F0928224D6852AC805C144579F608` |

The hashes were rechecked after the valid review and remained unchanged.

## Gate Result

- Critical: 0
- High: 0
- Gate: passed

The reviewer confirmed source-level failure isolation, health persistence, official/public API adapters, optional credential degradation, secret-safe redirects and error recording, original-link promotion, local social-snippet ownership, dedup-before-cap, and absence of a global selection cap.

## Findings and Independent Disposition

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| M1 | Medium | Direct collection/selection/stage CLIs do not validate the date before using it as a path and timestamp input. | Accepted into Task 7 checkpoint and CLI validation. The normal orchestrator validates dates; the direct malformed-input path is fail-closed for publication but can write scratch artifacts outside the intended run date. |
| M2 | Medium | Malformed elements in Bluesky, X, Reddit, GDELT, or GitHub payloads fail the whole source adapter; only HN has per-item degraded isolation. | Accepted into Task 8 hardening and corruption tests. Failure is visible and bounded to one source path. |
| M3 | Medium | Health records pre-dedup/pre-cap counts but not how many candidates finalization removed. | Accepted into Task 8 observability. Dedup-before-cap is implemented; loss accounting remains open. |
| M4 | Medium | Real X and Reddit missing-credential branches are not exercised by tests; a stub raises `Unconfigured`. | Accepted into Task 8 adapter contract tests. Live smoke independently observed all six optional paths as `unconfigured`. |
| M5 | Medium | Per-request deadlines exist but no aggregate collection wall-clock budget exists. | Accepted into Task 7 prepare-window control and Task 8 shadow timing. |
| M6 | Medium | Expanded downstream generation throughput has not been measured against the 06:00 to 07:00 window. | Accepted into Task 8 shadow acceptance; it requires live timing rather than speculative concurrency. |
| M7 | Medium | RSS aggregator entries still use the aggregator feed name/link instead of resolving the ultimate publisher. | Accepted into Task 8 provenance hardening. API/social promotion is complete; RSS resolution must remain bounded and SSRF-safe. |
| L1 | Low | RSS titles are not capped like API titles. | Accepted into Task 8 payload-boundary hardening. |
| L2 | Low | Per-source sorting uses raw timestamp strings; invalid strings admitted by the window check can outrank valid dates. | Accepted into Task 8 timestamp normalization. |
| L3 | Low | Authenticated GitHub redirects fail closed, so a renamed repository may be less available when a token is set. | Accepted security-first behavior; improve the diagnostic if encountered in shadow runs. |
| L4 | Low | Candidate and health artifacts are not written atomically. | Accepted into Task 7 checkpoint hardening. |
| L5 | Low | The legacy POSIX installer still documents Claude/opencli/twitter/Chrome assumptions. | Accepted into Task 7 Windows deployment replacement; it is not used by the Windows runtime. |
| L6 | Low | Aggregate warnings such as all-social-unavailable are not yet emitted. | Accepted into Task 6/7 manifest status and scheduling work. |
| L7 | Low | The legacy aggregate floor still conflicts with the approved 1-9 warning-publish policy. | Accepted into Task 5 volume-policy implementation. |

Medium and Low findings do not trigger automatic correction or another review round. There are no open Critical or High findings.

## Verification

- Task 4 and directly affected downstream tests: `109 passed`
- Full suite: `270 passed, 11 failed`; the same 11 pre-existing Windows publish/email failures remain
- Live read-only collection: `127` candidates from `31` source paths
- Live mix: official `19`, media `80`, developer `19`, social `9`; article `114`, repo `3`, sns `9`, video `1`
- Live integrity: duplicate candidate IDs `0`, invalid web URLs `0`, maximum per source `25`
- Live health: `15 ok`, `9 empty`, `1 failed` GDELT path, `6 unconfigured` X/Reddit paths
- `git diff --check`: no errors
- `runs/` artifacts are ignored; no content, commit, push, email, scheduler, or publication action occurred
