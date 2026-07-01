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
