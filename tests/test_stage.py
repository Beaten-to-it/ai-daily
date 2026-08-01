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
            status="ok", post_path=f"articles/{date}-{it['event_key']}.md",
            slug=f"{date}-{it['event_key']}", rank=it["rank"], rationale="r")
        r._md=f"---\ntitle: {it['title']}\n---\nbody\n"
        res.append(r)
    return res

def test_stage_writes_staging_and_generationjson(rundir):
    date="2026-07-02"; _write_selection(rundir, date, 3)
    out=stage.run(date, fetch=_fake_fetch, generate=_fake_gen,
                  guide=lambda results,d: "---\ntitle: U\n---\nu\n", executive=lambda r,d:None)
    d=rundir(date)
    assert (d/"staging"/"articles"/f"{date}-k0.md").exists()
    assert (d/"staging"/"daily"/f"{date}.md").exists()
    assert (d/"staging"/"guides"/f"{date}.md").exists()
    assert not (d/"staging"/"posts").exists()
    assert (d/"generation.json").exists()
    assert out["volume_status"] == "warning" and out["published_count"]==3
    assert out["target_count"] == 30 and out["target_met"] is False

def test_stage_warning_still_writes_daily(rundir):
    date="2026-07-03"; _write_selection(rundir, date, 2)
    out=stage.run(date, fetch=_fake_fetch, generate=_fake_gen, guide=lambda r,d:"x", executive=lambda r,d:None)
    d=rundir(date)
    assert out["volume_status"] == "warning"
    assert (d/"staging"/"daily"/f"{date}.md").exists()
    assert (d/"generation.json").exists()

def test_stage_zero_generated_writes_no_daily(rundir):
    date="2026-07-08"; _write_selection(rundir, date, 1)
    out=stage.run(date, fetch=_fake_fetch, generate=lambda items, fetched, day: [],
                  guide=lambda r,d:None, executive=lambda r,d:None)
    assert out["volume_status"] == "empty"
    assert not (rundir(date)/"staging"/"daily"/f"{date}.md").exists()

def test_stage_has_no_article_cap_and_records_target(rundir):
    date="2026-07-09"; _write_selection(rundir, date, 31)
    out=stage.run(date, fetch=_fake_fetch, generate=_fake_gen,
                  guide=lambda r,d:None, executive=lambda r,d:None)
    assert out["published_count"] == 31
    assert out["volume_status"] == "normal" and out["target_met"] is True
    assert len(list((rundir(date)/"staging"/"articles").glob("*.md"))) == 31

def test_stage_rerun_clears_stale_staging(rundir):
    # success (3) then rerun same date below floor (2) must remove old news
    date="2026-07-05"
    _write_selection(rundir, date, 3)
    stage.run(date, fetch=_fake_fetch, generate=_fake_gen, guide=lambda r,d:"---\nt\n---\nu\n", executive=lambda r,d:None)
    assert (rundir(date)/"staging"/"daily"/f"{date}.md").exists()
    _write_selection(rundir, date, 0)
    stage.run(date, fetch=_fake_fetch, generate=_fake_gen, guide=lambda r,d:"x", executive=lambda r,d:None)
    assert not (rundir(date)/"staging").exists()

def test_stage_skips_when_zero_items(rundir):
    date="2026-07-04"; _write_selection(rundir, date, 0)
    out=stage.run(date, fetch=_fake_fetch, generate=_fake_gen, guide=lambda r,d:"x", executive=lambda r,d:None)
    assert out["status"]=="skip-empty"
    assert out["volume_status"] == "empty"

def _gen_respecting_exclude(items, fetched_map, date, **kw):
    out=[]
    for it in items:
        ek=it["event_key"]; fr=fetched_map[ek]
        st="excluded" if fr.evidence_level=="exclude" else "ok"
        r=GenerationResult(event_key=ek, title=it["title"], url=it["url"], source="S",
            source_type="article", evidence_level=fr.evidence_level, status=st,
            post_path=(None if st!="ok" else f"articles/{date}-{ek}.md"),
            slug=f"{date}-{ek}", rank=it["rank"], rationale="r")
        if st=="ok": r._md=f"---\ntitle: {it['title']}\n---\nbody\n"
        out.append(r)
    return out

def test_stage_rejects_unsafe_event_key(rundir):
    # event_key with a path separator must be ISOLATED (excluded), never slugified/crash.
    date="2026-07-07"; d=rundir(date); d.mkdir(parents=True, exist_ok=True)
    def _it(ek,r): return {"event_key":ek,"title":"T","url":f"https://x/{r}","source":"S",
        "source_type":"article","evidence_type":"article","dedup":"new",
        "prior_post_path":None,"rank":r,"rationale":"r"}
    longkey="a"*200                                                  # charset-ok but > NAME_MAX slug
    items=[_it("good-1",1), _it("../evil",2), _it(longkey,3)]
    (d/"selection.json").write_text(json.dumps({"date":date,"items":items,
        "selected_count":3,"skipped_count":0,"generated_with":"test"}), encoding="utf-8")
    out=stage.run(date, fetch=_fake_fetch, generate=_gen_respecting_exclude, guide=lambda r,d:"x", executive=lambda r,d:None)
    status={r["event_key"]:r["status"] for r in out["results"]}
    assert status["good-1"]=="ok"                                    # valid item unaffected
    assert status["../evil"]=="excluded" and status[longkey]=="excluded"  # unsafe + overlong isolated
    assert not any("evil" in p.name for p in d.rglob("*") if p.is_file())  # no path-escape write
    assert (d/"generation.json").exists()                            # run did not crash before manifest

def test_stage_guide_failure_is_isolated(rundir):
    # §5: a usecase claude -p failure must NOT abort the run — manifest + posts + news survive
    date="2026-07-06"; _write_selection(rundir, date, 3)
    def boom(results, d): raise ValueError("guide output missing front matter")
    out=stage.run(date, fetch=_fake_fetch, generate=_fake_gen, guide=boom, executive=lambda r,d:None)
    d=rundir(date)
    assert (d/"generation.json").exists()                       # manifest still written
    assert out["published_count"]==3 and out["volume_status"] == "warning"
    assert "front matter" in (out["guide_error"] or "")
    assert (d/"staging"/"articles"/f"{date}-k0.md").exists()
    assert (d/"staging"/"daily"/f"{date}.md").exists()
    assert not (d/"staging"/"guides"/f"{date}.md").exists()


def test_stage_rejects_invalid_date_before_path_use(rundir, tmp_path):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        stage.run("../evil")
    assert not (tmp_path.parent / "evil").exists()


def test_stage_carries_source_health_warnings_into_generation(rundir):
    date="2026-08-01"; _write_selection(rundir, date, 0)
    (rundir(date)/"source_health.json").write_text(json.dumps([
        {"lane":"official","name":"feed","status":"ok","candidate_count":1,"elapsed_ms":2,"error":""},
        {"lane":"social","name":"x","status":"unconfigured","candidate_count":0,"elapsed_ms":0,"error":"missing"},
    ]), encoding="utf-8")
    out=stage.run(date)
    assert out["source_health_warnings"] == [{
        "lane":"social", "name":"x", "status":"unconfigured", "error":"missing"
    }]
