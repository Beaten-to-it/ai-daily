from collections import Counter
from pathlib import Path

import pytest

from nbs import collect
from nbs.models import Candidate


def test_main_rejects_invalid_date_before_creating_run_path(tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "run_dir", lambda date: tmp_path / date)
    with pytest.raises(SystemExit):
        collect.main(["--date", "../evil"])
    assert not (tmp_path.parent / "evil").exists()


def test_parse_rss_canonical_dedup():
    xml = Path("tests/fixtures/sample_rss.xml").read_bytes()
    candidates = collect.parse_rss(xml, {"name": "Ex", "url": "u",
                                         "source_type": "article", "lane": "official"})
    assert len(candidates) == 2 and candidates[0].title == "New AI model"
    assert candidates[0].published_at.endswith("+00:00")
    assert candidates[0].lane == "official" and candidates[0].discovered_via == "u"
    assert candidates[0].to_dict()["candidate_id"]
    assert len(collect.dedup_by_url(candidates)) == 1


def test_within_window_utc():
    assert collect.within_window("2026-06-30T09:00:00+00:00", "2026-07-01", hours=30)
    assert not collect.within_window("2026-06-01T00:00:00+00:00", "2026-07-01", hours=30)
    assert collect.within_window("2026-06-30T09:00:00", "2026-07-01", hours=30)
    assert collect.within_window(None, "2026-07-01")
    assert collect.within_window(1751270400, "2026-07-01")


def test_bluesky_external_link_promotes_original_source():
    item = {"post": {
        "uri": "at://did:plc:abc/app.bsky.feed.post/r1",
        "author": {"handle": "writer.bsky.social"},
        "record": {"text": "New AI release", "createdAt": "2026-08-01T00:00:00Z"},
        "embed": {"external": {"uri": "https://example.com/releases/ai", "title": "AI release"}},
    }}
    candidate = collect.candidate_from_bluesky(item)
    assert candidate.url == "https://example.com/releases/ai"
    assert candidate.source == "example.com" and candidate.source_type == "article"
    assert candidate.lane == "social"
    assert candidate.discovered_via == "https://bsky.app/profile/writer.bsky.social/post/r1"


def test_x_external_link_promotes_original_source():
    tweet = {"id": "123", "text": "Claude news", "created_at": "2026-08-01T00:00:00Z",
             "entities": {"urls": [{"expanded_url": "https://openai.com/index/update"}]}}
    candidate = collect.candidate_from_x(tweet, "AI query")
    assert candidate.url == "https://openai.com/index/update"
    assert candidate.source == "openai.com" and candidate.source_type == "article"
    assert candidate.discovered_via == "https://x.com/i/status/123"


def test_hn_promoted_platform_links_keep_their_evidence_type():
    tweet = collect.candidate_from_hn({"id": 1, "title": "AI thread",
                                      "url": "https://twitter.com/user/status/1"})
    video = collect.candidate_from_hn({"id": 2, "title": "AI talk",
                                      "url": "https://www.youtube.com/watch?v=abc"})
    assert tweet.source_type == "sns"
    assert video.source_type == "video"


def test_authenticated_api_redirect_is_not_followed(monkeypatch):
    class Response:
        status_code = 302
        headers = {"Location": "https://redirected.example/data"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Session:
        def __init__(self):
            self.calls = 0

        def request(self, *args, **kwargs):
            self.calls += 1
            return Response()

    session = Session()
    monkeypatch.setattr(collect, "_host_is_public", lambda url: True)
    with pytest.raises(RuntimeError, match="authenticated API redirect"):
        collect._request_bytes(session, "GET", "https://api.example/data",
                               headers={"Authorization": "Bearer secret"})
    assert session.calls == 1


def _candidate(source, index, url=None, published_at=None):
    url = url or f"https://example.com/{source}/{index}"
    return Candidate(source, "article", f"t{index}", url, collect.canonicalize_url(url),
                     published_at or f"2026-08-01T{index % 10:02d}:00:00+00:00",
                     "s", str(index))


def test_cap_per_source():
    candidates = ([_candidate("arXiv", index) for index in range(30)] +
                  [_candidate("GeekNews", index) for index in range(5)])
    counts = Counter(candidate.source for candidate in collect.cap_per_source(candidates, n=25))
    assert counts["arXiv"] == 25 and counts["GeekNews"] == 5


def test_cap_per_source_mixed_published_at():
    mixed = [_candidate("src", 1, published_at=1751270400),
             _candidate("src", 2, published_at=None),
             _candidate("src", 3, published_at="2026-06-30T12:00:00+00:00")]
    assert len(collect.cap_per_source(mixed, n=25)) == 3


def test_finalize_deduplicates_before_per_source_cap():
    candidates = [
        _candidate("same", 3, "https://example.com/dup?utm_source=a"),
        _candidate("same", 2, "https://example.com/dup"),
        _candidate("same", 1, "https://example.com/unique"),
    ]
    result = collect.finalize_candidates(candidates, cap=2)
    assert {candidate.canonical_url for candidate in result} == {
        "https://example.com/dup", "https://example.com/unique"
    }


def test_within_window_same_day_afternoon():
    assert collect.within_window("2026-07-01T15:00:00+09:00", "2026-07-01")
