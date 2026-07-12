import re

MIN_ARTICLE_CHARS = 1200   # tunable — below this an article body isn't "full text"
MIN_SHELL_CHARS = 200      # below this an HTML page is an empty JS shell / dead / stub
MIN_ABSTRACT_CHARS = 400   # arXiv abstract floor for confirmed
MAX_EVIDENCE_CHARS = 40000 # cap fed to claude -p (~10K tokens); long tail dropped
                           # ponytail: raise if detailed rewrites lose the article's end
PAYWALL_MARKERS = (
    "subscribe to continue", "subscribe to read", "sign in to read",
    "for subscribers", "create a free account", "이 기사를 읽으려면",
    "구독자 전용", "회원 전용", "로그인이 필요",
)

def _visible_text(html: str) -> str:
    # drop script+style BODIES + all tags so what we keep is readable text, not raw
    # HTML/JSON/CSS. The gate (_visible_len) and the return path share this so a
    # style-heavy JS shell can't pass the length gate on CSS then return thin text.
    t = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def _visible_len(text: str) -> int:
    return len(_visible_text(text))

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

import json, subprocess, tempfile, os, glob, urllib.request, time, socket, ipaddress
from urllib.parse import urlsplit
from .models import FetchResult

_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 nbs-daily/0.1"
MAX_FETCH_BYTES = 8_000_000   # raw-response memory cap (evidence is later capped to 40K chars);
                              # bounds OOM from a hostile/huge body BEFORE it is fully resident.
FETCH_DEADLINE = 45.0         # per-fetch TOTAL wall-clock ceiling. urllib/requests timeouts are
                              # per-read (reset on every byte) — a slow-drip server never trips them
                              # and would hang forever holding both run locks. This bounds total time.

def _host_is_public(url):
    # §10 SSRF guard: a candidate URL is untrusted (LLM/RSS/HN-derived). Block any host that
    # resolves to a non-global address (loopback/private/link-local/CGNAT/multicast/unspecified)
    # so an internal service cannot become published evidence. is_global covers 100.64/10 (CGNAT).
    # ponytail: resolve-then-check on the request URL + the final redirect URL; NOT rebinding-proof
    # (urllib re-resolves at connect). Full protection = pinning the resolved IP through the socket;
    # deferred (personal host, no state-changing internal GET endpoints) — upgrade if that changes.
    host = urlsplit(url).hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError, OSError, ValueError):
        return False
    if not infos:
        return False
    for info in infos:
        try:
            if not ipaddress.ip_address(info[4][0]).is_global:
                return False
        except ValueError:
            return False
    return True

def _read_capped(reader):
    # Read a file-like (urllib response) in chunks under a TOTAL deadline + byte cap. Each read()
    # is still socket-timeout-bounded; the deadline bounds a steady drip that never times out.
    deadline = time.monotonic() + FETCH_DEADLINE
    buf = bytearray()
    while len(buf) <= MAX_FETCH_BYTES and time.monotonic() < deadline:
        chunk = reader.read(65536)
        if not chunk:
            break
        buf += chunk
    return bytes(buf[:MAX_FETCH_BYTES])

def _http_get(url, timeout=20):
    if not _host_is_public(url):          # §10: block internal/non-global destinations (SSRF)
        return "", False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            # §10: a redirect can land off-web (urllib allows ftp:// redirect targets) or on an
            # internal host; re-check the FINAL url's scheme AND that it resolves to a public IP.
            if urlsplit(r.geturl()).scheme not in ("http", "https") or not _host_is_public(r.geturl()):
                return "", False
            return _read_capped(r).decode("utf-8", "replace"), True
    except Exception:
        return "", False

def _jina(url, timeout=30):
    # Jina Reader renders JS + returns clean markdown; public content only (§11). The target url
    # is embedded in jina's PATH (server-side fetch by jina), so the SSRF guard here is jina's
    # own public host — the inner url can't reach OUR internal network via this path.
    text, ok = _http_get("https://r.jina.ai/" + url, timeout=timeout)
    return text if ok else ""

