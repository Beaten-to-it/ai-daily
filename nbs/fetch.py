import re

MIN_ARTICLE_CHARS = 1200   # tunable — below this an article body isn't "full text"
MIN_SHELL_CHARS = 200      # below this an HTML page is an empty JS shell / dead / stub
MIN_ABSTRACT_CHARS = 400   # arXiv abstract floor for confirmed
PAYWALL_MARKERS = (
    "subscribe to continue", "subscribe to read", "sign in to read",
    "for subscribers", "create a free account", "이 기사를 읽으려면",
    "구독자 전용", "회원 전용", "로그인이 필요",
)

def _visible_len(text: str) -> int:
    # strip tags + collapse whitespace so an HTML shell scores ~0
    t = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return len(re.sub(r"\s+", " ", t).strip())

def classify_evidence(source_type, text, *, paywall_marker=False, fetch_ok=True):
    if not fetch_ok or not text or not text.strip():
        return "exclude"
    n = _visible_len(text)
    if n == 0:
        return "exclude"
    low = text.lower()
    marker = paywall_marker or any(m in low for m in PAYWALL_MARKERS)
    if source_type == "paper":
        return "confirmed" if n >= MIN_ABSTRACT_CHARS else "short"
    if source_type in ("sns", "video"):
        return "confirmed" if n >= MIN_ARTICLE_CHARS else "short"
    # article / repo (web page): tiny page = JS shell / dead / stub → not obtained
    if n < MIN_SHELL_CHARS:
        return "exclude"
    if marker and n < MIN_ARTICLE_CHARS:      # paywall stub: short body + gate marker
        return "exclude"
    return "confirmed" if n >= MIN_ARTICLE_CHARS else "short"

import json, subprocess, tempfile, os, glob, urllib.request
from .models import FetchResult

_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 nbs-daily/0.1"

def _http_get(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace"), True
    except Exception:
        return "", False

def _jina(url, timeout=30):
    # Jina Reader renders JS + returns clean markdown; public content only (§11)
    text, ok = _http_get("https://r.jina.ai/" + url, timeout=timeout)
    return text if ok else ""

def _curl_impersonate(url, timeout=30):
    try:
        from curl_cffi import requests as creq
        r = creq.get(url, impersonate="chrome", timeout=timeout)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""

def _has_paywall(text):
    low = text.lower()
    return any(m in low for m in PAYWALL_MARKERS) and _visible_len(text) < MIN_ARTICLE_CHARS

def fetch_article(url):
    text, ok = _http_get(url)
    if ok and _visible_len(text) >= MIN_ARTICLE_CHARS and not _has_paywall(text):
        return text, "http", True
    j = _jina(url)
    if _visible_len(j) >= MIN_SHELL_CHARS:
        return j, "jina", True
    c = _curl_impersonate(url)
    if _visible_len(c) >= MIN_SHELL_CHARS:
        return c, "curl_cffi", True
    return (text or j or c), "http", ok

def fetch_paper(url):
    # arXiv abs page via Jina reader (abstract lives in the page)
    j = _jina(url)
    return (j, "arxiv", True) if _visible_len(j) >= MIN_SHELL_CHARS else ("", "arxiv", False)

def _extract_tweets(raw):
    try:
        env = json.loads(raw)
    except Exception:
        return ""
    data = env.get("data") if isinstance(env, dict) else env
    if isinstance(data, dict):
        data = [data]
    parts = []
    for t in (data or []):
        if isinstance(t, dict):
            parts.append(t.get("text") or t.get("full_text") or "")
        elif isinstance(t, str):
            parts.append(t)
    return "\n\n".join(p for p in parts if p).strip()

def fetch_sns(item):
    url = item.get("url", "")
    if "twitter.com" in url or "x.com" in url:
        try:
            # Step 0-verified: no `twitter thread` subcommand exists. `twitter tweet
            # <url> --json` returns the same {"ok":..,"data":[...]} envelope; --max 1
            # caps it to the target tweet only (default also pulls in public replies
            # from unrelated users, which would pollute the evidence text).
            r = subprocess.run(["twitter", "tweet", url, "--json", "--max", "1"],
                               capture_output=True, text=True, timeout=60)
            if r.returncode == 0 and r.stdout.strip():
                text = _extract_tweets(r.stdout)
                if text:
                    return text, "twitter", True
        except Exception:
            pass
        return "", "twitter", False
    # reddit via opencli needs Chrome; guard-skip if unavailable
    try:
        r = subprocess.run(["opencli", "reddit", "read", url],
                           capture_output=True, text=True, timeout=60)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout, "opencli", True
    except Exception:
        pass
    return "", "opencli", False

def _strip_srt(raw):
    # ponytail: no dedup of overlapping/rolling auto-caption lines (YouTube auto-vtt
    # repeats fragments across cues) -- ceiling is duplicated text in evidence, not
    # broken text. Upgrade if that shows up in generation quality: drop a cue line
    # that's a prefix/suffix of the previous kept line.
    out = []
    for line in raw.splitlines():
        s = re.sub(r"<[^>]+>", "", line).strip()  # drop <c> word-timing tags (auto-subs)
        if not s or s.isdigit() or "-->" in line:
            continue
        if s == "WEBVTT" or s.startswith(("Kind:", "Language:")):
            continue  # VTT header lines (Step 0: ffmpeg absent -> yt-dlp keeps .vtt, not .srt)
        out.append(s)
    return "\n".join(out)

def fetch_video(url):
    try:
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run(
                # Step 0-verified: flag is --sub-langs (plural); --sub-lang doesn't
                # exist. --convert-subs srt is a no-op without ffmpeg (not installed
                # here), so yt-dlp leaves .vtt files behind -> glob for both below.
                ["yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs",
                 "--sub-langs", "en,ko", "--convert-subs", "srt",
                 "-o", os.path.join(td, "%(id)s.%(ext)s"), url],
                capture_output=True, text=True, timeout=120)
            subs = sorted(glob.glob(os.path.join(td, "*.srt"))) or \
                   sorted(glob.glob(os.path.join(td, "*.vtt")))
            if not subs:
                return "", "yt-dlp", False
            raw = open(subs[0], encoding="utf-8", errors="replace").read()
            text = _strip_srt(raw)
            return (text, "yt-dlp", True) if text else ("", "yt-dlp", False)
    except Exception:
        return "", "yt-dlp", False

_FETCHERS = {"article": lambda it: fetch_article(it["url"]),
             "repo":    lambda it: fetch_article(it["url"]),
             "paper":   lambda it: fetch_paper(it["url"]),
             "sns":     lambda it: fetch_sns(it),
             "video":   lambda it: fetch_video(it["url"])}

def fetch_item(item):
    st = item.get("source_type", "article")
    text, via, ok = _FETCHERS.get(st, _FETCHERS["article"])(item)
    level = classify_evidence(st, text, paywall_marker=_has_paywall(text), fetch_ok=ok)
    return FetchResult(event_key=item.get("event_key",""), url=item.get("url",""),
                       source_type=st, text=text, evidence_level=level, via=via, fetch_ok=ok)
