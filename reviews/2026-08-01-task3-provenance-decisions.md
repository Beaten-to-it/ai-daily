# Task 3 Provenance and Decision Completeness Adversarial Review

## Artifact

- Base commit: `2ee3dc417cebc30db84fedf5d1affb4af2a3c661`
- Branch: `codex/windows-rebuild`
- Review session: `3cc0fd6d-d444-44bd-8d33-c5a88837d0d8`
- Requested and resolved primary model: `claude-opus-5`
- Effort: `xhigh`
- Duration: `485172 ms`
- Mode: read-only, `Read,Grep,Glob`, no session persistence

| File | SHA-256 before and after review |
|---|---|
| `nbs/models.py` | `06E4E3A8A6C9327123F45323208B83DA3456B3544398E0BCBFA6953892AECC9C` |
| `nbs/collect.py` | `3C14867439270E77F200F82FC75B138A5CA1DE6E9DA8F01AFADB9CDFFD1945FD` |
| `nbs/select.py` | `803EEC64524676CC4DCC92A80BA953BB0D127D14F0E36839FD3265A9AAB05165` |
| `nbs/ledger.py` | `714950296C870722E91FEDD6A640E42AB145A3B00AB7C46D03A62742C2914AB2` |
| `prompts/select.md` | `B217A02EF7617A72565748F05C29DFABA2D461E5F66837C612359D0400A1A3A2` |
| `schemas/selection.schema.json` | `B1B1E621915F2D6EABEECCC443FDFBFBC9842B531B105A055743E58510387BE2` |
| `tests/test_models.py` | `D9C05A6F735F808EA4AC04FD13A4BAD6BD667317E8866C7FECCF832E80D865C3` |
| `tests/test_collect.py` | `D09A3AB7CF2292FA2D6F89FBAA2B8BE295C9103511FC839C65188DD5D2222211` |
| `tests/test_select.py` | `53FFB377DA12AC1726A38344A3FD91D8D16E66C385B47BFFBB4E5D11A6D01AB2` |
| `tests/test_ledger.py` | `35D5C79CCD8A3999F7D0F5AC67017540DA0C371E8C896D189E76F6883F63D5AB` |
| `tests/test_hardening.py` | `C09D11DED3E3DC33411BEA817144B5FF99FC45972318A7138ABC863D49C3E5C5` |
| `docs/superpowers/specs/2026-08-01-codex-windows-publisher-design.md` | `0F7BC8F4856EDE1ECDA23034C2FFB699B97AE3BE3ACB59B3F461E6D7E827692A` |

The hashes were rechecked after review and remained unchanged.

## Gate Result

- Critical: 0
- High: 0
- Gate: passed

`modelUsage` contained only `claude-opus-5`; no fallback occurred. The reviewer confirmed complete candidate-to-decision coverage, locally owned provenance, locally derived event keys and counts, and removal of the selection ceiling.

## Findings and Independent Disposition

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| M1 | Medium | Non-empty materialization copies `generated_with` from the model while the local validator also recognizes `local-empty`. | Accepted into Task 8 defense-in-depth. The live output schema permits only `codex-exec`; the empty path is local and bypasses the model. |
| M2 | Medium | No positive mixed select/skip test proves skipped rows and non-zero `skipped_count` survive end to end. | Accepted into Task 8 end-to-end coverage. Implementation currently preserves all ordered decisions and derives the count locally. |
| M3 | Medium | `stage.py` consumes persisted `selection.json` without re-running `validate_selection`. | Accepted into Task 7 checkpoint validation and Task 8 corruption tests. |
| M4 | Medium | Cross-day duplicate prevention remains model-directed and the selector sees only 14 days of ledger context. | Accepted into Task 8 hardening. Add a deterministic full-ledger canonical URL check before shadow publication. |
| M5 | Medium | Candidate title and model rationale can inject Markdown structure into the aggregate page; ledger summaries re-enter the selector prompt. | Accepted into Task 5 content rendering and prompt-boundary work. Raw HTML remains disabled and integrity checks limit the current blast radius. |
| M6 | Medium | Aggregator feed names can be recorded as publisher names rather than the linked article's actual publisher. | Accepted into Task 4 source normalization. This directly affects the requested source/provenance quality. |
| M7 | Medium | Collection canonicalization and cap-before-dedup can silently discard distinct candidates before decision coverage. | Partially accepted into Task 4: deduplicate before per-source cap and record collection loss. Fragment removal is retained as normal URL canonicalization unless a verified source uses fragment-distinct articles. |
| L1 | Low | Selection prompt substitutes input before the date placeholder. | Accepted into Task 8 prompt hardening; current only-later replacement is the trusted date and has no integrity impact. |
| L2 | Low | `selection.json` is not written atomically. | Accepted into Task 7 checkpoint hardening. |
| L3 | Low | An intentional 80-bit candidate ID collision fails the day closed. | Accepted risk; availability-only and infeasible for ordinary feeds. |
| L4 | Low | Some provenance and no-cap tests are shallow or bypass the full selector. | Accepted into Task 8 end-to-end tests. |
| L5 | Low | Archived fenced-response parser is not on the live path. | Rejected as documented fixture and archive compatibility. |
| L6 | Low | Existing RSS feeds default to `official`, including media and research feeds. | Accepted into Task 4; all existing and new feeds must receive explicit lanes. |

Medium and Low findings do not trigger an automatic correction or another review round.

## Verification

- Task 3 plus downstream generation tests: `86 passed`
- Full suite: `263 passed, 11 failed` before two additional passing provenance regression tests; the same 11 Windows publish/email failures remain
- `schemas/selection.schema.json`: valid JSON
- `git diff --check`: no errors
