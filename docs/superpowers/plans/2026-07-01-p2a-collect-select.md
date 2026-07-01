# P2a — 수집 + 중복판정·선별 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 하루치 AI 뉴스 후보를 **RSS 코어 소스**에서 수집하고, ledger 대비 **내용 기반 중복판정**(claude -p) + 중요도 순위로 선별해, P2b가 소비할 **선정 JSON**(`runs/<date>/selection.json`)을 결정론적으로 생성한다. (전문 fetch·블로그 생성=P2b, 조립·발행=P2c.)

**Architecture:** 결정론적 Python 패키지 `nbs/`. 수집은 RSS(feedparser). 중복판정·선별만 `claude -p`(구독, **stdin으로 프롬프트 전달**) 1회. 순수 로직(모델·ledger·파싱·정규화·검증·카운트)은 TDD, 네트워크/LLM은 얇게 감싸 통합 스모크로 검증.

**Tech Stack:** Python 3.11+(현재 3.14), feedparser+requests, `claude -p`(stdin), pytest.

## Global Constraints

- 작업 디렉터리 `/home/beaten/project/NBs`. **새 브랜치 `p2a-collect-select`**, 최종 리뷰 후 main 머지(기본 브랜치 직접작업 금지).
- 패키지 `nbs/`. CLI: `python -m nbs.collect --date YYYY-MM-DD`, `python -m nbs.select --date YYYY-MM-DD`.
- **v0 소스 = RSS 코어 + X(twitter) + Reddit(opencli).**
  - X: `twitter` CLI, 이미 인증(@beaten2it, `twitter status` ok). `twitter search "<q>" --type latest --json -n N`.
  - Reddit: `opencli reddit subreddit <name> --limit N -f json`. **Chrome + OpenCLI Browser-Bridge 확장 상시 필요** — 안 떠 있으면 `BROWSER_CONNECT` → **가드 스킵+로그**. 무인 실행 시 Chrome·확장 기동/점검은 **P3 preflight** 책임.
  - Threads: 후속.
  - 각 어댑터는 실패 시 `[]` 반환(한 소스 죽어도 run 진행). 스킵 시 로그(조용한 누락 금지).
- **insane-search는 P2a 미사용 — P2b(전문 fetch)에서** 페이월·차단·JS·동영상 grounding 폴백(Jina Reader/curl_cffi/yt-dlp/Playwright)으로 사용.
- 날짜·시각: KST 출력 라벨, **시간 비교는 UTC 통일**. RSS `published_parsed`는 UTC → `tzinfo=timezone.utc`로 라벨. naive 입력은 UTC로 간주(KST 라벨 금지 — 9h 오류 방지). "최근 창" = run date 00:00 KST를 UTC로 환산한 시점 기준 직전 ~30h.
- `claude -p`는 **프롬프트를 stdin으로**(`subprocess.run(["claude","-p"], input=text, ...)`) — argv 길이/이스케이프 회피. (검증: `echo ...|claude -p` 동작 확인됨.)
- **카운트는 로컬 재계산**(LLM이 준 skipped_count 신뢰 금지). 선별 항목의 **url은 후보에 존재**해야 하고, **url·event_key는 선별 내에서 유일**해야(membership·uniqueness 검증, 실패 시 abort). (Candidate엔 event_key 없음 — membership은 url 기준.)
- run 산출물 `runs/<date>/`(gitignore). ledger `data/published.csv`는 커밋.
- **데이터 계약(고정 — P2b/P2c 소비):**
  - **Candidate**: `{ "source", "source_type":"article|sns|paper|repo|video", "title", "url", "canonical_url", "published_at":ISO8601|null, "snippet", "raw_id" }`
  - **SelectionItem**: `{ "event_key":kebab, "title", "url", "source", "source_type", "evidence_type", "dedup":"new|followup|skip", "prior_post_path":str|null, "rank":int, "rationale" }`
  - **selection.json 루트**: `{ "date", "items":[SelectionItem(skip 제외)], "selected_count":int, "skipped_count":int, "generated_with" }`
  - **Ledger row** (`data/published.csv` 헤더): `canonical_key,event_key,date,title,url,source,post_path,summary,entities,tags,confidence`
