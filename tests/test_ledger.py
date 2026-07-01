from nbs import ledger
def test_roundtrip_and_recent(tmp_path):
    p = tmp_path/"led.csv"
    rows = [
      {"canonical_key":"a","event_key":"a","date":"2026-06-20","title":"A","url":"u1","source":"s",
       "post_path":"posts/a","summary":"sa","entities":"x","tags":"t","confidence":"high"},
      {"canonical_key":"b","event_key":"b","date":"2026-06-30","title":"B","url":"u2","source":"s",
       "post_path":"posts/b","summary":"sb","entities":"y","tags":"t","confidence":"high"}]
    ledger.append_rows(rows, path=p)
    recent = ledger.read_recent(days=7, today="2026-07-01", path=p)
    assert {r["event_key"] for r in recent} == {"b"}
    assert ledger.ledger_digest(recent)[0].keys() >= {"event_key","title","summary","date","post_path"}
def test_append_creates_header(tmp_path):
    p = tmp_path/"led.csv"; ledger.append_rows([], path=p)
    assert p.read_text().strip().split("\n")[0] == ",".join(ledger.LEDGER_HEADER)
