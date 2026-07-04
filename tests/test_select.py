from nbs import select

def test_run_claude_disables_tools_and_uses_stdin(monkeypatch):
    # §10: select processes untrusted RSS/X/Reddit candidate text via claude -p; it needs
    # text->JSON generation only, no tool access. --tools "" is the empirically-verified
    # no-tool flag (task-4-report.md Step 0; --allowedTools "" does NOT restrict).
    seen = {}
    class R: returncode = 0; stdout = "ok"; stderr = ""
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd; seen["input"] = kw.get("input"); seen["timeout"] = kw.get("timeout")
        return R()
    monkeypatch.setattr(select.subprocess, "run", fake_run)
    out = select.run_claude("hello", timeout=7)
    assert out == "ok" and "--tools" in seen["cmd"]
    # regression: the --tools VALUE must be a non-empty dummy (== select.NOTOOLS). An EMPTY
    # `--tools ""` deadlocks claude on a large stdin prompt (2026-07-04 P0). NOTOOLS still yields
    # tools: [] (zero tools, §10) — verified live — so security is unchanged.
    ti = seen["cmd"].index("--tools")
    assert seen["cmd"][ti + 1] == select.NOTOOLS and seen["cmd"][ti + 1] != ""
    assert seen["input"] == "hello" and seen["timeout"] == 7

def test_run_claude_default_timeout_is_300(monkeypatch):
    seen = {}
    class R: returncode = 0; stdout = "ok"; stderr = ""
    def fake_run(cmd, **kw):
        seen["timeout"] = kw.get("timeout"); return R()
    monkeypatch.setattr(select.subprocess, "run", fake_run)
    select.run_claude("hello")
    assert seen["timeout"] == 300

def test_parse_strips_fences():
    raw='설명\n```json\n{"date":"2026-07-01","items":[],"selected_count":0,"skipped_count":0,"generated_with":"claude-p"}\n```\n끝'
    assert select.parse_selection(raw)["date"]=="2026-07-01"
def test_recount_local():
    obj={"items":[{"dedup":"new"},{"dedup":"followup"},{"dedup":"skip"}],
         "selected_count":99,"skipped_count":99}
    select.recount(obj)
    assert obj["selected_count"]==2 and obj["skipped_count"]==1
def test_build_input_has_ledger_and_candidates():
    txt=select.build_prompt_input(
        [{"source":"OpenAI","title":"T","url":"u","canonical_url":"u","snippet":"s",
          "source_type":"article","published_at":None,"raw_id":"r"}],
        [{"event_key":"old","title":"O","summary":"s","date":"2026-06-30","post_path":"posts/old"}],
        "2026-07-01")
    assert "OpenAI" in txt and "old" in txt and "2026-07-01" in txt