- **중복 규칙(스펙 §6):** URL canonical(UTM/fbclid/gclid 제거, 호스트 소문자, 끝슬래시 정리) 1차 제거. 내용판정: skip은 *새 정보 0 순수 재보도*만. 변화·후속 → `followup`+prior_post_path. 애매하면 keep. event_key는 LLM 생성(불안정성은 v0 수용 — 규모 시 클러스터/임베딩, 스펙 ponytail). 정규화 title 슬러그를 힌트로 제공.
- 시크릿: 토큰·쿠키 출력·커밋 금지(기존 `.gitignore`). 커밋: 태스크별 1커밋. 의존성 `requirements.txt`.

---

### Task 0: P2a 작업 브랜치

- [ ] **Step 1: 브랜치 생성**

```bash
cd /home/beaten/project/NBs
git switch -c p2a-collect-select
git branch --show-current
```
Expected: `p2a-collect-select` (이후 모든 커밋 이 브랜치에).

---

### Task 1: 패키지 골격 + 모델 + 검증

**Files:** Create `nbs/__init__.py`, `nbs/config.py`, `nbs/models.py`, `requirements.txt` · Test `tests/test_models.py`

**Interfaces:** `Candidate`, `SelectionItem` dataclass; `validate_selection(obj)->list[str]`; `validate_against_candidates(obj, cand_canon_urls:set)->list[str]`(멤버십+유일성); 상수 `SOURCE_TYPES/EVIDENCE_TYPES/DEDUP_VALUES`; `config.KST/LEDGER_PATH/run_dir`.

- [ ] **Step 1: 실패 테스트 `tests/test_models.py`**

```python
from nbs.models import validate_selection, validate_against_candidates

BASE_ITEM = {"event_key":"k","title":"T","url":"https://x/y","source":"s",
             "source_type":"article","evidence_type":"article","dedup":"new",
             "prior_post_path":None,"rank":1,"rationale":"why"}

def _obj(items): return {"date":"2026-07-01","items":items,"selected_count":len(items),
                         "skipped_count":0,"generated_with":"claude-p"}

def test_valid_selection_passes():
    assert validate_selection(_obj([dict(BASE_ITEM)])) == []

def test_bad_dedup_value_flagged():
    it = dict(BASE_ITEM, dedup="MAYBE")
    assert any("dedup" in e for e in validate_selection(_obj([it])))

def test_followup_requires_prior_path():
    it = dict(BASE_ITEM, dedup="followup", prior_post_path=None)
    errs = validate_selection(_obj([it]))
    assert any("prior_post_path" in e for e in errs)

def test_membership_and_uniqueness():
    it = dict(BASE_ITEM, url="https://x/y")
    cand = {"https://x/y"}
    assert validate_against_candidates(_obj([it]), cand) == []
    # url not in candidates
    bad = dict(BASE_ITEM, url="https://x/z")
    assert any("not in candidates" in e for e in validate_against_candidates(_obj([bad]), cand))
    # duplicate event_key
    dup = _obj([dict(BASE_ITEM), dict(BASE_ITEM, url="https://x/y")])
    assert any("duplicate" in e for e in validate_against_candidates(dup, cand))
```

- [ ] **Step 2: 실패 확인** — Run: `cd /home/beaten/project/NBs && python -m pytest tests/test_models.py -q` → FAIL

- [ ] **Step 3: `nbs/config.py`**

```python
from datetime import timezone, timedelta
from pathlib import Path
KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LEDGER_PATH = DATA_DIR / "published.csv"
RUNS_DIR = ROOT / "runs"
def run_dir(date: str) -> Path: return RUNS_DIR / date
```

- [ ] **Step 4: `nbs/models.py`**

