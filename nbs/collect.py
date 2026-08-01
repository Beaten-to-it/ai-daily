import argparse
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlsplit

import feedparser
import requests

from . import sources
from .config import KST, run_dir
from .fetch import _host_is_public, _read_capped
from .models import Candidate, SourceHealth, canonicalize_url


_AI_TERMS = re.compile(
    r"\b(ai|llm|gpt|claude|gemini|openai|anthropic|agentic|agents?|rag|codex|"
    r"copilot|cursor|qwen|deepseek|mistral|transformers?|inference|neural)\b|"
    r"machine learning|deep learning|language model",
    re.I,
)
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_SECRET_ENV = (
    "AI_DAILY_X_BEARER",
    "AI_DAILY_REDDIT_CLIENT_ID",
    "AI_DAILY_REDDIT_CLIENT_SECRET",
    "AI_DAILY_GITHUB_TOKEN",
)


class Unconfigured(RuntimeError):
    pass


class Degraded(RuntimeError):
    def __init__(self, candidates, message):
        super().__init__(message)
        self.candidates = candidates


def parse_rss(xml_bytes, feed):
    parsed = feedparser.parse(xml_bytes)
    output = []
    for entry in parsed.entries:
        published = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        published_at = datetime(*published[:6], tzinfo=timezone.utc).isoformat() if published else None
        url = (entry.get("link") or "").strip()
        if not url:
            continue
        output.append(Candidate(
            source=feed["name"],
            source_type=feed["source_type"],
            title=(entry.get("title") or "").strip(),
            url=url,
            canonical_url=canonicalize_url(url),
            published_at=published_at,
            snippet=(entry.get("summary", "") or "")[:500],
            raw_id=entry.get("id") or url,
            lane=feed["lane"],
            discovered_via=feed["url"],
        ))
    return output


def within_window(published_at, today, hours=30):
    if not published_at or not isinstance(published_at, str):
        return True
    try:
        published = datetime.fromisoformat(published_at)
    except ValueError:
        return True
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    day_start = datetime.fromisoformat(today + "T00:00:00").replace(tzinfo=KST).astimezone(timezone.utc)
    return day_start - published <= timedelta(hours=hours) and published <= day_start + timedelta(hours=24)


def dedup_by_url(candidates):
    seen = set()
    output = []
    for candidate in candidates:
        key = candidate.canonical_url or candidate.url
        if key and key not in seen:
            seen.add(key)
            output.append(candidate)
    return output


def cap_per_source(candidates, n=25):
    from collections import defaultdict
    buckets = defaultdict(list)
    for candidate in candidates:
        buckets[candidate.source].append(candidate)
    output = []
    for items in buckets.values():
        items.sort(key=lambda candidate: candidate.published_at
                   if isinstance(candidate.published_at, str) else "", reverse=True)
        output.extend(items[:n])
    return output


def finalize_candidates(candidates, cap=25):
    return cap_per_source(dedup_by_url(candidates), cap)


def _request_bytes(session, method, url, *, params=None, headers=None, data=None, auth=None,
                   timeout=(10, 20)):
    current = url
    headers = headers or {}
    for _ in range(4):
        if urlsplit(current).scheme not in {"http", "https"} or not _host_is_public(current):
            raise RuntimeError("non-public source URL")
        with session.request(method, current, params=params, headers=headers, data=data, auth=auth,
                             timeout=timeout, stream=True, allow_redirects=False) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                if auth or any(name.lower() == "authorization" for name in headers):
                    raise RuntimeError("authenticated API redirect refused")
                if method.upper() != "GET" or not response.headers.get("Location"):
                    raise RuntimeError("unexpected API redirect")
                current = urljoin(current, response.headers["Location"])
                continue
            response.raise_for_status()
            if hasattr(response.raw, "decode_content"):
                response.raw.decode_content = True
            return _read_capped(response.raw)
    raise RuntimeError("too many source redirects")


def _request_json(session, method, url, **kwargs):
    raw = _request_bytes(session, method, url, **kwargs)
    return json.loads(raw.decode("utf-8", "replace"))


def fetch_rss(feed, session=None):
    session = session or requests.Session()
    raw = _request_bytes(session, "GET", feed["url"],
                         headers={"User-Agent": "nbs-collector/0.2"})
    return parse_rss(raw, feed)


