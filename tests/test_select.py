from nbs import select
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
