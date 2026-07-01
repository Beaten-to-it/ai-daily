import argparse, json, shutil, subprocess
from datetime import datetime, timedelta, timezone
import feedparser, requests
from .config import KST, run_dir
from .models import Candidate, canonicalize_url
from . import sources

def parse_rss(xml_bytes, feed):
    d = feedparser.parse(xml_bytes); out=[]
    for e in d.entries:
        tm = getattr(e,"published_parsed",None) or getattr(e,"updated_parsed",None)
        pub = datetime(*tm[:6], tzinfo=timezone.utc).isoformat() if tm else None
        url = (e.get("link") or "").strip()
        out.append(Candidate(source=feed["name"], source_type=feed["source_type"],
            title=(e.get("title") or "").strip(), url=url, canonical_url=canonicalize_url(url),
            published_at=pub, snippet=(e.get("summary","") or "")[:500],
            raw_id=(e.get("id") or url)))
    return out

def within_window(pub_iso, today, hours=30):
    if not pub_iso or not isinstance(pub_iso, str): return True   # epoch int/None → 보수적 통과(TypeError 차단)
    try: pub = datetime.fromisoformat(pub_iso)
    except ValueError: return True
    if pub.tzinfo is None: pub = pub.replace(tzinfo=timezone.utc)   # naive=UTC (KST 라벨 금지)
    end = datetime.fromisoformat(today+"T00:00:00").replace(tzinfo=KST).astimezone(timezone.utc)
    return (end - pub) <= timedelta(hours=hours) and pub <= end + timedelta(hours=6)

def dedup_by_url(cands):
    seen, out = set(), []
    for c in cands:
        key = c.canonical_url or c.url
        if key and key not in seen: seen.add(key); out.append(c)
    return out

def fetch_rss(feed, timeout=20):
    r = requests.get(feed["url"], timeout=timeout, headers={"User-Agent":"nbs-collector/0.1"})
    r.raise_for_status(); return parse_rss(r.content, feed)

def parse_twitter_json(stdout, query):
    try: data = json.loads(stdout or "[]")
    except json.JSONDecodeError: return []
    out=[]
    for t in (data if isinstance(data, list) else []):
        tid = str(t.get("id","")).strip()
        if not tid: continue
        text = t.get("text") or ""
        url = f"https://x.com/i/status/{tid}"
        out.append(Candidate(source="X", source_type="sns", title=text[:100], url=url,
            canonical_url=canonicalize_url(url),
            published_at=t.get("created_at") or t.get("time"),  # 비ISO('Jun 30 23:49')는 window가 통과 처리
            snippet=text[:500], raw_id=tid))
    return out

def fetch_x(query, limit=15):
    if not shutil.which("twitter"): print("[info] twitter CLI 없음 — X 스킵"); return []
    try:
        r = subprocess.run(["twitter","search",query,"--type","latest","-n",str(limit),"--json"],
                           capture_output=True, text=True, timeout=90)
        if r.returncode != 0: print(f"[warn] X '{query[:30]}': rc={r.returncode}"); return []
        return parse_twitter_json(r.stdout, query)
    except Exception as e:
        print(f"[warn] X '{query[:30]}': {e}"); return []

def fetch_reddit(sub, limit=15):
    # opencli reddit: Chrome+Browser-Bridge 필요. 미연결이면 BROWSER_CONNECT → 가드 스킵.
    if not shutil.which("opencli"): print("[info] opencli 없음 — Reddit 스킵"); return []
    try:
        r = subprocess.run(["opencli","reddit","subreddit",sub,"--limit",str(limit),"-f","json"],
                           capture_output=True, text=True, timeout=90)
        if r.returncode != 0 or "BROWSER_CONNECT" in (r.stdout + r.stderr):
            print(f"[warn] Reddit r/{sub}: browser-bridge 미연결 — 스킵"); return []
        data = json.loads(r.stdout or "[]")
        items = data if isinstance(data, list) else data.get("posts", data.get("data", []))
        out=[]
        for p in items:
            url = p.get("url") or p.get("permalink") or ""
            if url.startswith("/"): url = "https://www.reddit.com" + url
            out.append(Candidate(source=f"reddit/{sub}", source_type="sns",
                title=(p.get("title") or "")[:200], url=url, canonical_url=canonicalize_url(url),
                published_at=p.get("created_at") or p.get("created"),
                snippet=(p.get("selftext") or p.get("text") or "")[:500], raw_id=str(p.get("id",""))))
        return [c for c in out if c.url]
    except Exception as e:
        print(f"[warn] Reddit r/{sub}: {e}"); return []

def collect(date):
    cands=[]
    for feed in sources.RSS_FEEDS:
        try: cands += [c for c in fetch_rss(feed) if within_window(c.published_at, date)]
        except Exception as e: print(f"[warn] RSS {feed['name']}: {e}")
    for q in sources.X_QUERIES:
        cands += [c for c in fetch_x(q) if within_window(c.published_at, date)]
    for sub in sources.REDDIT_SUBS:
        cands += [c for c in fetch_reddit(sub) if within_window(c.published_at, date)]
    return dedup_by_url(cands)

def write_candidates(date, cands):
    d=run_dir(date); d.mkdir(parents=True, exist_ok=True)
    p=d/"candidates.json"
    p.write_text(json.dumps([c.to_dict() for c in cands], ensure_ascii=False, indent=2), encoding="utf-8")
    return p

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--date", required=True); a=ap.parse_args()
    cands=collect(a.date); p=write_candidates(a.date, cands)
    print(f"collected {len(cands)} candidates -> {p}")

if __name__ == "__main__": main()
