import json, pytest
from pathlib import Path
from nbs import stage
from nbs.models import FetchResult, GenerationResult

@pytest.fixture
def rundir(tmp_path, monkeypatch):
    # redirect run_dir so tests never touch the real runs/ tree
    monkeypatch.setattr(stage, "run_dir", lambda date: tmp_path / date)
    return lambda date: tmp_path / date

def _write_selection(rundir, date, n):
    d=rundir(date); d.mkdir(parents=True, exist_ok=True)
    items=[{"event_key":f"k{i}","title":f"T{i}","url":f"https://x/{i}",
            "source":"S","source_type":"article","evidence_type":"article",
            "dedup":"new","prior_post_path":None,"rank":i,"rationale":"r"} for i in range(n)]
    (d/"selection.json").write_text(json.dumps(
        {"date":date,"items":items,"selected_count":n,"skipped_count":0,
         "generated_with":"test"}), encoding="utf-8")

def _fake_fetch(item):
    return FetchResult(item["event_key"], item["url"], "article", "t"*50, "confirmed", "http", True)
def _fake_gen(items, fetched_map, date, **kw):
    res=[]
    for it in items:
        r=GenerationResult(event_key=it["event_key"], title=it["title"], url=it["url"],
            source=it["source"], source_type="article", evidence_level="confirmed",
            status="ok", post_path=f"posts/{date}-{it['event_key']}.md",
            slug=f"{date}-{it['event_key']}", rank=it["rank"], rationale="r")
        r._md=f"---\ntitle: {it['title']}\n---\nbody\n"
        res.append(r)
    return res

def test_stage_writes_staging_and_generationjson(rundir):
    date="2026-07-02"; _write_selection(rundir, date, 3)
    out=stage.run(date, fetch=_fake_fetch, generate=_fake_gen,
                  usecase=lambda results,d: "---\ntitle: U\n---\nu\n")
    d=rundir(date)
    assert (d/"staging"/"posts"/f"{date}-k0.md").exists()
    assert (d/"staging"/"news"/f"{date}.md").exists()
    assert (d/"staging"/"usecase"/f"{date}.md").exists()
    assert (d/"generation.json").exists()
    assert out["floor_failed"] is False and out["published_count"]==3

def test_stage_floor_failed_writes_no_news(rundir):
    date="2026-07-03"; _write_selection(rundir, date, 2)
    out=stage.run(date, fetch=_fake_fetch, generate=_fake_gen, usecase=lambda r,d:"x")
    d=rundir(date)
    assert out["floor_failed"] is True
    assert not (d/"staging"/"news"/f"{date}.md").exists()
    assert (d/"generation.json").exists()

def test_stage_rerun_clears_stale_staging(rundir):
    # success (3) then rerun same date below floor (2) must remove old news
    date="2026-07-05"
    _write_selection(rundir, date, 3)
    stage.run(date, fetch=_fake_fetch, generate=_fake_gen, usecase=lambda r,d:"---\nt\n---\nu\n")
    assert (rundir(date)/"staging"/"news"/f"{date}.md").exists()
    _write_selection(rundir, date, 2)
    stage.run(date, fetch=_fake_fetch, generate=_fake_gen, usecase=lambda r,d:"x")
    assert not (rundir(date)/"staging"/"news"/f"{date}.md").exists()

def test_stage_skips_when_zero_items(rundir):
    date="2026-07-04"; _write_selection(rundir, date, 0)
    out=stage.run(date, fetch=_fake_fetch, generate=_fake_gen, usecase=lambda r,d:"x")
    assert out["status"]=="skip-empty"

def test_stage_usecase_failure_is_isolated(rundir):
    # §5: a usecase claude -p failure must NOT abort the run — manifest + posts + news survive
    date="2026-07-06"; _write_selection(rundir, date, 3)
    def boom(results, d): raise ValueError("usecase output missing front matter")
    out=stage.run(date, fetch=_fake_fetch, generate=_fake_gen, usecase=boom)
    d=rundir(date)
    assert (d/"generation.json").exists()                       # manifest still written
    assert out["published_count"]==3 and out["floor_failed"] is False
    assert "front matter" in (out["usecase_error"] or "")       # failure recorded
    assert (d/"staging"/"posts"/f"{date}-k0.md").exists()       # posts survive
    assert (d/"staging"/"news"/f"{date}.md").exists()           # news survives
    assert not (d/"staging"/"usecase"/f"{date}.md").exists()    # usecase skipped
