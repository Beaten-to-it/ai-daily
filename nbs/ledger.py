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