```python
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

SOURCE_TYPES = {"article","sns","paper","repo","video"}
EVIDENCE_TYPES = SOURCE_TYPES
DEDUP_VALUES = {"new","followup","skip"}
_DROP_PARAMS = ("utm_","fbclid","gclid","mc_cid","mc_eid")

def canonicalize_url(u: str) -> str:
    if not u: return ""
    try: s = urlsplit(u.strip())
    except Exception: return u.strip()
    q = [(k,v) for k,v in parse_qsl(s.query) if not k.lower().startswith(_DROP_PARAMS)]
    path = s.path.rstrip("/") or "/"
    return urlunsplit((s.scheme.lower(), s.netloc.lower(), path, urlencode(q), ""))

@dataclass
class Candidate:
    source: str; source_type: str; title: str; url: str; canonical_url: str
    published_at: Optional[str]; snippet: str; raw_id: str
    def to_dict(self): return asdict(self)

@dataclass
class SelectionItem:
    event_key: str; title: str; url: str; source: str; source_type: str
    evidence_type: str; dedup: str; prior_post_path: Optional[str]; rank: int; rationale: str

_ITEM_KEYS = {"event_key","title","url","source","source_type","evidence_type",
              "dedup","prior_post_path","rank","rationale"}

def validate_selection(obj) -> list:
    errs = []
    if not isinstance(obj, dict): return ["root not a dict"]
    for k in ("date","items","selected_count","skipped_count","generated_with"):
        if k not in obj: errs.append(f"missing root key: {k}")
    for i, it in enumerate(obj.get("items", [])):
        miss = _ITEM_KEYS - set(it)
        if miss: errs.append(f"item[{i}] missing: {sorted(miss)}")
        if it.get("source_type") not in SOURCE_TYPES: errs.append(f"item[{i}] bad source_type")
        if it.get("evidence_type") not in EVIDENCE_TYPES: errs.append(f"item[{i}] bad evidence_type")
        if it.get("dedup") not in DEDUP_VALUES: errs.append(f"item[{i}] bad dedup")
        if it.get("dedup") == "followup" and not it.get("prior_post_path"):
            errs.append(f"item[{i}] followup requires prior_post_path")
        if not isinstance(it.get("rank"), int): errs.append(f"item[{i}] rank not int")
    return errs

def validate_against_candidates(obj, cand_canon_urls: set) -> list:
    errs = []
    seen_keys, seen_urls = set(), set()
    for i, it in enumerate(obj.get("items", [])):
        cu = canonicalize_url(it.get("url",""))
        if cu not in cand_canon_urls: errs.append(f"item[{i}] url not in candidates: {it.get('url')}")
        if it.get("event_key") in seen_keys: errs.append(f"item[{i}] duplicate event_key")
        if cu in seen_urls: errs.append(f"item[{i}] duplicate url")
        seen_keys.add(it.get("event_key")); seen_urls.add(cu)
    return errs
```

- [ ] **Step 5: `requirements.txt`**

```text
feedparser>=6.0
requests>=2.31
```

- [ ] **Step 5b: 의존성 설치** — Run: `pip install -r requirements.txt` → feedparser/requests 설치(이후 Task 4 `nbs.collect` import 가능). Expected: 설치 성공 또는 already satisfied.

- [ ] **Step 6: pass 확인** — `python -m pytest tests/test_models.py -q` → PASS (4 passed)

- [ ] **Step 7: 커밋** — `git add nbs/__init__.py nbs/config.py nbs/models.py tests/test_models.py requirements.txt && git commit -m "feat(p2a): models, url canonicalize, selection+candidate validation"`

---

### Task 2: ledger (published.csv 읽기/쓰기)

**Files:** Create `nbs/ledger.py` · Test `tests/test_ledger.py`

**Interfaces:** `LEDGER_HEADER`; `read_recent(days,today,path=None)->list[dict]`; `append_rows(rows,path=None)`; `ledger_digest(rows)->list[dict]`(`{event_key,title,summary,date,post_path}`).

- [ ] **Step 1: 실패 테스트 `tests/test_ledger.py`**

