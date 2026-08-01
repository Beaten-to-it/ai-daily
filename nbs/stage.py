import argparse
import json
import re
import shutil

from . import assemble as asm
from . import fetch as fetch_mod
from . import generate as gen_mod
from .config import run_dir
from .models import FetchResult


_EVENT_KEY_RE = re.compile(r"^[a-z0-9-]{1,100}$")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _source_health_warnings(directory):
    path = directory / "source_health.json"
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [{"lane": "unknown", "name": "source_health", "status": "failed",
                 "error": "source_health.json unreadable"}]
    return [
        {key: row.get(key, "") for key in ("lane", "name", "status", "error")}
        for row in rows if isinstance(row, dict) and row.get("status") in {"unconfigured", "degraded", "failed"}
    ]


def run(date, *, fetch=None, generate=None, guide=None, executive=None):
    if not _DATE_RE.fullmatch(date or ""):
        raise ValueError("date must be YYYY-MM-DD")
    fetch = fetch or fetch_mod.fetch_item
    generate = generate or gen_mod.generate_all
    guide = guide or asm.build_guide
    executive = executive or asm.build_executive
    directory = run_dir(date)
    directory.mkdir(parents=True, exist_ok=True)
    selection = json.loads((directory / "selection.json").read_text(encoding="utf-8"))
    items = selection.get("items", [])
    source_health_warnings = _source_health_warnings(directory)

    staging = directory / "staging"
    if staging.exists():
        shutil.rmtree(staging)

    if not items:
        payload = {
            "date": date,
            "status": "skip-empty",
            "results": [],
            "published_count": 0,
            "volume_status": "empty",
            "target_count": asm.TARGET_ARTICLES,
            "target_met": False,
            "guide_error": None,
            "executive_error": None,
            "source_health_warnings": source_health_warnings,
        }
        (directory / "generation.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return payload

    fetched_map = {}
    (directory / "fetched").mkdir(parents=True, exist_ok=True)
    for item in items:
        event_key = item.get("event_key", "")
        source_type = item.get("source_type", "article")
        if not isinstance(event_key, str) or not _EVENT_KEY_RE.match(event_key):
            try:
                fetched_map[event_key] = FetchResult(
                    event_key=event_key,
                    url=item.get("url", ""),
                    source_type=source_type,
                    text="",
                    evidence_level="exclude",
                    via="invalid-key",
                    fetch_ok=False,
                )
            except TypeError:
                pass
            continue
        try:
            fetched = fetch(item)
            (directory / "fetched" / f"{event_key}.txt").write_text(
                fetched.text or "", encoding="utf-8"
            )
        except Exception:
            fetched = FetchResult(
                event_key=event_key,
                url=item.get("url", ""),
                source_type=source_type,
                text="",
                evidence_level="exclude",
                via="fetch-error",
                fetch_ok=False,
            )
        fetched_map[event_key] = fetched

    results = generate(items, fetched_map, date)
    for subdirectory in ("articles", "daily", "guides", "executive"):
        (staging / subdirectory).mkdir(parents=True, exist_ok=True)
    for result in results:
        if result.status == "ok" and getattr(result, "_md", None):
            (staging / "articles" / f"{result.slug}.md").write_text(
                result._md, encoding="utf-8"
            )

    published_count = len(asm.publishable(results))
    status = asm.volume_status(published_count)
    guide_error = None
    executive_error = None
    if published_count:
        (staging / "daily" / f"{date}.md").write_text(
            asm.build_daily(results, date), encoding="utf-8"
        )
        try:
            guide_markdown = guide(results, date)
            if guide_markdown:
                (staging / "guides" / f"{date}.md").write_text(
                    guide_markdown, encoding="utf-8"
                )
        except Exception as error:
            guide_error = str(error)[:200]
        try:
            executive_markdown = executive(results, date)
            if executive_markdown:
                (staging / "executive" / f"{date}.md").write_text(
                    executive_markdown, encoding="utf-8"
                )
        except Exception as error:
            executive_error = str(error)[:200]

    payload = {
        "date": date,
        "status": "ok",
        "results": [result.to_dict() for result in results],
        "published_count": published_count,
        "volume_status": status,
        "target_count": asm.TARGET_ARTICLES,
        "target_met": published_count >= asm.TARGET_ARTICLES,
        "guide_error": guide_error,
        "executive_error": executive_error,
        "source_health_warnings": source_health_warnings,
    }
    (directory / "generation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    output = run(args.date)
    print(
        f"[{output['status']}] published={output['published_count']} "
        f"volume={output['volume_status']} -> runs/{args.date}/staging/ + generation.json"
    )


if __name__ == "__main__":
    main()
