import argparse, json, re, shutil
from .config import run_dir
from . import fetch as fetch_mod
from . import generate as gen_mod
from . import assemble as asm
from .models import FetchResult

_EVENT_KEY_RE = re.compile(r"^[a-z0-9-]{1,100}$")   # bounded: slug goes in a filename (NAME_MAX 255)

def run(date, *, fetch=None, generate=None, usecase=None, ax=None):
    fetch = fetch or fetch_mod.fetch_item
    generate = generate or gen_mod.generate_all
    usecase = usecase or asm.build_usecase
    ax = ax or asm.build_ax
    d = run_dir(date)
    d.mkdir(parents=True, exist_ok=True)
    sel = json.loads((d/"selection.json").read_text(encoding="utf-8"))
    items = sel.get("items", [])

    staging = d/"staging"
    if staging.exists():
        shutil.rmtree(staging)               # idempotent rerun — no stale artifacts

    if not items:
        payload = {"date": date, "status": "skip-empty", "results": [],
                   "published_count": 0, "floor_failed": False, "usecase_error": None, "ax_error": None}
        (d/"generation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    fetched_map = {}
    (d/"fetched").mkdir(parents=True, exist_ok=True)
    for it in items:
        ek = it.get("event_key", "")
        st = it.get("source_type", "article")
        # event_key is LLM output and becomes a fetched filename + post slug/path. REJECT
        # (don't coerce) anything outside the slug charset: slugifying could map two
        # distinct keys onto one path -> silent overwrite. Isolate as excluded, no writes.
        # isinstance guard FIRST: schema allows `"event_key": null`, and _EVENT_KEY_RE.match(None)
        # raises TypeError HERE (outside the try) -> one bad field would abort the whole day.
        if not isinstance(ek, str) or not _EVENT_KEY_RE.match(ek):
            fetched_map[ek] = FetchResult(event_key=ek, url=it.get("url",""), source_type=st,
                text="", evidence_level="exclude", via="invalid-key", fetch_ok=False)
            continue
        try:                                     # §5: one item's fetch failure must not abort the run
            fr = fetch(it)
            (d/"fetched"/f"{ek}.txt").write_text(fr.text or "", encoding="utf-8")
        except Exception:
            fr = FetchResult(event_key=ek, url=it.get("url",""), source_type=st,
                text="", evidence_level="exclude", via="fetch-error", fetch_ok=False)
        fetched_map[ek] = fr

    results = generate(items, fetched_map, date)

    for sub in ("posts", "news", "usecase", "ax"):
        (staging/sub).mkdir(parents=True, exist_ok=True)
    for r in results:
        if r.status == "ok" and getattr(r, "_md", None):
            (staging/"posts"/f"{r.slug}.md").write_text(r._md, encoding="utf-8")

    floor_failed = not asm.floor_ok(results)
    usecase_error = None
    ax_error = None
    if not floor_failed:
        (staging/"news"/f"{date}.md").write_text(asm.build_news_index(results, date), encoding="utf-8")
        try:
            # §5 isolation: a usecase claude -p failure (bad output/timeout) must not abort
            # the whole run and lose the manifest + all successfully staged posts.
            uc = usecase(results, date)
            if uc:
                (staging/"usecase"/f"{date}.md").write_text(uc, encoding="utf-8")
        except Exception as e:
            usecase_error = str(e)[:200]
        try:
            # §5 isolation: ax failure (bad output/timeout/grounding-gate reject) must not abort.
            # Gate rejection (ungrounded) is a normal "no AX page today" outcome.
            ax_md = ax(results, date)
            if ax_md:
                (staging/"ax"/f"{date}.md").write_text(ax_md, encoding="utf-8")
        except Exception as e:
            ax_error = str(e)[:200]

    payload = {"date": date, "status": "ok",
               "results": [r.to_dict() for r in results],
               "published_count": len(asm.publishable(results)),
               "floor_failed": floor_failed, "usecase_error": usecase_error, "ax_error": ax_error}
    (d/"generation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--date", required=True); a = ap.parse_args()
    out = run(a.date)
    print(f"[{out['status']}] published={out['published_count']} floor_failed={out['floor_failed']} "
          f"-> runs/{a.date}/staging/ + generation.json")

if __name__ == "__main__": main()
