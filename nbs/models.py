import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SOURCE_TYPES = {"article", "sns", "paper", "repo", "video"}
EVIDENCE_TYPES = SOURCE_TYPES
DEDUP_VALUES = {"new", "followup", "skip"}
DECISION_VALUES = {"select", "skip"}
REASON_CODES = {"selected", "duplicate", "stale", "weak_evidence",
                "low_significance", "off_topic"}
LANES = {"official", "media", "social", "research", "developer", "web"}
SOURCE_HEALTH_STATUSES = {"ok", "empty", "unconfigured", "degraded", "failed"}
_DROP_PARAMS = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid")


def canonicalize_url(url: str) -> str:
    if not isinstance(url, str) or not url:
        return ""
    try:
        split = urlsplit(url.strip())
    except Exception:
        return url.strip()
    query = [(key, value) for key, value in parse_qsl(split.query)
             if not key.lower().startswith(_DROP_PARAMS)]
    path = split.path.rstrip("/") or "/"
    return urlunsplit((split.scheme.lower(), split.netloc.lower(), path,
                       urlencode(sorted(query)), ""))


def candidate_id(url: str) -> str:
    return hashlib.sha256(canonicalize_url(url).encode("utf-8")).hexdigest()[:20]


@dataclass
class Candidate:
    source: str
    source_type: str
    title: str
    url: str
    canonical_url: str
    published_at: Optional[str]
    snippet: str
    raw_id: str
    lane: str = "official"
    discovered_via: str = ""

    def to_dict(self):
        data = asdict(self)
        data["candidate_id"] = candidate_id(self.url)
        return data


@dataclass
class SourceHealth:
    lane: str
    name: str
    status: str
    candidate_count: int
    elapsed_ms: int
    error: str = ""

    def __post_init__(self):
        if self.lane not in LANES or self.status not in SOURCE_HEALTH_STATUSES:
            raise ValueError("invalid source health")
        self.error = str(self.error)[:500]

    def to_dict(self):
        return asdict(self)


_DECISION_KEYS = {"candidate_id", "decision", "dedup", "prior_post_path",
                  "rank", "reason_code", "rationale"}
_ITEM_KEYS = {"candidate_id", "event_key", "title", "url", "canonical_url", "source", "snippet",
              "source_type", "lane", "discovered_via", "published_at", "raw_id",
              "evidence_type", "dedup", "prior_post_path", "rank", "reason_code", "rationale"}
_CANDIDATE_ID_RE = re.compile(r"^[0-9a-f]{20}$")


def validate_decisions(obj) -> list:
    errors = []
    if not isinstance(obj, dict):
        return ["root not a dict"]
    for key in ("date", "decisions", "generated_with"):
        if key not in obj:
            errors.append(f"missing root key: {key}")
    if not isinstance(obj.get("date"), str):
        errors.append("date not a string")
    if obj.get("generated_with") not in {"codex-exec", "local-empty"}:
        errors.append("bad generated_with")
    decisions = obj.get("decisions")
    if not isinstance(decisions, list):
        errors.append("decisions not a list")
        return errors
    for index, row in enumerate(decisions):
        if not isinstance(row, dict):
            errors.append(f"decision[{index}] not a dict")
            continue
        missing = _DECISION_KEYS - set(row)
        extra = set(row) - _DECISION_KEYS
        if missing:
            errors.append(f"decision[{index}] missing: {sorted(missing)}")
        if extra:
            errors.append(f"decision[{index}] unexpected: {sorted(extra)}")
        cid = row.get("candidate_id")
        if not isinstance(cid, str) or not _CANDIDATE_ID_RE.fullmatch(cid):
            errors.append(f"decision[{index}] bad candidate_id")
        decision = row.get("decision")
        dedup = row.get("dedup")
        reason = row.get("reason_code")
        if not isinstance(decision, str) or decision not in DECISION_VALUES:
            errors.append(f"decision[{index}] bad decision")
        if not isinstance(dedup, str) or dedup not in DEDUP_VALUES:
            errors.append(f"decision[{index}] bad dedup")
        if not isinstance(reason, str) or reason not in REASON_CODES:
            errors.append(f"decision[{index}] bad reason_code")
        rank = row.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1:
            errors.append(f"decision[{index}] rank not positive int")
        if not isinstance(row.get("rationale"), str):
            errors.append(f"decision[{index}] rationale not a string")
        prior = row.get("prior_post_path")
        if prior is not None and not isinstance(prior, str):
            errors.append(f"decision[{index}] prior_post_path not string or null")
        if decision == "select":
            if dedup not in {"new", "followup"} or reason != "selected":
                errors.append(f"decision[{index}] select requires new/followup and selected reason")
            if dedup == "followup" and not prior:
                errors.append(f"decision[{index}] followup requires prior_post_path")
        elif decision == "skip" and (dedup != "skip" or reason == "selected"):
            errors.append(f"decision[{index}] skip requires skip dedup and non-selected reason")
    return errors