```python
from nbs import ledger
def test_roundtrip_and_recent(tmp_path):
    p = tmp_path/"led.csv"
    rows = [
      {"canonical_key":"a","event_key":"a","date":"2026-06-20","title":"A","url":"u1","source":"s",
       "post_path":"posts/a","summary":"sa","entities":"x","tags":"t","confidence":"high"},
      {"canonical_key":"b","event_key":"b","date":"2026-06-30","title":"B","url":"u2","source":"s",
       "post_path":"posts/b","summary":"sb","entities":"y","tags":"t","confidence":"high"}]
    ledger.append_rows(rows, path=p)
    recent = ledger.read_recent(days=7, today="2026-07-01", path=p)
    assert {r["event_key"] for r in recent} == {"b"}
    assert ledger.ledger_digest(recent)[0].keys() >= {"event_key","title","summary","date","post_path"}
def test_append_creates_header(tmp_path):
    p = tmp_path/"led.csv"; ledger.append_rows([], path=p)
    assert p.read_text().strip().split("\n")[0] == ",".join(ledger.LEDGER_HEADER)
```

- [ ] **Step 2: 실패 확인** — `python -m pytest tests/test_ledger.py -q` → FAIL

- [ ] **Step 3: `nbs/ledger.py`**

```python
import csv
from datetime import date as _date, timedelta
from pathlib import Path
from .config import LEDGER_PATH
LEDGER_HEADER = ["canonical_key","event_key","date","title","url","source",
                 "post_path","summary","entities","tags","confidence"]
def _p(path): return Path(path) if path else LEDGER_PATH
def append_rows(rows, path=None):
    p=_p(path); p.parent.mkdir(parents=True, exist_ok=True); new=not p.exists()
    with p.open("a", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=LEDGER_HEADER)
        if new: w.writeheader()
        for r in rows: w.writerow({k:r.get(k,"") for k in LEDGER_HEADER})
def read_recent(days, today, path=None):
    p=_p(path)
    if not p.exists(): return []
    cutoff=_date.fromisoformat(today)-timedelta(days=days); out=[]
    with p.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                if _date.fromisoformat(r["date"])>=cutoff: out.append(r)
            except (ValueError, KeyError): continue
    return out
def ledger_digest(rows):
    return [{"event_key":r.get("event_key",""),"title":r.get("title",""),
             "summary":r.get("summary",""),"date":r.get("date",""),
             "post_path":r.get("post_path","")} for r in rows]
```

- [ ] **Step 4: pass 확인** — `python -m pytest tests/test_ledger.py -q` → PASS

- [ ] **Step 5: 커밋** — `git add nbs/ledger.py tests/test_ledger.py && git commit -m "feat(p2a): ledger read_recent/append/digest"`

---

### Task 3: 코어 소스 정의 (RSS + X + Reddit)

**Files:** Create `nbs/sources.py` · Test `tests/test_sources.py`

**Interfaces:** `RSS_FEEDS: list[{name,url,source_type}]`, `X_QUERIES: list[str]`, `REDDIT_SUBS: list[str]` (모두 v0 활성; Reddit은 Chrome 미가동 시 collect에서 가드 스킵).

- [ ] **Step 1: 실패 테스트 `tests/test_sources.py`**

```python
from nbs import sources
def test_core_rss_present():
    names = {f["name"] for f in sources.RSS_FEEDS}
    assert {"GeekNews","HackerNews","arXiv cs.AI"} <= names
    for f in sources.RSS_FEEDS:
        assert f["url"].startswith("http") and f["source_type"] in {"article","paper"}
def test_sns_sources_active():
    assert len(sources.X_QUERIES) >= 3
    assert "LocalLLaMA" in sources.REDDIT_SUBS
```

- [ ] **Step 2: 실패 확인** — `python -m pytest tests/test_sources.py -q` → FAIL

- [ ] **Step 3: `nbs/sources.py`** (URL은 Task 6에서 실검증, 죽은 피드 교체)

