from nbs import sources


def test_core_rss_present():
    names = {feed["name"] for feed in sources.RSS_FEEDS}
    assert {"OpenAI", "GeekNews", "arXiv cs.AI", "AWS ML", "NVIDIA Developer",
            "Google DeepMind", "GitHub Changelog", "AI타임스"} <= names
    for feed in sources.RSS_FEEDS:
        assert feed["url"].startswith("http")
        assert feed["source_type"] in {"article", "paper"}
        assert feed["lane"] in {"official", "media", "research", "developer"}


def test_public_and_optional_sources_are_configured():
    assert len(sources.X_QUERIES) >= 3
    assert "LocalLLaMA" in sources.REDDIT_SUBS
    assert "simonwillison.net" in sources.BLUESKY_ACCOUNTS
    assert "openai/openai-python" in sources.GITHUB_REPOS
    assert sources.GDELT_QUERIES


def test_dead_guessed_feeds_are_not_configured():
    urls = "\n".join(feed["url"] for feed in sources.RSS_FEEDS).lower()
    assert "anthropic.com/rss" not in urls
    assert "microsoft.com/en-us/ai/rss" not in urls
    assert "ai.meta.com/blog/rss" not in urls
