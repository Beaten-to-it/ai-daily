from nbs import sources
def test_core_rss_present():
    names = {f["name"] for f in sources.RSS_FEEDS}
    assert {"GeekNews","HackerNews","arXiv cs.AI"} <= names
    for f in sources.RSS_FEEDS:
        assert f["url"].startswith("http") and f["source_type"] in {"article","paper"}
def test_sns_sources_active():
    assert len(sources.X_QUERIES) >= 3
    assert "LocalLLaMA" in sources.REDDIT_SUBS
