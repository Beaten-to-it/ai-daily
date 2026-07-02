from nbs.publish import extract_tldr
_FM = "---\ntitle: T\n---\n"

def test_extract_tldr_from_heading():
    md = _FM + "리드 문장.\n\n## TL;DR\n- 첫째 요점\n- 둘째 요점\n\n## 본문\n내용\n"
    out = extract_tldr(md)
    assert "첫째 요점" in out and "둘째 요점" in out and "본문" not in out and "리드 문장" not in out

def test_extract_tldr_from_bold_marker():
    md = _FM + "**TL;DR**\n- 요점 A\n- 요점 B\n\n본문\n"
    assert "요점 A" in extract_tldr(md)

def test_extract_tldr_fallback_first_paragraph():
    md = _FM + "첫 문단이 요약을 대신한다.\n\n둘째 문단.\n"
    out = extract_tldr(md)
    assert out.startswith("첫 문단") and "둘째 문단" not in out

from nbs.publish import decide
def _gen(results, date="2026-07-01"): return {"date": date, "status": "ok", "results": results}
def _res(ek, evidence, status):
    s=f"2026-07-01-{ek}"
    return {"event_key": ek, "evidence_level": evidence, "status": status, "slug": s,
            "url": f"https://x/{ek}", "post_path": f"posts/{s}.md", "title": "T", "source": "S"}

def test_decide_publish_when_evidence_and_ok():
    assert decide(_gen([_res("a","confirmed","ok"), _res("b","confirmed","ok"), _res("c","short","ok")]))[0] == "publish"

def test_decide_held_when_evidence_below_floor():
    assert decide(_gen([_res("a","confirmed","ok"), _res("b","exclude","excluded"), _res("c","exclude","excluded")]))[0] == "held"

def test_decide_held_when_all_generation_failed():
    d, reason = decide(_gen([_res("a","confirmed","failed"), _res("b","confirmed","failed"), _res("c","confirmed","failed")]))
    assert d == "held" and "generation" in reason.lower()

from pathlib import Path
from nbs.publish import check_completeness

def _write_post(staging, slug, ek, url, date="2026-07-01", ev="confirmed", tags="[ai]", body="## TL;DR\n- x\n본문\n"):
    (staging/"posts").mkdir(parents=True, exist_ok=True)
    (staging/"posts"/f"{slug}.md").write_text(
        f"---\ntitle: T\ndate: {date}\ntags: {tags}\nsource_url: {url}\n"
        f"source_lang: en\nsource_type: article\nevidence_level: {ev}\nevent_key: {ek}\n---\n{body}",
        encoding="utf-8")

def _write_news(staging, slugs, date="2026-07-01"):
    (staging/"news").mkdir(parents=True, exist_ok=True)
    links = "\n".join('- [T]({{< relref "/posts/%s.md" >}}) — h' % s for s in slugs)
    (staging/"news"/f"{date}.md").write_text(f"---\ntitle: N\n---\n{links}\n", encoding="utf-8")

def _okres(ek):
    s=f"2026-07-01-{ek}"
    return {"event_key":ek,"evidence_level":"confirmed","status":"ok","slug":s,
            "url":f"https://x/{ek}","post_path":f"posts/{s}.md","title":"T","source":"S"}

def test_completeness_passes_on_matching_set(tmp_path):
    staging=tmp_path/"staging"; gen={"date":"2026-07-01","results":[_okres("a"),_okres("b")]}
    for r in gen["results"]: _write_post(staging, r["slug"], r["event_key"], r["url"])
    _write_news(staging, [r["slug"] for r in gen["results"]])
    assert check_completeness(gen, staging) == []

def test_completeness_flags_missing_post_file(tmp_path):
    staging=tmp_path/"staging"; gen={"date":"2026-07-01","results":[_okres("a"),_okres("b")]}
    _write_post(staging,"2026-07-01-a","a","https://x/a"); _write_news(staging,["2026-07-01-a","2026-07-01-b"])
    assert any("2026-07-01-b" in e for e in check_completeness(gen, staging))