def _curl_impersonate(url, timeout=30):
    if not _host_is_public(url):          # §10: SSRF guard (same as _http_get)
        return ""
    try:
        from curl_cffi import requests as creq
        # stream=True + capped read so a hostile body can't OOM us (curl_cffi's timeout is total,
        # so time is already bounded; this bounds memory).
        with creq.get(url, impersonate="chrome", timeout=timeout, stream=True) as r:
            # §10: libcurl follows redirects and supports file://; enforce the FINAL url is a public web host.
            if r.status_code != 200 or urlsplit(str(r.url)).scheme not in ("http", "https") \
               or not _host_is_public(str(r.url)):
                return ""
            deadline = time.monotonic() + FETCH_DEADLINE
            buf = bytearray()
            for chunk in r.iter_content(65536):
                if len(buf) > MAX_FETCH_BYTES or time.monotonic() > deadline:
                    break
                buf += chunk or b""
            return bytes(buf[:MAX_FETCH_BYTES]).decode("utf-8", "replace")
    except Exception:
        return ""

def _has_paywall(text):
    low = text.lower()
    return any(m in low for m in PAYWALL_MARKERS) and _visible_len(text) < MIN_ARTICLE_CHARS

def fetch_article(url):
    text, ok = _http_get(url)
    if ok and _visible_len(text) >= MIN_ARTICLE_CHARS and not _has_paywall(text):
        return _visible_text(text)[:MAX_EVIDENCE_CHARS], "http", True
    j = _jina(url)                                   # jina returns clean markdown, keep as-is
    if _visible_len(j) >= MIN_SHELL_CHARS:
        return j[:MAX_EVIDENCE_CHARS], "jina", True
    c = _curl_impersonate(url)
    if _visible_len(c) >= MIN_SHELL_CHARS:
        return _visible_text(c)[:MAX_EVIDENCE_CHARS], "curl_cffi", True
    return (_visible_text(text) or j or _visible_text(c))[:MAX_EVIDENCE_CHARS], "http", ok

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
    # ponytail: containment-based dedup collapses rolling auto-caption overlap
    # (each new cue is a superset/subset of the previous kept line, the common
    # case for YouTube auto-vtt). Ceiling: partial word-boundary overlap that
    # isn't a full substring won't collapse -- upgrade to a suffix/prefix
    # longest-common-overlap merge if that shows up in evidence text.
    out = []
    for line in raw.splitlines():
        s = re.sub(r"<[^>]+>", "", line).strip()  # drop <c> word-timing tags (auto-subs)
        if not s or s.isdigit() or "-->" in line:
            continue
        if s == "WEBVTT" or s.startswith(("Kind:", "Language:")):
            continue  # VTT header lines (Step 0: ffmpeg absent -> yt-dlp keeps .vtt, not .srt)
        if out:
            prev = out[-1]
            if prev in s:
                out[-1] = s   # rolling cue grew -> supersedes previous
                continue
            if s in prev:
                continue      # rolling fragment already covered by previous
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
    url = item.get("url", "")
    # §10 trust boundary: only http(s). file://, ftp:// etc. would let a hostile feed
    # URL read the local FS (urllib/libcurl/yt-dlp all honor them) into published
    # evidence. Guard once at dispatch — covers every backend. (_jina fetches server-side.)
    if urlsplit(url).scheme not in ("http", "https"):
        return FetchResult(event_key=item.get("event_key",""), url=url, source_type=st,
                           text="", evidence_level="exclude", via="bad-scheme", fetch_ok=False)
    text, via, ok = _FETCHERS.get(st, _FETCHERS["article"])(item)
    level = classify_evidence(st, text, paywall_marker=_has_paywall(text), fetch_ok=ok)
    return FetchResult(event_key=item.get("event_key",""), url=url,
                       source_type=st, text=text, evidence_level=level, via=via, fetch_ok=ok)