```python
# v0 활성. RSS 코어 (죽은 피드는 Task 6 스모크에서 교체) + X(twitter) + Reddit(opencli).
RSS_FEEDS = [
    {"name":"OpenAI",        "url":"https://openai.com/news/rss.xml",                                  "source_type":"article"},
    {"name":"GoogleAI",      "url":"https://blog.google/technology/ai/rss/",                           "source_type":"article"},
    {"name":"HuggingFace",   "url":"https://huggingface.co/blog/feed.xml",                             "source_type":"article"},
    {"name":"GeekNews",      "url":"https://feeds.feedburner.com/geeknews-feed",                       "source_type":"article"},
    {"name":"HackerNews",    "url":"https://hnrss.org/frontpage",                                      "source_type":"article"},
    {"name":"TheVerge AI",   "url":"https://www.theverge.com/rss/ai-artificial-intelligence/index.xml","source_type":"article"},
    {"name":"TechCrunch AI", "url":"https://techcrunch.com/category/artificial-intelligence/feed/",    "source_type":"article"},
    {"name":"arXiv cs.AI",   "url":"https://rss.arxiv.org/rss/cs.AI",                                  "source_type":"paper"},
    {"name":"arXiv cs.CL",   "url":"https://rss.arxiv.org/rss/cs.CL",                                  "source_type":"paper"},
]
# X (twitter CLI, 인증됨 @beaten2it) — v0 활성
X_QUERIES = [
    'AI agents OR "coding agents" OR agentic',
    '"Claude Code" OR Cursor OR Codex OR Windsurf',
    "OpenAI OR Anthropic OR Gemini OR Grok model",
    "open source LLM OR Qwen OR DeepSeek OR Mistral",
]
# Reddit (opencli) — v0 활성(best-effort). Chrome+Browser-Bridge 미가동 시 collect에서 가드 스킵.
REDDIT_SUBS = ["LocalLLaMA", "MachineLearning"]
```

- [ ] **Step 4: pass 확인** — `python -m pytest tests/test_sources.py -q` → PASS

- [ ] **Step 5: 커밋** — `git add nbs/sources.py tests/test_sources.py && git commit -m "feat(p2a): core sources (RSS + X queries + Reddit subs)"`

---

### Task 4: 수집(collect) — 후보 + canonical URL 중복제거 + 시간창

**Files:** Create `nbs/collect.py` · Test `tests/test_collect.py` · Fixture `tests/fixtures/sample_rss.xml`

**Interfaces:** `parse_rss(xml_bytes,feed)->list[Candidate]`; `within_window(pub_iso,today,hours=30)->bool`; `dedup_by_url(cands)->list[Candidate]`(canonical 기준); `parse_twitter_json(stdout,query)->list[Candidate]`; `fetch_x(query,limit)`/`fetch_reddit(sub,limit)`(가드, 실패→`[]`); `collect(date)->list[Candidate]`(RSS+X+Reddit); `write_candidates(date,cands)`. CLI `python -m nbs.collect --date`.
> Reddit 출력 JSON 필드명은 Chrome 미가동으로 미검증 — **구현 스모크(Task 6, Chrome 띄운 상태)에서 `opencli reddit subreddit ... -f json` 실출력 확인 후 parse 필드 보정**(title/url/permalink/selftext/created 등 추정).

- [ ] **Step 1: 실패 테스트 + fixture**

`tests/fixtures/sample_rss.xml`:
```xml
<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>New AI model</title><link>https://ex.com/a?utm_source=rss</link>
<pubDate>Mon, 30 Jun 2026 09:00:00 +0000</pubDate><description>summary</description></item>
<item><title>Dup link</title><link>https://ex.com/a</link>
<pubDate>Mon, 30 Jun 2026 10:00:00 +0000</pubDate><description>dup</description></item>
</channel></rss>
```

`tests/test_collect.py`:
```python
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

def test_parse_twitter_json_builds_url():
    raw='[{"id":"123","author":"@a","text":"Claude news here"}]'
    cands = collect.parse_twitter_json(raw, "q")
    assert len(cands)==1 and cands[0].url=="https://x.com/i/status/123"
    assert cands[0].source_type=="sns" and cands[0].title.startswith("Claude")
```

- [ ] **Step 2: 실패 확인** — `python -m pytest tests/test_collect.py -q` → FAIL