def test_completeness_flags_frontmatter_mismatch(tmp_path):
    staging=tmp_path/"staging"; gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")]}
    _write_post(staging,"2026-07-01-a","WRONG","https://x/a")
    _write_post(staging,"2026-07-01-b","b","https://x/b"); _write_post(staging,"2026-07-01-c","c","https://x/c")
    _write_news(staging,["2026-07-01-a","2026-07-01-b","2026-07-01-c"])
    assert any("event_key" in e for e in check_completeness(gen, staging))

def test_completeness_flags_scalar_or_empty_tags(tmp_path):
    staging=tmp_path/"staging"; gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")]}
    _write_post(staging,"2026-07-01-a","a","https://x/a", tags="ai")     # scalar, not a list
    _write_post(staging,"2026-07-01-b","b","https://x/b", tags="[]")     # empty list
    _write_post(staging,"2026-07-01-c","c","https://x/c")
    _write_news(staging,["2026-07-01-a","2026-07-01-b","2026-07-01-c"])
    errs = check_completeness(gen, staging)
    assert any("2026-07-01-a" in e and "tags" in e for e in errs)
    assert any("2026-07-01-b" in e and "tags" in e for e in errs)

def test_completeness_flags_empty_body(tmp_path):
    staging=tmp_path/"staging"; gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")]}
    _write_post(staging,"2026-07-01-a","a","https://x/a", body="")       # empty body
    _write_post(staging,"2026-07-01-b","b","https://x/b"); _write_post(staging,"2026-07-01-c","c","https://x/c")
    _write_news(staging,["2026-07-01-a","2026-07-01-b","2026-07-01-c"])
    assert any("2026-07-01-a" in e and "body" in e.lower() for e in check_completeness(gen, staging))

def test_completeness_flags_news_link_mismatch(tmp_path):
    staging=tmp_path/"staging"; gen={"date":"2026-07-01","results":[_okres("a"),_okres("b")]}
    for r in gen["results"]: _write_post(staging, r["slug"], r["event_key"], r["url"])
    _write_news(staging,["2026-07-01-a"])
    assert any("news" in e.lower() for e in check_completeness(gen, staging))

import subprocess
from nbs import publish, config

def _git_in(args, cwd): return subprocess.run(["git"]+args, cwd=str(cwd), capture_output=True, text=True)

def _init_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(publish, "ROOT", tmp_path)
    monkeypatch.setattr(publish, "run_dir", lambda date: tmp_path/"runs"/date)
    _git_in(["init","-q"], tmp_path); _git_in(["config","user.email","t@t"], tmp_path); _git_in(["config","user.name","t"], tmp_path)
    for d in ("posts","news","usecase"): (tmp_path/"content"/d).mkdir(parents=True)
    (tmp_path/"data").mkdir()
    (tmp_path/"content"/".keep").write_text("x")
    (tmp_path/".gitignore").write_text("runs/\n", encoding="utf-8")   # mirror prod: runs/ is scratch
    _git_in(["add","-A"], tmp_path); _git_in(["commit","-qm","init"], tmp_path)
    return tmp_path

def _gen2(date="2026-07-01"): return {"date":date, "results":[_okres("a"), _okres("b")]}

def _stage_posts(root, gen):
    staging=root/"runs"/gen["date"]/"staging"
    for r in gen["results"]: _write_post(staging, r["slug"], r["event_key"], r["url"], date=gen["date"])
    _write_news(staging, [r["slug"] for r in gen["results"]], date=gen["date"])
    (staging/"usecase").mkdir(parents=True, exist_ok=True)
    (staging/"usecase"/f"{gen['date']}.md").write_text("---\ntitle: U\n---\nu\n", encoding="utf-8")
    return staging

