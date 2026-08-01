# Task 5 Content Separation Adversarial Review

## Artifact

- Base commit: `2ee3dc417cebc30db84fedf5d1affb4af2a3c661`
- Branch: `codex/windows-rebuild`
- Task 5 composite SHA-256: `2AA82AF34D600857B926AB65A0A17F4B802ADDDD31699A8D14414C83FDA380C0`
- Valid review session: `59e5efbe-60e3-43a2-96bd-389d7534098f`
- Result UUID: `a87cf540-40aa-4eeb-994a-72f1bfcb5b1e`
- Requested and resolved model: `claude-opus-5`
- Effort: `xhigh`
- Duration: `348529 ms`
- Mode: read-only `Read,Grep,Glob`, plan permission mode, no session persistence, prompt suggestions disabled

`modelUsage` contained only `claude-opus-5`; no fallback or auxiliary model occurred. The composite digest was rechecked after review and remained unchanged.

| File | SHA-256 before and after review |
|---|---|
| `hugo.toml` | `75426F5D012E2F4CA7F05EC95BE1A6D09BA3BE50440FF59492BDFE233FD156E4` |
| `nbs/generate.py` | `FCF1370F3DCAEEEE32B2C71ADA273FF925BB5D97602F25E55DC822073939C8B5` |
| `nbs/models.py` | `1BF5CA5FE1919BC4E7A9FE9F2BAEDCA65C343517781493A31733B31C865FC549` |
| `nbs/assemble.py` | `27EA17BA80E5448A1E4A3878EBF75F16B2AE12F4445E9D713A5FD6EAD80908B8` |
| `nbs/stage.py` | `C03CB070C82A907032932FF8E9C0A6C5D3F74B787BB96182E8356AD382C9F986` |
| `nbs/publish.py` | `B51BF3F537D82528A912619A1AE34B0FD2B68ABC5F8EF254A30CAFE155AABCF8` |
| `nbs/email.py` | `96CD3451CE8D04CCFF368ED296C871A609440F70045D99E9BAD60EEF36C3B887` |
| `nbs/orchestrate.py` | `58ADB65B3498C25258D2E7F36D3915B2BF3E27CD1C7352AB211AF1B682432B66` |
| `prompts/blog.md` | `233BEC7541158A947B37F19EA9ECD2308B09F742683F6ACE917D2233ED6AD01E` |
| `prompts/ax.md` | `46A2A7B78AB4A6AEF958A375849233869588CC5FA7520AEBBEF0AA96F29A9015` |
| `prompts/usecase.md` | `2E908B4A9B472FF39424DB9832F95E0F3568828381E7B0990AC8E893058B0F29` |
| `schemas/article.schema.json` | `7F67C8C818DEECE14969B0A5E9926304561A98801CC0D73749AA343D9080BB83` |
| `schemas/derived.schema.json` | `6BB473710244FCA4872D9BB6B4D35721F7F67984F8497819B4D1681A18DB2B21` |
| `tests/test_generate.py` | `F45A0925645E20126805129FFCDE4C63F09CDBB596649685B4772CC0DE84B68E` |
| `tests/test_models.py` | `4BC4403ED300364E0C0A80C1EE969E993831830DF707ED768CC6CE2C642FD19D` |
| `tests/test_assemble.py` | `60A0AEA24BF0A5FDD67A6BC60908A2E3115CE3B48736CEA681C89BBDB73361C9` |
| `tests/test_stage.py` | `227112C386C0E4DC2F94163E63D095B227CB725DB9FF35FFC556DF50C92491AD` |
| `tests/test_ax.py` | `116FD51B47E8906111B57A5A1A2C7DA9895D8BAC9458826BD7373898E1143832` |
| `tests/test_content_routes.py` | `703D37B7F3D8755196C87895CD7B79FC317460B2CF9F19B8079F4C8266F702E5` |
| `tests/test_hardening.py` | `5B7275D4908780C9B45988CECD85018830F1C02BC7C72C07C41CBB1A8A8D2F9A` |
| `tests/test_publish.py` | `F3A85445BD8767300E9A2C73D15E26678AAAA55B92B7B4B8B326BAB6D85D402A` |
| `docs/superpowers/specs/2026-08-01-codex-windows-publisher-design.md` | `0F7BC8F4856EDE1ECDA23034C2FFB699B97AE3BE3ACB59B3F461E6D7E827692A` |
| `docs/superpowers/plans/2026-08-01-codex-windows-publisher.md` | `2B4E99F206920E948DFA404A7FCCF053EC6F0928224D6852AC805C144579F608` |

