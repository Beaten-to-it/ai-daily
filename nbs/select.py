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
    # --tools "" : empty tool set = no tool access (§10). select only needs text->JSON
    # generation over untrusted RSS/X/Reddit candidate text; --allowedTools "" does NOT
    # restrict (see nbs/generate.py, task-4-report.md Step 0) -- --tools "" is the flag
    # that actually zeroes tool_use.
    r=subprocess.run(["claude","-p","--tools",""], input=text, capture_output=True, text=True, timeout=timeout)
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
    # recount drops dedup:"skip" rows before membership check; skipped_count counts only explicit dedup:"skip" items
    recount(obj)
    cand_urls={canonicalize_url(c["url"]) for c in cands}
    # source/source_type are the LLM's editorial classification (e.g. arXiv-via-HN => paper); grounded by URL membership, intentionally not overwritten from candidate.
    errs=validate_against_candidates(obj, cand_urls)
    if errs: raise ValueError("selection membership/uniqueness invalid: "+"; ".join(errs[:8]))
    (run_dir(date)/"selection.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    return obj

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--date", required=True); a=ap.parse_args()
    obj=select(a.date)
    print(f"selected {obj['selected_count']} (skipped {obj['skipped_count']}) -> runs/{a.date}/selection.json")

if __name__ == "__main__": main()