- [ ] **Step 3: `nbs/collect.py`**

```python
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
```

- [ ] **Step 4: pass 확인** — `python -m pytest tests/test_collect.py -q` → PASS

- [ ] **Step 5: 커밋** — `git add nbs/collect.py tests/test_collect.py tests/fixtures/sample_rss.xml && git commit -m "feat(p2a): collect RSS+X+Reddit with canonical-url dedup + UTC window"`

---

### Task 5: 중복판정·선별(select) — claude -p (stdin)

**Files:** Create `nbs/select.py`, `prompts/select.md` · Test `tests/test_select.py`

**Interfaces:** `build_prompt_input(cands,digest,date)->str`; `run_claude(text,timeout=300)->str`(stdin); `parse_selection(raw)->dict`; `recount(obj)`(selected/skipped 로컬 재계산); `select(date)->dict`. CLI `python -m nbs.select --date`.

- [ ] **Step 1: 실패 테스트 `tests/test_select.py`**

```python
from nbs import select
def test_parse_strips_fences():
    raw='설명\n```json\n{"date":"2026-07-01","items":[],"selected_count":0,"skipped_count":0,"generated_with":"claude-p"}\n```\n끝'
    assert select.parse_selection(raw)["date"]=="2026-07-01"
def test_recount_local():
    obj={"items":[{"dedup":"new"},{"dedup":"followup"},{"dedup":"skip"}],
         "selected_count":99,"skipped_count":99}
    select.recount(obj)
    assert obj["selected_count"]==2 and obj["skipped_count"]==1
def test_build_input_has_ledger_and_candidates():
    txt=select.build_prompt_input(
        [{"source":"OpenAI","title":"T","url":"u","canonical_url":"u","snippet":"s",
          "source_type":"article","published_at":None,"raw_id":"r"}],
        [{"event_key":"old","title":"O","summary":"s","date":"2026-06-30","post_path":"posts/old"}],
        "2026-07-01")
    assert "OpenAI" in txt and "old" in txt and "2026-07-01" in txt
```

- [ ] **Step 2: 실패 확인** — `python -m pytest tests/test_select.py -q` → FAIL

- [ ] **Step 3: 프롬프트 `prompts/select.md`**

```markdown
너는 AI 데일리 편집자다. 후보(candidates)와 최근 발행 ledger를 보고 오늘 다룰 항목을 선별한다.

## 규칙
- 중복: ledger event(제목+요약)와 **내용으로** 비교.
  - 새 정보 0 순수 재보도 → dedup:"skip"
  - 변화·후속(새 디테일/벤치마크/가격/반응/버전) → dedup:"followup" + 해당 ledger post_path를 prior_post_path
  - 새 사건 → dedup:"new"
  - 애매하면 keep(new/followup). 과잉 skip 금지.
- url은 후보의 url을 **그대로** 쓴다(새 url 만들지 말 것).
- event_key: 사건 단위 kebab 슬러그. 같은 사건=같은 키.
- rank(1=최상) 정렬. 우선순위: AI에이전트>코딩도구>모델업데이트>오픈소스LLM>제품/투자>멀티모달>논문/벤치>기업/생산성>한국커뮤니티>규제(큰건만).
- evidence_type=source_type. 홍보·저품질 제외.

## 출력 (valid JSON만, ```json 펜스 안에. 아래는 형식 예시 — 항목은 items 배열에 추가)
{"date":"<DATE>","items":[{"event_key":"openai-foo-launch","title":"한글 제목","url":"https://원문","source":"OpenAI","source_type":"article","evidence_type":"article","dedup":"new","prior_post_path":null,"rank":1,"rationale":"왜 중요한지 한 줄"}],"selected_count":1,"skipped_count":0,"generated_with":"claude-p"}

## 입력
<<INPUT>>
```

- [ ] **Step 4: `nbs/select.py`**

```python
import argparse, json, re, subprocess
from pathlib import Path
from .config import run_dir
from .models import validate_selection, validate_against_candidates, canonicalize_url
from . import ledger as ledger_mod

PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "select.md"

def build_prompt_input(cands, digest, date):
    payload={"date":date,"recent_ledger":digest,"candidates":cands}
    return PROMPT.read_text(encoding="utf-8").replace(
        "<<INPUT>>", json.dumps(payload, ensure_ascii=False, indent=2)).replace("<DATE>", date)

def parse_selection(raw):
    m=re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.S)
    blob=m.group(1) if m else raw[raw.find("{"):raw.rfind("}")+1]
    return json.loads(blob)

def run_claude(text, timeout=300):
    r=subprocess.run(["claude","-p"], input=text, capture_output=True, text=True, timeout=timeout)
    if r.returncode!=0: raise RuntimeError(f"claude -p failed: {r.stderr[:300]}")
    return r.stdout

def recount(obj):
    items=obj.get("items",[])
    obj["skipped_count"]=sum(1 for it in items if it.get("dedup")=="skip")
    obj["items"]=[it for it in items if it.get("dedup")!="skip"]
    obj["items"].sort(key=lambda x:x.get("rank",999))
    obj["selected_count"]=len(obj["items"])

def select(date):
    cands=json.loads((run_dir(date)/"candidates.json").read_text(encoding="utf-8"))
    if not cands:
        obj={"date":date,"items":[],"selected_count":0,"skipped_count":0,"generated_with":"none(empty)"}
        (run_dir(date)/"selection.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
        return obj
    digest=ledger_mod.ledger_digest(ledger_mod.read_recent(days=14, today=date))
    obj=parse_selection(run_claude(build_prompt_input(cands, digest, date)))
    errs=validate_selection(obj)
    if errs: raise ValueError("selection schema invalid: "+"; ".join(errs[:8]))
    cand_urls={canonicalize_url(c["url"]) for c in cands}
    errs=validate_against_candidates(obj, cand_urls)
    if errs: raise ValueError("selection membership/uniqueness invalid: "+"; ".join(errs[:8]))
    recount(obj)
    (run_dir(date)/"selection.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    return obj

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--date", required=True); a=ap.parse_args()
    obj=select(a.date)
    print(f"selected {obj['selected_count']} (skipped {obj['skipped_count']}) -> runs/{a.date}/selection.json")

if __name__ == "__main__": main()
```

- [ ] **Step 5: pass 확인** — `python -m pytest tests/test_select.py -q` → PASS

- [ ] **Step 6: 커밋** — `git add nbs/select.py prompts/select.md tests/test_select.py && git commit -m "feat(p2a): claude -p select (stdin) + local recount + membership validation"`

---

### Task 6: gitignore + 통합 스모크(실데이터 1회)

**Files:** Modify `.gitignore` · Create `scripts/p2a_smoke.sh`

- [ ] **Step 1: `.gitignore`에 추가** — `runs/`, `__pycache__/`, `.pytest_cache/`

- [ ] **Step 2: deps 설치** — `pip install -r requirements.txt` (feedparser 설치)

- [ ] **Step 3: `scripts/p2a_smoke.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
DATE="${1:?usage: p2a_smoke.sh YYYY-MM-DD}"
python -m nbs.collect --date "$DATE"
N=$(python -c "import json;print(len(json.load(open(f'runs/$DATE/candidates.json'))))")
echo "candidates: $N"
[ "$N" -gt 0 ] || { echo "FAIL: 0 candidates — sources.py 피드 점검"; exit 1; }
python -m nbs.select --date "$DATE"
python - "$DATE" <<'PY'
import json,sys
from nbs.models import validate_selection
o=json.load(open(f"runs/{sys.argv[1]}/selection.json"))
assert validate_selection(o)==[], "schema invalid"
assert o["selected_count"]==len(o["items"])
print("selected:",o["selected_count"],"| skipped:",o["skipped_count"],"\nSMOKE OK")
PY
```

- [ ] **Step 4: 전체 테스트 + 스모크(피드 실검증)**

```bash
python -m pytest -q
chmod +x scripts/p2a_smoke.sh
./scripts/p2a_smoke.sh 2026-07-01
```
Expected: pytest 전부 PASS; 스모크 `candidates: >0` + `SMOKE OK`. RSS+X(인증됨)로 후보는 확보됨. **Reddit이 후보에 들어오려면 Chrome+OpenCLI 확장을 띄운 상태**여야(아니면 가드 스킵, RSS+X만). 이때 `opencli reddit subreddit LocalLLaMA --limit 3 -f json` 실출력을 보고 **`fetch_reddit` 필드명 보정**(title/url/permalink/selftext/created). 죽은 RSS 피드는 `nbs/sources.py` URL 교체(각 피드 `curl -fsI` 200 확인).

- [ ] **Step 5: 커밋** — `git add .gitignore scripts/p2a_smoke.sh nbs/sources.py && git commit -m "test(p2a): gitignore scratch + integration smoke; fix dead feeds"`

- [ ] **Step 6: 완료 보고(5필드)** — 근본원인/변경/재발방지/검증(명령+출력)/남은 리스크.

---

## Self-Review

**Spec 커버리지(P2a):** §4 수집(RSS 코어; X/Reddit/Threads 명시 deferred) ✓ · §6 내용 중복판정(canonical URL 1차 + claude-p, keep 편향, skip=순수재보도, followup 링크) ✓ · ledger digest(rolling window) ✓ · 데이터 계약 고정 ✓.

**Placeholder 스캔:** 순수 로직 실코드+TDD. RSS URL은 Task 6 실검증·교체 명시. X/Reddit는 의도적 deferred(빈 리스트+로그). TBD 없음.

**타입/이름 일관성:** Candidate(canonical_url 추가)·SelectionItem 필드, ledger 헤더, dedup 값, selection 루트(selected_count/skipped_count) 계약·코드·테스트·프롬프트 동일.

**Codex 적대 리뷰 반영(R1):** BLOCKER 전부 — claude -p **stdin**(검증됨), **카운트 로컬 재계산**, **datetime UTC 통일**(published_parsed=UTC 라벨, naive=UTC), **walrus 테스트 제거**. HIGH — RSS 실검증(Task6), feedparser updated_parsed fallback, **canonical URL(UTM 제거)**, **멤버십·유일성 검증**, event_key 불안정성 v0 수용(명시). MED — 빈 후보 가드(claude 생략), **범위 축소(RSS-only, X/Reddit/Threads 후속)**.

**Codex 적대 리뷰 반영(R2, 수렴):** R1 8개 OK(=f 문구만 보정). 신규 BLOCKER 3개 반영 — ① 의존성 설치를 Task 1(Step 5b)로 당김(Task 4 import 실패 방지) ② 프롬프트 출력 예시를 valid JSON으로 ③ 브랜치 생성 Task 0 추가. **수렴 — 리뷰 종료.**

**정찰 후 소스 확정(2026-07-01):** `twitter`(pipx, 인증 @beaten2it) 실동작 확인 → X 활성. `opencli reddit`은 Chrome+Browser-Bridge 확장 필요(BROWSER_CONNECT) → Reddit 활성하되 가드 스킵 + 무인 Chrome 기동은 P3. X/Reddit 어댑터(fetch_x/parse_twitter_json/fetch_reddit) 추가. Reddit 출력 필드는 impl 스모크(Chrome up)에서 검증·보정. insane-search는 P2b fetch 폴백으로 명시.
- **어댑터 델타 Codex 점검:** 신규 BLOCKER 0. HIGH 반영 — within_window가 **non-str(reddit epoch) 방어**(TypeError 차단, collect 누수 방지) + 테스트 추가, parse_twitter_json `created_at or time`. reddit JSON shape는 impl 검증으로 위임(명시됨).

**남은 미결(P2b/c):** 전문 fetch(article/sns/paper별)+grounding 게이트, 항목당 claude -p 생성·timeout·실패격리, 최소발행 floor, News/UseCase 조립, 원자적 스테이징·발행, 생성 후 ledger append(post_path 채움), X/Reddit/Threads 소스 활성화.