def validate_decision_coverage(obj, candidates) -> list:
    errors = []
    expected_order = []
    expected = set()
    for candidate in candidates:
        cid = candidate.get("candidate_id") if isinstance(candidate, dict) else None
        if cid in expected:
            errors.append(f"duplicate candidate: {cid}")
        else:
            expected.add(cid)
            expected_order.append(cid)
    seen = set()
    for row in obj.get("decisions", []) if isinstance(obj, dict) else []:
        if not isinstance(row, dict):
            continue
        cid = row.get("candidate_id")
        if cid in seen:
            errors.append(f"duplicate decision: {cid}")
            continue
        seen.add(cid)
        if cid not in expected:
            errors.append(f"unexpected decision: {cid}")
    for cid in expected_order:
        if cid not in seen:
            errors.append(f"missing decision: {cid}")
    return errors


def materialize_selected(candidate, decision) -> dict:
    return {
        "candidate_id": candidate["candidate_id"],
        "event_key": candidate["candidate_id"],
        "title": candidate["title"],
        "snippet": candidate.get("snippet", ""),
        "url": candidate["url"],
        "canonical_url": candidate["canonical_url"],
        "source": candidate["source"],
        "source_type": candidate["source_type"],
        "lane": candidate["lane"],
        "discovered_via": candidate["discovered_via"],
        "published_at": candidate.get("published_at"),
        "raw_id": candidate.get("raw_id", ""),
        "evidence_type": candidate["source_type"],
        "dedup": decision["dedup"],
        "prior_post_path": decision["prior_post_path"],
        "rank": decision["rank"],
        "reason_code": decision["reason_code"],
        "rationale": decision["rationale"],
    }


