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

def test_parse_twitter_json_envelope_and_url():
    raw='{"ok":true,"data":[{"id":"123","text":"Claude news here"}]}'  # twitter --json 봉투(실제 포맷)
    cands = collect.parse_twitter_json(raw, "q")
    assert len(cands)==1 and cands[0].url=="https://x.com/i/status/123"
    assert cands[0].source_type=="sns" and cands[0].title.startswith("Claude")
    assert len(collect.parse_twitter_json('[{"id":"9","text":"x"}]',"q"))==1  # bare array도 허용

def test_cap_per_source():
    from nbs.models import Candidate
    mk=lambda src,i: Candidate(src,"paper",f"t{i}",f"http://x/{src}/{i}",f"http://x/{src}/{i}",
                               f"2026-06-{10+i:02d}T00:00:00","s",str(i))
    cands=[mk("arXiv",i) for i in range(30)]+[mk("GeekNews",i) for i in range(5)]
    from collections import Counter
    c=Counter(x.source for x in collect.cap_per_source(cands, n=25))
    assert c["arXiv"]==25 and c["GeekNews"]==5

def test_cap_per_source_mixed_published_at():
    # Fix 1: epoch int / None / ISO str mixed → must not raise TypeError
    from nbs.models import Candidate
    mk=lambda pub: Candidate("src","article","t","http://x/1","http://x/1",pub,"s","1")
    mixed=[mk(1751270400), mk(None), mk("2026-06-30T12:00:00+00:00")]
    result=collect.cap_per_source(mixed, n=25)
    assert len(result)==3  # all returned (well under cap)

def test_within_window_same_day_afternoon():
    # Fix 4: same-day afternoon (KST 15:00 = UTC 06:00) must pass on that run date
    assert collect.within_window("2026-07-01T15:00:00+09:00","2026-07-01")
