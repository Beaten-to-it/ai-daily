from pathlib import Path
from nbs import fetch
FX = Path(__file__).parent / "fixtures"
def _rd(n): return (FX / n).read_text(encoding="utf-8")

def test_full_article_confirmed():
    assert fetch.classify_evidence("article", _rd("article_full.txt")) == "confirmed"
def test_paywall_stub_excluded():
    assert fetch.classify_evidence("article", _rd("paywall_stub.html"), paywall_marker=True) == "exclude"
def test_js_empty_shell_excluded():
    assert fetch.classify_evidence("article", _rd("js_empty_shell.html")) == "exclude"
def test_dead_link_excluded():
    assert fetch.classify_evidence("article", "", fetch_ok=False) == "exclude"
def test_short_tweet_is_short():                       # regression for the guard-order bug
    assert fetch.classify_evidence("sns", _rd("short_tweet.txt")) == "short"
def test_sns_below_shell_threshold_still_short():
    assert fetch.classify_evidence("sns", "tiny") == "short"
def test_arxiv_abstract_confirmed():
    assert fetch.classify_evidence("paper", _rd("arxiv_abstract.txt")) == "confirmed"
def test_short_but_real_article_is_short():
    assert fetch.classify_evidence("article", "A real 300-char note. " * 12) == "short"
def test_video_long_captions_confirmed():
    assert fetch.classify_evidence("video", "auto captions text " * 100) == "confirmed"
def test_video_short_caption_is_short():
    assert fetch.classify_evidence("video", "short caption") == "short"
def test_empty_excluded_any_type():
    assert fetch.classify_evidence("video", "") == "exclude"
    assert fetch.classify_evidence("sns", "   ") == "exclude"

def test_article_returns_visible_text_not_raw_html(monkeypatch):
    html = ("<html><head><style>.x{color:red}</style>"
            "<script>var junk={a:1,b:2}</script></head>"
            "<body><h1>Title</h1><p>" + "real body text " * 120 + "</p></body></html>")
    monkeypatch.setattr(fetch, "_http_get", lambda u, timeout=20: (html, True))
    text, via, ok = fetch.fetch_article("https://x.test/a")
    assert via == "http" and ok
    assert "<" not in text and "var junk" not in text and "color:red" not in text
    assert "real body text" in text

def test_article_caps_evidence_size(monkeypatch):
    big = "<p>" + ("word " * fetch.MAX_EVIDENCE_CHARS) + "</p>"   # visible >> cap
    monkeypatch.setattr(fetch, "_http_get", lambda u, timeout=20: (big, True))
    text, via, ok = fetch.fetch_article("https://x.test/a")
    assert len(text) == fetch.MAX_EVIDENCE_CHARS

def test_http_get_rejects_redirect_off_web(monkeypatch):
    # §10: an http URL that redirects to file:// (final scheme off-web) must not be read
    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def geturl(self): return "file:///etc/passwd"
        def read(self): return b"root:x:0:0"
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    text, ok = fetch._http_get("http://evil.test/redir")
    assert text == "" and ok is False

def test_fetch_item_rejects_non_http_scheme():
    # §10: file:// / ftp:// would read the local FS into evidence — reject at dispatch
    r = fetch.fetch_item({"event_key":"k","url":"file:///etc/passwd","source_type":"article"})
    assert r.evidence_level=="exclude" and r.fetch_ok is False and r.via=="bad-scheme" and r.text==""

def test_article_style_heavy_shell_falls_to_jina(monkeypatch):
    # gate must strip <style> (not count CSS as content): a CSS-heavy shell whose real
    # visible text is tiny should fall through to jina, not be accepted via http.
    shell = "<html><head><style>" + ".c{color:red;padding:1px} "*300 + "</style></head><body><nav>Home About</nav></body></html>"
    monkeypatch.setattr(fetch, "_http_get", lambda u, timeout=20: (shell, True))
    monkeypatch.setattr(fetch, "_jina", lambda u, timeout=30: "실제 기사 본문 "*200)
    text, via, ok = fetch.fetch_article("https://x.test/a")
    assert via=="jina" and ok and "실제 기사" in text

def test_article_falls_back_to_jina_when_http_thin(monkeypatch):
    monkeypatch.setattr(fetch, "_http_get", lambda u, timeout=20: ("<div id=root></div>", True))
    monkeypatch.setattr(fetch, "_jina", lambda u, timeout=30: "F"*1500)
    text, via, ok = fetch.fetch_article("https://x.test/a")
    assert ok and via == "jina" and len(text) >= 1500

def test_fetch_item_routes_by_source_type(monkeypatch):
    monkeypatch.setattr(fetch, "fetch_paper", lambda u: ("abstract "*80, "arxiv", True))
    r = fetch.fetch_item({"event_key":"k","url":"https://arxiv.org/abs/1","source_type":"paper"})
    assert r.evidence_level == "confirmed" and r.source_type == "paper" and r.via == "arxiv"

def test_fetch_item_excludes_on_total_failure(monkeypatch):
    monkeypatch.setattr(fetch, "fetch_article", lambda u: ("", "none", False))
    r = fetch.fetch_item({"event_key":"k","url":"https://x.test","source_type":"article"})
    assert r.evidence_level == "exclude" and r.fetch_ok is False

def test_fetch_sns_uses_collected_snippet_without_cli(monkeypatch):
    monkeypatch.setattr(fetch, "fetch_article", lambda url: (_ for _ in ()).throw(
        AssertionError("collected social text should not need a second fetch")))
    item = {"event_key": "k", "url": "https://x.com/a/status/1",
            "source_type": "sns", "snippet": "tiny tweet"}
    text, via, ok = fetch.fetch_sns(item)
    result = fetch.fetch_item(item)
    assert text == "tiny tweet" and via == "collected-snippet" and ok
    assert result.evidence_level == "short"


def test_fetch_sns_falls_back_to_public_page(monkeypatch):
    monkeypatch.setattr(fetch, "fetch_article", lambda url: ("public post", "jina", True))
    assert fetch.fetch_sns({"url": "https://www.reddit.com/r/test/comments/1"}) == (
        "public post", "jina", True
    )

def test_strip_srt_removes_timestamps_and_indices():
    srt = "1\n00:00:01,000 --> 00:00:03,000\nHello world\n\n2\n00:00:03,000 --> 00:00:05,000\nSecond line\n"
    out = fetch._strip_srt(srt)
    assert out == "Hello world\nSecond line"

def test_strip_srt_dedupes_rolling_captions():
    vtt = (
        "WEBVTT\nKind: captions\nLanguage: en\n\n"
        "00:00:00.000 --> 00:00:02.000\nhello world this\n\n"
        "00:00:01.000 --> 00:00:03.000\nhello world this is a test\n\n"
        "00:00:02.000 --> 00:00:04.000\nthis is a test\n"
    )
    out = fetch._strip_srt(vtt)
    assert out == "hello world this is a test"
