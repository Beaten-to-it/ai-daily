# Task 2 Codex Exec Adversarial Review

## Artifact

- Base commit: `2ee3dc417cebc30db84fedf5d1affb4af2a3c661`
- Branch: `codex/windows-rebuild`
- Valid review session: `9c49929c-414a-4f7a-b611-3246a4a25902`
- Requested and resolved primary model: `claude-opus-5`
- Effort: `xhigh`
- Duration: `500718 ms`
- Mode: read-only, tools limited to `Read,Grep,Glob`, no session persistence

| File | SHA-256 before and after review |
|---|---|
| `nbs/codex_cli.py` | `13BCF388795C3C4F462E1B66CF8DF17808D7DE3B643C2520793D73E7425475B0` |
| `nbs/select.py` | `3AEFEBF950009FE41809D1C250F8CFD5D80EB4F91EC699E556CF5C92A2C190A0` |
| `nbs/generate.py` | `5C8DB11997F60C6A311ED0A06CF190516B3A4D8AE9462D5CD05D1B220AD428B9` |
| `nbs/assemble.py` | `3A1C1BCF06F8FE3D0CAFC68432706A3E77170351580CA5571201E3858E805C44` |
| `nbs/publish.py` | `B51BF3F537D82528A912619A1AE34B0FD2B68ABC5F8EF254A30CAFE155AABCF8` |
| `prompts/select.md` | `4D53E4DD0252B39E34C6587A360384780A017905EC8D5DD15E886729561B36DC` |
| `schemas/selection.schema.json` | `A18C94D1FDCE0ACA0A3E078B87D9A852BB58714FC27242475963860C8A6801D0` |
| `schemas/article.schema.json` | `7F67C8C818DEECE14969B0A5E9926304561A98801CC0D73749AA343D9080BB83` |
| `schemas/derived.schema.json` | `6BB473710244FCA4872D9BB6B4D35721F7F67984F8497819B4D1681A18DB2B21` |
| `tests/test_codex_cli.py` | `356388DA232879C2CD20ACE35E419651B47C50DA775CE5585E0EA6B8EA16B78F` |
| `tests/test_select.py` | `F2F0C77AB2461CB4343AC829F3555993CC51DB74F03DCDCC07CC609468BF0301` |
| `tests/test_generate.py` | `305CC67AB14791AD315880ABD15C404825CCE653FB311D707463CEFD49D07E0F` |
| `tests/test_assemble.py` | `E54B1605359F6F9521A4640F07553442AB6E54BC6D2020145CCC7ED9E65FA2A6` |
| `tests/test_ax.py` | `5B666AC35A2D5888B8BD9FAEFA01E6B2DC74B9911ABD6AF3340DA2CB7AA9943E` |
| `tests/test_publish.py` | `C7A53C119B6BC4A659F45589465B3913B80CD85AAE18797DF77F4300E56A04FA` |

The reviewer did not modify the tree. The scoped hashes were rechecked after the review and matched the request.

## Gate Result

- Critical: 0
- High: 0
- Gate: passed

The earlier 124-second and 360-second attempts returned no response or model metadata and remain invalid. The user then approved a 15-minute window; the valid review completed in about 8 minutes 21 seconds. `modelUsage` contained only `claude-opus-5`, so there was no fallback.

## Findings and Independent Disposition

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| M1 | Medium | The trusted output file is inside the model working directory and safety depends on Windows read-only sandbox enforcement. | Accepted into Task 8 hardening. Move the output sink outside `--cd` and run a Windows write-denial probe before real publishing. Not escalated: no bypass was reproduced and the current CLI is explicitly read-only. |
| M2 | Medium | The credential-sanitization test does not first set sentinel environment variables. | Accepted into Task 8 hardening. Add sentinels for `OPENAI_API_KEY` and another non-allowlisted variable, while asserting required auth/path variables survive. |
| M3 | Medium | Direct `select` and `stage` date arguments can reach filesystem creation without the validation used by publish/orchestrate. | Accepted into Task 7, where Windows entry points and date validation are centralized. Current orchestrated path already validates the date. |
| M4 | Medium | Blog/derived prompts do not yet document their JSON envelopes, `publish=false` semantics are undefined, and select still asks for a JSON fence. | Accepted into Task 3 for selection and Task 5 for article/derived prompt semantics and manifest recording. Structured schema failures are fail-closed today. |
| M5 | Medium | Windows path separators break publish path sets and can make rollback delete a just-restored worktree file. | Accepted into Task 6. Publishing on Windows remains explicitly unauthorized until Task 6 fixes and tests path normalization. |
| M6 | Medium | Reviewer reported an email residue-regex typo. | Rejected after direct verification: current `nbs/email.py:83` is `r"\{\{[<%]\s*/?\s*(?:rel)?ref\b"`, matching the correct assemble form. The reported `\?` and carriage-return message are not present. |
| M7 | Medium | A timed-out Windows `codex.cmd` grandchild may later write to the fixed retry output path. | Accepted into Task 8 hardening. Use a per-attempt output location or freshness token before shadow/real publication. Downstream URL/event-key and grounding gates bound current integrity impact. |
| M8 | Medium | `shutil.which` can prefer a repository-local `codex.cmd` on Windows. | Accepted into Task 7 installer hardening. Resolve and persist an absolute validated executable path. Repository takeover is outside the release threat model. |
| L1 | Low | Empty selection uses `generated_with=none(empty)`, outside the model schema enum. | Accepted into Task 3 while selection output is redesigned. |
| L2 | Low | The legacy fenced-output parser is no longer on the live path. | Rejected as deliberate compatibility for archived responses and fixtures; the function is documented as such. |
| L3 | Low | Model-provided candidate metadata is not yet joined back from local candidates. | Accepted into Task 3 as a required provenance rule. |
| L4 | Low | Some command details and the POSIX executable branch lack focused tests. | Accepted as non-Windows hardening backlog. |
| L5 | Low | Orchestration still invokes `python3`, which is unreliable on Windows. | Accepted into Task 7 Windows entry-point work. |

Medium and Low findings do not trigger an automatic correction or another review round under the project review policy.

## Verification

- `python -m pytest tests/test_codex_cli.py tests/test_select.py tests/test_generate.py tests/test_assemble.py tests/test_ax.py tests/test_publish.py::test_commit_message_does_not_attribute_codex_output_to_claude -q --deselect tests/test_ax.py::test_promote_copies_ax_optional` -> `60 passed, 1 deselected`
- `python -m nbs.codex_cli --self-test` -> `{"ok": true}` using saved ChatGPT authentication
- `python -m pytest -q` -> `262 passed, 11 failed`; the 11 failures remain the pre-existing Windows publish/email compatibility baseline
- `git diff --check` -> no errors
