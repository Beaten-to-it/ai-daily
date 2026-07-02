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

from nbs.ledger import rewrite_date, append_rows
import csv as _csv
def _read(p):
    with open(p, newline="", encoding="utf-8") as f: return list(_csv.DictReader(f))

def test_rewrite_date_replaces_only_that_date(tmp_path):
    p = tmp_path / "led.csv"
    append_rows([{"event_key":"old","date":"2026-06-30","title":"O"}], path=p)
    append_rows([{"event_key":"stale","date":"2026-07-01","title":"S"}], path=p)
    rewrite_date("2026-07-01", [{"event_key":"fresh","date":"2026-07-01","title":"F"}], path=p)
    keys = {r["event_key"] for r in _read(p)}
    assert keys == {"old", "fresh"}

def test_rewrite_date_is_idempotent(tmp_path):
    p = tmp_path / "led.csv"; row = [{"event_key":"a","date":"2026-07-01","title":"A"}]
    rewrite_date("2026-07-01", row, path=p); rewrite_date("2026-07-01", row, path=p)
    assert len(_read(p)) == 1