def test_promote_copies_and_deletes_stale(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    # a stale same-date post from a previous run, committed
    (root/"content"/"posts"/"2026-07-01-old.md").write_text("---\ntitle: O\n---\nx\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","stale"], root)
    gen=_gen2(); staging=_stage_posts(root, gen)
    touched = publish.promote(gen, staging)
    assert (root/"content"/"posts"/"2026-07-01-a.md").exists()
    assert not (root/"content"/"posts"/"2026-07-01-old.md").exists()   # stale deleted
    assert (root/"content"/"news"/"2026-07-01.md").exists() and (root/"content"/"usecase"/"2026-07-01.md").exists()

def test_promote_drops_stale_usecase_when_staging_absent(tmp_path, monkeypatch):
    # R2-#2: degraded rerun (no staging usecase) must remove a previously-published usecase
    root=_init_repo(tmp_path, monkeypatch)
    (root/"content"/"usecase"/"2026-07-01.md").write_text("---\ntitle: old U\n---\nx\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","old usecase"], root)
    gen=_gen2(); staging=_stage_posts(root, gen)
    (staging/"usecase"/"2026-07-01.md").unlink()          # simulate degraded: no staging usecase
    touched = publish.promote(gen, staging)
    assert not (root/"content"/"usecase"/"2026-07-01.md").exists()
    assert "content/usecase/2026-07-01.md" in touched