def validate_selection(obj) -> list:
    errors = validate_decisions(obj)
    if not isinstance(obj, dict):
        return errors
    for key in ("items", "selected_count", "skipped_count"):
        if key not in obj:
            errors.append(f"missing root key: {key}")
    items = obj.get("items")
    if not isinstance(items, list):
        errors.append("items not a list")
        return errors
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"item[{index}] not a dict")
            continue
        missing = _ITEM_KEYS - set(item)
        if missing:
            errors.append(f"item[{index}] missing: {sorted(missing)}")
        if item.get("source_type") not in SOURCE_TYPES:
            errors.append(f"item[{index}] bad source_type")
        if item.get("evidence_type") != item.get("source_type"):
            errors.append(f"item[{index}] bad evidence_type")
        if item.get("lane") not in LANES:
            errors.append(f"item[{index}] bad lane")
        if item.get("dedup") not in {"new", "followup"}:
            errors.append(f"item[{index}] bad dedup")
        if item.get("dedup") == "followup" and not item.get("prior_post_path"):
            errors.append(f"item[{index}] followup requires prior_post_path")
        if not isinstance(item.get("rank"), int) or isinstance(item.get("rank"), bool):
            errors.append(f"item[{index}] rank not int")
        for field in ("candidate_id", "event_key", "url", "canonical_url"):
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"item[{index}] {field} not a non-empty string")
        if item.get("event_key") != item.get("candidate_id"):
            errors.append(f"item[{index}] event_key mismatch")
        for field in ("title", "snippet", "source", "discovered_via", "rationale", "reason_code"):
            if not isinstance(item.get(field), str):
                errors.append(f"item[{index}] {field} not a string")
    decisions = obj.get("decisions", []) if isinstance(obj.get("decisions"), list) else []
    selected_ids = [row.get("candidate_id") for row in decisions
                    if isinstance(row, dict) and row.get("decision") == "select"]
    item_ids = [item.get("candidate_id") for item in items if isinstance(item, dict)]
    if set(selected_ids) != set(item_ids) or len(selected_ids) != len(item_ids):
        errors.append("selected decisions do not match items")
    if obj.get("selected_count") != len(selected_ids):
        errors.append("selected_count mismatch")
    if obj.get("skipped_count") != len(decisions) - len(selected_ids):
        errors.append("skipped_count mismatch")
    return errors


EVIDENCE_LEVELS = {"confirmed", "short", "exclude"}


@dataclass
class FetchResult:
    event_key: str
    url: str
    source_type: str
    text: str
    evidence_level: str
    via: str
    fetch_ok: bool

    def to_dict(self):
        return asdict(self)


@dataclass
class GenerationResult:
    event_key: str
    title: str
    url: str
    source: str
    source_type: str
    evidence_level: str
    status: str
    post_path: Optional[str]
    slug: str
    rank: int
    rationale: str = ""
    error: Optional[str] = None

    def to_dict(self):
        return asdict(self)


REQUIRED_FRONTMATTER = {"title", "date", "tags", "source_url", "source_name",
                        "source_published_at", "source_lang", "source_type",
                        "evidence_level", "event_key"}
_FRONTMATTER = re.compile(
    r"\A\ufeff?---[ \t]*\r?\n(?P<header>.*?)(?:\r?\n)---[ \t]*(?:\r?\n|\Z)",
    re.S,
)


def split_frontmatter(markdown):
    if not isinstance(markdown, str):
        return None
    match = _FRONTMATTER.match(markdown)
    return (match.group("header"), markdown[match.end():]) if match else None


def parse_frontmatter(markdown) -> dict:
    parts = split_frontmatter(markdown)
    if parts is None:
        return {}
    keys = {}
    for line in parts[0].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            keys[key.strip()] = value.strip()
    return keys


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_frontmatter_strict(markdown) -> dict:
    # ponytail: stdlib-only parser for the front matter this project emits, not general YAML.
    output = {}
    for key, value in parse_frontmatter(markdown).items():
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            output[key] = [_unquote(item) for item in inner.split(",") if item.strip()] if inner else []
        else:
            output[key] = _unquote(value)
    return output


def validate_blog_output(markdown) -> list:
    if not isinstance(markdown, str) or not re.match(r"\A\ufeff?---[ \t]*(?:\r?\n|\Z)", markdown):
        return ["missing front matter block"]
    parts = split_frontmatter(markdown)
    if parts is None:
        return ["unterminated front matter"]
    keys = parse_frontmatter(markdown)
    body = parts[1]
    errors = [f"front matter missing: {key}" for key in REQUIRED_FRONTMATTER - set(keys)]
    unknown = set(keys) - REQUIRED_FRONTMATTER
    if unknown:
        errors.append(f"front matter unknown: {sorted(unknown)}")
    if keys.get("source_type") not in SOURCE_TYPES:
        errors.append("front matter bad source_type")
    if keys.get("evidence_level") not in {"confirmed", "short"}:
        errors.append("front matter bad evidence_level")
    if not body.strip():
        errors.append("empty body")
    return errors
