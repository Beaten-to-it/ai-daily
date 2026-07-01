import argparse, json, shutil
from .config import run_dir
from . import fetch as fetch_mod
from . import generate as gen_mod
from . import assemble as asm

def run(date, *, fetch=None, generate=None, usecase=None):
    fetch = fetch or fetch_mod.fetch_item
    generate = generate or gen_mod.generate_all
    usecase = usecase or asm.build_usecase
    d = run_dir(date)
    d.mkdir(parents=True, exist_ok=True)
    sel = json.loads((d/"selection.json").read_text(encoding="utf-8"))
    items = sel.get("items", [])

    staging = d/"staging"
    if staging.exists():
        shutil.rmtree(staging)               # idempotent rerun — no stale artifacts

    if not items:
        payload = {"date": date, "status": "skip-empty", "results": [],
                   "published_count": 0, "floor_failed": False}
        (d/"generation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    fetched_map = {}
    (d/"fetched").mkdir(parents=True, exist_ok=True)
    for it in items:
        fr = fetch(it)
        fetched_map[it["event_key"]] = fr
        (d/"fetched"/f"{it['event_key']}.txt").write_text(fr.text or "", encoding="utf-8")

    results = generate(items, fetched_map, date)

    for sub in ("posts", "news", "usecase"):
        (staging/sub).mkdir(parents=True, exist_ok=True)
    for r in results:
        if r.status == "ok" and getattr(r, "_md", None):
            (staging/"posts"/f"{r.slug}.md").write_text(r._md, encoding="utf-8")

    floor_failed = not asm.floor_ok(results)
    if not floor_failed:
        (staging/"news"/f"{date}.md").write_text(asm.build_news_index(results, date), encoding="utf-8")
        uc = usecase(results, date)
        if uc:
            (staging/"usecase"/f"{date}.md").write_text(uc, encoding="utf-8")

    payload = {"date": date, "status": "ok",
               "results": [r.to_dict() for r in results],
               "published_count": len(asm.publishable(results)),
               "floor_failed": floor_failed}
    (d/"generation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--date", required=True); a = ap.parse_args()
    out = run(a.date)
    print(f"[{out['status']}] published={out['published_count']} floor_failed={out['floor_failed']} "
          f"-> runs/{a.date}/staging/ + generation.json")

if __name__ == "__main__": main()