def test_preflight_detects_dirty_writeset(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    (root/"data"/"published.csv").write_text("dirty\n", encoding="utf-8")
    assert "data/published.csv" in publish.preflight_clean(["data/published.csv"])

def test_rollback_restores_and_deletes(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    (root/"content"/"posts"/"2026-07-01-old.md").write_text("orig\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","base"], root)
    # simulate a partial promote: overwrite tracked + create untracked, stage them
    (root/"content"/"posts"/"2026-07-01-old.md").write_text("CHANGED\n", encoding="utf-8")
    (root/"content"/"posts"/"2026-07-01-new.md").write_text("NEW\n", encoding="utf-8")
    _git_in(["add","-A"], root)
    publish.rollback(["content/posts/2026-07-01-old.md", "content/posts/2026-07-01-new.md"])
    assert (root/"content"/"posts"/"2026-07-01-old.md").read_text() == "orig\n"   # restored to HEAD
    assert not (root/"content"/"posts"/"2026-07-01-new.md").exists()              # untracked removed
    assert _git_in(["status","--porcelain"], root).stdout.strip() == ""           # index clean

def _render(outdir, date, slugs, usecase=False):
    for s in slugs:
        (Path(outdir)/"posts"/s).mkdir(parents=True); (Path(outdir)/"posts"/s/"index.html").write_text("x")
    (Path(outdir)/"news"/date).mkdir(parents=True)
    (Path(outdir)/"news"/date/"index.html").write_text("".join(f'<a href="/ai-daily/posts/{s}/">x</a>' for s in slugs))
    if usecase:
        (Path(outdir)/"usecase"/date).mkdir(parents=True); (Path(outdir)/"usecase"/date/"index.html").write_text("u")
    return 0

def test_build_verify_flags_missing_rendered_post(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a"]))  # b missing
    assert any("2026-07-01-b" in e for e in publish.build_verify(gen))

def test_build_verify_flags_missing_usecase_when_present(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    (root/"content"/"usecase"/"2026-07-01.md").write_text("---\ntitle: U\n---\nu\n", encoding="utf-8")
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a","2026-07-01-b"], usecase=False))
    assert any("usecase" in e.lower() for e in publish.build_verify(gen))

def test_build_verify_passes_when_all_rendered(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    (root/"content"/"usecase"/"2026-07-01.md").write_text("---\ntitle: U\n---\nu\n", encoding="utf-8")
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a","2026-07-01-b"], usecase=True))
    assert publish.build_verify(gen) == []

import pytest
def test_ledger_rows_fields(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    (root/"content"/"posts"/"2026-07-01-a.md").write_text(
        "---\ntitle: A\ndate: 2026-07-01\ntags: [ai, model]\nsource_url: https://x/a\n"
        "source_lang: en\nsource_type: article\nevidence_level: confirmed\nevent_key: a\n---\n## TL;DR\n- 요약 문장\n본문\n", encoding="utf-8")
    (root/"content"/"posts"/"2026-07-01-b.md").write_text(
        "---\ntitle: B\ndate: 2026-07-01\ntags: [x]\nsource_url: https://x/b\n"
        "source_lang: en\nsource_type: article\nevidence_level: confirmed\nevent_key: b\n---\n첫 문단.\n", encoding="utf-8")
    gen["results"][0]["title"]="A"; gen["results"][0]["source"]="OpenAI"
    rows = publish.ledger_rows(gen)
    ra = next(r for r in rows if r["event_key"]=="a")
    assert ra["canonical_key"]=="https://x/a" and "요약 문장" in ra["summary"] and ra["tags"]=="ai,model"
    assert ra["post_path"]=="posts/2026-07-01-a.md"
    assert next(r for r in rows if r["event_key"]=="b")["summary"].startswith("첫 문단")

def test_ledger_rows_raises_on_empty_summary(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen={"date":"2026-07-01","results":[_okres("a")]}
    (root/"content"/"posts"/"2026-07-01-a.md").write_text("---\ntitle: A\n---\n\n", encoding="utf-8")  # empty body
    with pytest.raises(ValueError):
        publish.ledger_rows(gen)

import json
def _stage_full(root, gen):
    d=root/"runs"/gen["date"]; _stage_posts(root, gen)
    (d/"generation.json").write_text(json.dumps(gen), encoding="utf-8"); return d

def test_run_held_when_evidence_low(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    gen={"date":"2026-07-01","results":[_res("a","confirmed","ok"), _res("b","exclude","excluded"), _res("c","exclude","excluded")]}
    _stage_full(root, gen)
    m=publish.run("2026-07-01")
    assert m["status"]=="held" and not (root/"content"/"news"/"2026-07-01.md").exists()
    assert (root/"runs"/"2026-07-01"/"publish.json").exists()

def test_run_publishes_and_writes_ledger_and_manifest(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a","2026-07-01-b","2026-07-01-c"], usecase=True))
    gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")]}
    _stage_full(root, gen)
    m=publish.run("2026-07-01")
    assert m["status"]=="published" and m["commit_sha"]
    assert (root/"content"/"news"/"2026-07-01.md").exists()
    led=(root/"data"/"published.csv").read_text(encoding="utf-8")
    assert "2026-07-01-a" in led and led.count("2026-07-01-a")==1
    # idempotent rerun -> still published, still one row
    m2=publish.run("2026-07-01")
    assert m2["status"]=="published"
    assert (root/"data"/"published.csv").read_text(encoding="utf-8").count("2026-07-01-a")==1

def test_run_degraded_publishes_without_usecase(tmp_path, monkeypatch):
    # §15: usecase optional — usecase_error set, no staging usecase file -> still publishes
    root=_init_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a","2026-07-01-b","2026-07-01-c"], usecase=False))
    gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")], "usecase_error":"boom"}
    d=root/"runs"/gen["date"]; staging=d/"staging"
    for r in gen["results"]: _write_post(staging, r["slug"], r["event_key"], r["url"])
    _write_news(staging, [r["slug"] for r in gen["results"]])       # NO usecase file
    (d/"generation.json").write_text(json.dumps(gen), encoding="utf-8")
    m=publish.run("2026-07-01")
    assert m["status"]=="published" and m["degraded"].get("usecase")
    assert not (root/"content"/"usecase"/"2026-07-01.md").exists()
    assert (root/"content"/"news"/"2026-07-01.md").exists()

def test_run_rolls_back_on_build_failure(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(publish, "_hugo_build", lambda o: 1)         # build fails
    gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")]}
    _stage_full(root, gen)
    m=publish.run("2026-07-01")
    assert m["status"]=="failed"
    assert not (root/"content"/"posts"/"2026-07-01-a.md").exists()   # rolled back
    assert _git_in(["status","--porcelain"], root).stdout.strip()==""  # clean tree/ledger