def _host(url):
    hostname = (urlsplit(url).hostname or "").lower()
    return hostname[4:] if hostname.startswith("www.") else hostname


def _source_name(url, fallback):
    return _host(url) or fallback


def _target_type(url, default="article"):
    if _is_platform_url(url, {"x.com", "twitter.com", "reddit.com", "bsky.app",
                              "news.ycombinator.com"}):
        return "sns"
    if _is_platform_url(url, {"youtube.com", "youtu.be", "vimeo.com"}):
        return "video"
    return default


def _is_platform_url(url, hosts):
    hostname = _host(url)
    return any(hostname == host or hostname.endswith("." + host) for host in hosts)


def _external_url(urls, blocked_hosts):
    for url in urls:
        if (isinstance(url, str) and urlsplit(url).scheme in {"http", "https"}
                and _host(url) and not _is_platform_url(url, blocked_hosts)):
            return url
    return ""


def _iso(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if not isinstance(value, str):
        return None
    if re.fullmatch(r"\d{8}T\d{6}Z", value):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
    return value


def candidate_from_bluesky(item):
    post = item.get("post", {})
    record = post.get("record", {})
    handle = post.get("author", {}).get("handle", "unknown")
    record_key = (post.get("uri", "").rsplit("/", 1)[-1] or "unknown")
    post_url = f"https://bsky.app/profile/{handle}/post/{record_key}"
    external = (post.get("embed", {}).get("external", {}) or
                record.get("embed", {}).get("external", {}))
    original_url = _external_url([external.get("uri", "")], {"bsky.app"})
    url = original_url or post_url
    text = record.get("text", "") or ""
    return Candidate(
        source=_source_name(original_url, f"Bluesky @{handle}"),
        source_type=_target_type(url, "article" if original_url else "sns"),
        title=(external.get("title") or text or "Bluesky post")[:200],
        url=url,
        canonical_url=canonicalize_url(url),
        published_at=_iso(record.get("createdAt")),
        snippet=(text + " " + (external.get("description") or "")).strip()[:500],
        raw_id=post.get("uri") or record_key,
        lane="social",
        discovered_via=post_url,
    )


def candidate_from_x(tweet, query=""):
    tweet_id = str(tweet.get("id", ""))
    post_url = f"https://x.com/i/status/{tweet_id}"
    expanded = [row.get("expanded_url", "") for row in tweet.get("entities", {}).get("urls", [])]
    original_url = _external_url(expanded, {"x.com", "twitter.com", "t.co"})
    url = original_url or post_url
    text = tweet.get("text", "") or ""
    return Candidate(
        source=_source_name(original_url, "X"),
        source_type=_target_type(url, "article" if original_url else "sns"),
        title=text[:200] or query[:200],
        url=url,
        canonical_url=canonicalize_url(url),
        published_at=_iso(tweet.get("created_at")),
        snippet=text[:500],
        raw_id=tweet_id,
        lane="social",
        discovered_via=post_url,
    )


def candidate_from_reddit(post, subreddit):
    permalink = post.get("permalink", "") or ""
    post_url = urljoin("https://www.reddit.com", permalink)
    submitted = post.get("url_overridden_by_dest") or post.get("url") or ""
    original_url = _external_url([submitted], {"reddit.com", "redd.it"})
    url = original_url or post_url
    return Candidate(
        source=_source_name(original_url, f"Reddit r/{subreddit}"),
        source_type=_target_type(url, "article" if original_url else "sns"),
        title=(post.get("title") or "Reddit post")[:200],
        url=url,
        canonical_url=canonicalize_url(url),
        published_at=_iso(post.get("created_utc")),
        snippet=(post.get("selftext") or post.get("title") or "")[:500],
        raw_id=str(post.get("id", "")),
        lane="social",
        discovered_via=post_url,
    )


def candidate_from_hn(item):
    item_id = str(item.get("id", ""))
    discussion_url = f"https://news.ycombinator.com/item?id={item_id}"
    original_url = _external_url([item.get("url", "")], {"ycombinator.com"})
    url = original_url or discussion_url
    return Candidate(
        source=_source_name(original_url, "Hacker News"),
        source_type=_target_type(url, "article" if original_url else "sns"),
        title=(item.get("title") or "Hacker News item")[:200],
        url=url,
        canonical_url=canonicalize_url(url),
        published_at=_iso(item.get("time")),
        snippet=(item.get("text") or item.get("title") or "")[:500],
        raw_id=item_id,
        lane="developer",
        discovered_via=discussion_url,
    )


def fetch_hn(session, limit=40):
    ids = _request_json(session, "GET", "https://hacker-news.firebaseio.com/v0/newstories.json")
    output = []
    failures = 0
    for item_id in (ids if isinstance(ids, list) else [])[:limit]:
        try:
            item = _request_json(session, "GET",
                                 f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
            if isinstance(item, dict) and _AI_TERMS.search(item.get("title", "") or ""):
                output.append(candidate_from_hn(item))
        except Exception:
            failures += 1
    if failures:
        raise Degraded(output, f"{failures} Hacker News item requests failed")
    return output


def fetch_bluesky(session, handle, limit=20):
    payload = _request_json(
        session,
        "GET",
        "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed",
        params={"actor": handle, "limit": limit, "filter": "posts_no_replies"},
    )
    return [candidate_from_bluesky(item) for item in payload.get("feed", [])
            if isinstance(item, dict) and item.get("post")]


def fetch_gdelt(session, query, limit=75):
    payload = _request_json(
        session,
        "GET",
        "https://api.gdeltproject.org/api/v2/doc/doc",
        params={"query": query, "mode": "artlist", "format": "json", "timespan": "1day",
                "maxrecords": limit, "sort": "DateDesc"},
    )
    output = []
    for article in payload.get("articles", []):
        url = article.get("url", "")
        if not url:
            continue
        output.append(Candidate(
            source=article.get("domain") or _source_name(url, "GDELT"),
            source_type=_target_type(url),
            title=(article.get("title") or "GDELT article")[:200],
            url=url,
            canonical_url=canonicalize_url(url),
            published_at=_iso(article.get("seendate")),
            snippet="",
            raw_id=url,
            lane="web",
            discovered_via="https://api.gdeltproject.org/api/v2/doc/doc",
        ))
    return output


def fetch_github(session, repo, limit=10):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "nbs-collector/0.2"}
    token = os.environ.get("AI_DAILY_GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    releases = _request_json(session, "GET", f"https://api.github.com/repos/{repo}/releases",
                             params={"per_page": limit}, headers=headers)
    output = []
    for release in releases if isinstance(releases, list) else []:
        url = release.get("html_url", "")
        if not url:
            continue
        output.append(Candidate(
            source=f"GitHub {repo}",
            source_type="repo",
            title=(release.get("name") or release.get("tag_name") or "New release")[:200],
            url=url,
            canonical_url=canonicalize_url(url),
            published_at=_iso(release.get("published_at") or release.get("created_at")),
            snippet=(release.get("body") or "")[:500],
            raw_id=str(release.get("id", "")),
            lane="developer",
            discovered_via=f"https://api.github.com/repos/{repo}/releases",
        ))
    return output


def fetch_x(session, query, limit=20):
    token = os.environ.get("AI_DAILY_X_BEARER")
    if not token:
        raise Unconfigured("AI_DAILY_X_BEARER is not configured")
    payload = _request_json(
        session,
        "GET",
        "https://api.x.com/2/tweets/search/recent",
        params={"query": f"({query}) -is:retweet", "max_results": max(10, min(limit, 100)),
                "tweet.fields": "created_at,entities"},
        headers={"Authorization": f"Bearer {token}", "User-Agent": "nbs-collector/0.2"},
    )
    return [candidate_from_x(tweet, query) for tweet in payload.get("data", [])
            if isinstance(tweet, dict) and tweet.get("id")]


def fetch_reddit(session, subreddit, limit=25):
    client_id = os.environ.get("AI_DAILY_REDDIT_CLIENT_ID")
    client_secret = os.environ.get("AI_DAILY_REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise Unconfigured("Reddit API credentials are not configured")
    user_agent = "windows:nbs-daily:0.2 (by /u/beaten2it)"
    token = _request_json(
        session,
        "POST",
        "https://www.reddit.com/api/v1/access_token",
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        headers={"User-Agent": user_agent},
    ).get("access_token")
    if not token:
        raise RuntimeError("Reddit OAuth returned no access token")
    payload = _request_json(
        session,
        "GET",
        f"https://oauth.reddit.com/r/{subreddit}/new",
        params={"limit": limit, "raw_json": 1},
        headers={"Authorization": f"Bearer {token}", "User-Agent": user_agent},
    )
    children = payload.get("data", {}).get("children", [])
    return [candidate_from_reddit(row.get("data", {}), subreddit) for row in children
            if isinstance(row, dict) and row.get("data", {}).get("id")]


def _safe_error(error):
    message = f"{type(error).__name__}: {error}"
    for name in _SECRET_ENV:
        value = os.environ.get(name)
        if value:
            message = message.replace(value, "[redacted]")
    message = re.sub(r"(?i)(Authorization\s*:\s*Bearer)\s+\S+",
                     r"\1 [redacted]", message)
    return message[:500]


def collect_with(adapters, date, cap=25):
    candidates = []
    health = []
    for adapter in adapters:
        started = time.monotonic()
        rows = []
        status = "failed"
        error = ""
        try:
            rows = adapter["fetch"]() or []
            if not isinstance(rows, list) or not all(isinstance(row, Candidate) for row in rows):
                raise TypeError("source adapter did not return Candidate list")
            rows = [row for row in rows if row.url and within_window(row.published_at, date)]
            status = "ok" if rows else "empty"
        except Degraded as exc:
            rows = [row for row in exc.candidates
                    if isinstance(row, Candidate) and row.url and within_window(row.published_at, date)]
            status = "degraded"
            error = _safe_error(exc)
        except Unconfigured as exc:
            status = "unconfigured"
            error = _safe_error(exc)
        except Exception as exc:
            status = "failed"
            error = _safe_error(exc)
        candidates.extend(rows)
        health.append(SourceHealth(
            lane=adapter["lane"],
            name=adapter["name"],
            status=status,
            candidate_count=len(rows),
            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
            error=error,
        ))
    return finalize_candidates(candidates, cap), health


def default_adapters(session=None):
    session = session or requests.Session()
    adapters = [
        {"name": feed["name"], "lane": feed["lane"],
         "fetch": lambda feed=feed: fetch_rss(feed, session)}
        for feed in sources.RSS_FEEDS
    ]
    adapters.append({"name": "Hacker News", "lane": "developer",
                     "fetch": lambda: fetch_hn(session)})
    adapters.extend(
        {"name": f"Bluesky @{handle}", "lane": "social",
         "fetch": lambda handle=handle: fetch_bluesky(session, handle)}
        for handle in sources.BLUESKY_ACCOUNTS
    )
    adapters.extend(
        {"name": f"GDELT {index + 1}", "lane": "web",
         "fetch": lambda query=query: fetch_gdelt(session, query)}
        for index, query in enumerate(sources.GDELT_QUERIES)
    )
    adapters.extend(
        {"name": f"GitHub {repo}", "lane": "developer",
         "fetch": lambda repo=repo: fetch_github(session, repo)}
        for repo in sources.GITHUB_REPOS
    )
    adapters.extend(
        {"name": f"X {index + 1}", "lane": "social",
         "fetch": lambda query=query: fetch_x(session, query)}
        for index, query in enumerate(sources.X_QUERIES)
    )
    adapters.extend(
        {"name": f"Reddit r/{subreddit}", "lane": "social",
         "fetch": lambda subreddit=subreddit: fetch_reddit(session, subreddit)}
        for subreddit in sources.REDDIT_SUBS
    )
    return adapters


def collect(date, cap=25, session=None):
    return collect_with(default_adapters(session), date, cap)


def write_candidates(date, candidates, health=None):
    directory = run_dir(date)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "candidates.json"
    path.write_text(json.dumps([candidate.to_dict() for candidate in candidates],
                               ensure_ascii=False, indent=2), encoding="utf-8")
    if health is not None:
        (directory / "source_health.json").write_text(
            json.dumps([row.to_dict() for row in health], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args(argv)
    if not _DATE_RE.fullmatch(args.date or ""):
        parser.error("--date must be YYYY-MM-DD")
    candidates, health = collect(args.date)
    path = write_candidates(args.date, candidates, health)
    unavailable = sum(row.status in {"unconfigured", "degraded", "failed"} for row in health)
    print(f"collected {len(candidates)} candidates from {len(health)} sources "
          f"({unavailable} unavailable/degraded) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