## Gate Result

- Critical: 0
- High: 0
- Gate: passed

The reviewer confirmed disjoint `articles`, `daily`, `executive`, and `guides` staging; an uncapped 30-article target; warning publication for 1-9 articles; no daily/derived output at zero; deterministic optional derived output; local provenance checks; current-article slug allowlisting; and fail-closed separation from the still-legacy Task 6 publisher and email paths.

## Findings and Independent Disposition

| ID | Severity | Finding | Independent disposition |
|---|---|---|---|
| F1 | Medium | `build_daily` writes candidate titles and model rationales into Markdown without escaping link or shortcode syntax. | Accepted into Task 6 before publication wiring. Add hostile title/rationale tests, neutralize Markdown/shortcode control syntax, and keep article relrefs locally constructed. The code inspection supports the finding; current Task 5 only stages files and cannot externally publish them. |
| F2 | Medium | Executive/guide summary inputs are not fenced or explicitly marked as untrusted, so source titles and generated snippets can steer the derived model. | Accepted into Task 6 pre-publication hardening. Reuse the existing source delimiter neutralization contract and test instruction-like summaries. Slug allowlisting currently bounds link integrity. |
| F3 | Medium | `render_blog` does not require front-matter `date`, `source_type`, or `evidence_level` to equal locally owned inputs. | Accepted into Task 6 before the new publisher trusts these fields. Add equality checks and targeted mismatch tests in generation rather than relying on the legacy publisher. |
| F4 | Medium | Direct `stage.run` does not validate its date before using it as a path and before deleting stale staging. | Duplicate of Task 4 M1 and retained for Task 7 CLI validation. Normal orchestration validates the date; a destructive result requires a contrived direct-call target and remains scratch-scoped. |
| F5 | Medium | The no-original-body contract is prompt-only; headings and substantial source overlap are not deterministically rejected. | Accepted into Task 6 content validation. Add required-heading checks and a bounded overlap test designed to avoid rejecting ordinary names and short factual phrases. No naive full-text or quadratic comparison will be added without a false-positive test corpus. |
| F6 | Low | The Tags taxonomy intentionally aggregates new and legacy content types. | Accepted behavior. Tags is the explicit cross-section discovery view; homepage, default list, RSS intent, and default email remain daily-only. Revisit only if shadow users find tags confusing. |
| F7 | Low | Daily link text uses the candidate title, which may not be Korean, rather than the generated Korean article title. | Accepted into Task 6 before publication. Read the validated generated front-matter title with candidate title only as a fail-closed fallback. |
| F8 | Low | A comment in `generate._mapped` inaccurately says stage skips all invalid keys. | Accepted as documentation cleanup in Task 6; behavior and tests are correct. |
| F9 | Low | Stage does not independently assert equality between daily-linked slugs and staged article files. | Accepted into the first Task 6 completeness gate, together with an explicit regression proving the legacy publisher/email remain fail-closed until rewired. |

Medium and Low findings do not trigger an automatic correction or another review round. F1, F2, F3, F5, F7, and F9 must be handled before Task 6 permits real publication. F4 remains at the Task 7 direct-CLI boundary.

## Accepted Task 6 Boundary

The legacy `nbs/publish.py`, `nbs/email.py`, `nbs/orchestrate.py`, and scheduler pathspecs still refer to `posts/news/ax/usecase`. This is the planned Task 6 migration, not a Task 5 defect. The current publisher fails completeness before promotion because new stage output has none of the three legacy artifacts it requires, and email independently gates on the absent origin `content/news/<date>.md`. No supported Task 5 entry point can publish mixed content.

## Verification

- Task 5 targeted tests: `79 passed`
- Additional affected integration tests: `4 passed`
- Full suite: `277 passed, 12 failed`; 11 pre-existing Windows publish/email failures plus one deferred old publisher expectation for the removed three-item floor
- `python -m compileall -q nbs`: passed
- JSON schema parsing: passed
- Task 5 legacy-route scan: clean
- `git diff --check`: passed
- Hugo executable was not available on Windows PATH, so no live Hugo build was claimed
- No content, commit, push, email, scheduler, or publication action occurred
