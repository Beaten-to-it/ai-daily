from pathlib import Path
from nbs import collect
def test_parse_rss_canonical_dedup():
    xml = Path("tests/fixtures/sample_rss.xml").read_bytes()
    cands = collect.parse_rss(xml, {"name":"Ex","url":"u","source_type":"article"})
    assert len(cands) == 2 and cands[0].title == "New AI model"
    assert cands[0].published_at.endswith("+00:00")          # UTC aware
    # utm 제거 + 동일 기사 → canonical 1개
    assert len(collect.dedup_by_url(cands)) == 1
def test_within_window_utc():
    assert collect.within_window("2026-06-30T09:00:00+00:00","2026-07-01",hours=30)
    assert not collect.within_window("2026-06-01T00:00:00+00:00","2026-07-01",hours=30)
    assert collect.within_window("2026-06-30T09:00:00","2026-07-01",hours=30)  # naive→UTC, no crash
    assert collect.within_window(None,"2026-07-01")
    assert collect.within_window(1751270400,"2026-07-01")  # epoch int(reddit) → no TypeError, 통과

def test_parse_twitter_json_builds_url():
    raw='[{"id":"123","author":"@a","text":"Claude news here"}]'
    cands = collect.parse_twitter_json(raw, "q")
    assert len(cands)==1 and cands[0].url=="https://x.com/i/status/123"
    assert cands[0].source_type=="sns" and cands[0].title.startswith("Claude")
