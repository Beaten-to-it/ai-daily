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
    return urlunsplit((s.scheme.lower(), s.netloc.lower(), path, urlencode(sorted(q)), ""))

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
    if not isinstance(obj.get("items"), list):
        errs.append("items not a list"); return errs
    for i, it in enumerate(obj.get("items", [])):
        if not isinstance(it, dict):
            errs.append(f"item[{i}] not a dict"); continue
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

EVIDENCE_LEVELS = {"confirmed", "short", "exclude"}

@dataclass
class FetchResult:
    event_key: str; url: str; source_type: str
    text: str; evidence_level: str; via: str; fetch_ok: bool
    def to_dict(self): return asdict(self)

@dataclass
class GenerationResult:
    event_key: str; title: str; url: str; source: str; source_type: str
    evidence_level: str; status: str            # ok | failed | excluded
    post_path: Optional[str]; slug: str; rank: int
    rationale: str = ""
    error: Optional[str] = None
    def to_dict(self): return asdict(self)

REQUIRED_FRONTMATTER = {"title","date","tags","source_url","source_lang",
                        "source_type","evidence_level","event_key"}

def parse_frontmatter(md) -> dict:
    if not isinstance(md, str) or not md.lstrip().startswith("---"):
        return {}
    start = md.find("---")
    end = md.find("---", start + 3)
    if end == -1:
        return {}
    keys = {}
    for line in md[start+3:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            keys[k.strip()] = v.strip()
    return keys

def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s

def parse_frontmatter_strict(md) -> dict:
    # like parse_frontmatter but unquotes scalars and parses `key: [a, b]` as a list.
    # ponytail: NOT full YAML (stdlib-only rule); covers our own emitted front matter.
    # Inherits parse_frontmatter's unanchored-`---` split (documented defer-safe minor;
    # our posts never put `---` inside a value).
    out = {}
    for k, v in parse_frontmatter(md).items():
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            out[k] = [_unquote(x) for x in inner.split(",") if x.strip()] if inner else []
        else:
            out[k] = _unquote(v)
    return out

def validate_blog_output(md) -> list:
    if not isinstance(md, str) or not md.lstrip().startswith("---"):
        return ["missing front matter block"]
    start = md.find("---")
    end = md.find("---", start + 3)
    if end == -1:
        return ["unterminated front matter"]
    keys = parse_frontmatter(md)
    body = md[end+3:]
    errs = [f"front matter missing: {k}" for k in REQUIRED_FRONTMATTER - set(keys)]
    if keys.get("source_type") not in SOURCE_TYPES:
        errs.append("front matter bad source_type")
    if keys.get("evidence_level") not in {"confirmed","short"}:
        errs.append("front matter bad evidence_level")
    if not body.strip():
        errs.append("empty body")
    return errs
