import subprocess

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
            "url": f"https://x/{ek}", "post_path": f"articles/{s}.md", "title": "T", "source": "S",
            "source_type": "article"}

def test_decide_publish_when_evidence_and_ok():
    assert decide(_gen([_res("a","confirmed","ok"), _res("b","confirmed","ok"), _res("c","short","ok")]))[0] == "publish"

def test_decide_publishes_one_verified_article_with_warning_policy():
    assert decide(_gen([_res("a","confirmed","ok"), _res("b","exclude","excluded"), _res("c","exclude","excluded")]))[0] == "publish"

def test_decide_volume_boundaries():
    for count in (1, 9, 10, 30):
        decision, reason = decide(_gen([_res(str(i), "confirmed", "ok") for i in range(count)]))
        assert decision == "publish"
        assert ("warning" in reason) is (count < 10)
    assert decide(_gen([]))[0] == "held"

def test_source_health_warning_is_recorded_but_does_not_block():
    warning = [{"lane":"social", "name":"x", "status":"unconfigured", "error":"missing"}]
    gen = _gen([_res("a", "confirmed", "ok")])
    gen["source_health_warnings"] = warning
    assert decide(gen)[0] == "publish"
    assert publish._degraded(gen)["source_health"] == warning

def test_date_writeset_uses_new_routes(tmp_path, monkeypatch):
    from nbs import publish
    monkeypatch.setattr(publish, "ROOT", tmp_path)
    (tmp_path / "content" / "articles").mkdir(parents=True)
    monkeypatch.setattr(publish, "_git", lambda args, timeout=None: subprocess.CompletedProcess(args, 0, "", ""))
    gen = {"date": "2026-08-01", "results": [{"status": "ok", "slug": "2026-08-01-a"}]}
    paths = publish.date_writeset(gen)
    assert "content/articles/2026-08-01-a.md" in paths
    assert "content/daily/2026-08-01.md" in paths
    assert "content/executive/2026-08-01.md" in paths
    assert "content/guides/2026-08-01.md" in paths
    assert all("content/news/" not in path and "content/posts/" not in path for path in paths)

def test_decide_held_when_all_generation_failed():
    d, reason = decide(_gen([_res("a","confirmed","failed"), _res("b","confirmed","failed"), _res("c","confirmed","failed")]))
    assert d == "held" and "generation" in reason.lower()

from pathlib import Path
from nbs.publish import check_completeness

def _write_post(staging, slug, ek, url, date="2026-07-01", ev="confirmed", tags="[ai]", body="## TL;DR\n- x\n본문\n"):
    (staging/"articles").mkdir(parents=True, exist_ok=True)
    (staging/"articles"/f"{slug}.md").write_text(
        f"---\ntitle: T\ndate: {date}\ntags: {tags}\nsource_url: {url}\n"
        f"source_name: S\nsource_published_at: 2026-07-01T00:00:00+00:00\n"
        f"source_lang: en\nsource_type: article\nevidence_level: {ev}\nevent_key: {ek}\n---\n{body}",
        encoding="utf-8")

def _write_news(staging, slugs, date="2026-07-01"):
    (staging/"daily").mkdir(parents=True, exist_ok=True)
    links = "\n".join('- [T]({{< relref "/articles/%s.md" >}}) — h' % s for s in slugs)
    (staging/"daily"/f"{date}.md").write_text(f"---\ntitle: N\n---\n{links}\n", encoding="utf-8")

def _okres(ek):
    s=f"2026-07-01-{ek}"
    return {"event_key":ek,"evidence_level":"confirmed","status":"ok","slug":s,
            "url":f"https://x/{ek}","post_path":f"articles/{s}.md","title":"T","source":"S",
            "source_type":"article"}

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

def test_completeness_flags_daily_link_mismatch(tmp_path):
    staging=tmp_path/"staging"; gen={"date":"2026-07-01","results":[_okres("a"),_okres("b")]}
    for r in gen["results"]: _write_post(staging, r["slug"], r["event_key"], r["url"])
    _write_news(staging,["2026-07-01-a"])
    assert any("daily" in e.lower() for e in check_completeness(gen, staging))

def test_completeness_rejects_unsafe_slugs(tmp_path):
    # fullmatch charset guard: traversal, slash, trailing newline, uppercase, empty, underscore
    for i, bad in enumerate(["../evil", "a/b", "evil\n", "UPPER", "", "under_score"]):
        gen={"date":"2026-07-01","results":[{"event_key":"a","evidence_level":"confirmed",
             "status":"ok","slug":bad,"url":"https://x/a","post_path":f"articles/{bad}.md",
             "title":"T","source":"S"}]}
        assert any("slug" in e for e in check_completeness(gen, tmp_path/f"s{i}")), f"not rejected: {bad!r}"

import subprocess
from nbs import publish, config

def _git_in(args, cwd): return subprocess.run(["git"]+args, cwd=str(cwd), capture_output=True, text=True)

def _init_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(publish, "ROOT", tmp_path)
    monkeypatch.setattr(publish, "run_dir", lambda date: tmp_path/"runs"/date)
    _git_in(["init","-q"], tmp_path); _git_in(["config","user.email","t@t"], tmp_path); _git_in(["config","user.name","t"], tmp_path)
    for d in ("articles","daily","guides","executive"): (tmp_path/"content"/d).mkdir(parents=True)
    (tmp_path/"data").mkdir()
    (tmp_path/"content"/".keep").write_text("x")
    (tmp_path/".gitignore").write_text("runs/\n", encoding="utf-8")   # mirror prod: runs/ is scratch
    _git_in(["add","-A"], tmp_path); _git_in(["commit","-qm","init"], tmp_path)
    _git_in(["branch", "-M", "main"], tmp_path)
    return tmp_path

def _gen2(date="2026-07-01"): return {"date":date, "results":[_okres("a"), _okres("b")]}

def _stage_posts(root, gen):
    staging=root/"runs"/gen["date"]/"staging"
    ok = [r for r in gen["results"] if r["status"] == "ok"]
    for r in ok: _write_post(staging, r["slug"], r["event_key"], r["url"], date=gen["date"])
    _write_news(staging, [r["slug"] for r in ok], date=gen["date"])
    (staging/"guides").mkdir(parents=True, exist_ok=True)
    (staging/"guides"/f"{gen['date']}.md").write_text("---\ntitle: U\n---\nu\n", encoding="utf-8")
    return staging

def test_promote_copies_and_deletes_stale(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    # a stale same-date post from a previous run, committed
    (root/"content"/"articles"/"2026-07-01-old.md").write_text("---\ntitle: O\n---\nx\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","stale"], root)
    gen=_gen2(); staging=_stage_posts(root, gen)
    touched = publish.promote(gen, staging)
    assert (root/"content"/"articles"/"2026-07-01-a.md").exists()
    assert not (root/"content"/"articles"/"2026-07-01-old.md").exists()   # stale deleted
    assert (root/"content"/"daily"/"2026-07-01.md").exists() and (root/"content"/"guides"/"2026-07-01.md").exists()

def test_promote_preserves_legacy_posts_and_news(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    legacy_post=root/"content"/"posts"/"2026-07-01-legacy.md"
    legacy_news=root/"content"/"news"/"2026-07-01.md"
    legacy_post.parent.mkdir(); legacy_news.parent.mkdir()
    legacy_post.write_text("legacy post\n", encoding="utf-8")
    legacy_news.write_text("legacy news\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","legacy"], root)
    gen=_gen2(); staging=_stage_posts(root, gen)
    touched=publish.promote(gen, staging)
    assert legacy_post.read_text(encoding="utf-8") == "legacy post\n"
    assert legacy_news.read_text(encoding="utf-8") == "legacy news\n"
    assert all(not path.startswith(("content/posts/", "content/news/")) for path in touched)

def test_promote_drops_stale_guide_when_staging_absent(tmp_path, monkeypatch):
    # Degraded rerun (no staged guide) removes the prior guide for that date.
    root=_init_repo(tmp_path, monkeypatch)
    (root/"content"/"guides"/"2026-07-01.md").write_text("---\ntitle: old U\n---\nx\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","old guide"], root)
    gen=_gen2(); staging=_stage_posts(root, gen)
    (staging/"guides"/"2026-07-01.md").unlink()
    touched = publish.promote(gen, staging)
    assert not (root/"content"/"guides"/"2026-07-01.md").exists()
    assert "content/guides/2026-07-01.md" in touched

def test_preflight_detects_dirty_writeset(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    (root/"data"/"published.csv").write_text("dirty\n", encoding="utf-8")
    assert "data/published.csv" in publish.preflight_clean(["data/published.csv"])

def test_rollback_restores_and_deletes(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    (root/"content"/"articles"/"2026-07-01-old.md").write_text("orig\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","base"], root)
    # simulate a partial promote: overwrite tracked + create untracked, stage them
    (root/"content"/"articles"/"2026-07-01-old.md").write_text("CHANGED\n", encoding="utf-8")
    (root/"content"/"articles"/"2026-07-01-new.md").write_text("NEW\n", encoding="utf-8")
    _git_in(["add","-A"], root)
    publish.rollback(["content/articles/2026-07-01-old.md", "content/articles/2026-07-01-new.md"])
    assert (root/"content"/"articles"/"2026-07-01-old.md").read_text() == "orig\n"   # restored to HEAD
    assert not (root/"content"/"articles"/"2026-07-01-new.md").exists()              # untracked removed
    assert _git_in(["status","--porcelain"], root).stdout.strip() == ""           # index clean

def _render(outdir, date, slugs, guide=False):
    for s in slugs:
        (Path(outdir)/"articles"/s).mkdir(parents=True); (Path(outdir)/"articles"/s/"index.html").write_text("x")
    (Path(outdir)/"daily"/date).mkdir(parents=True)
    (Path(outdir)/"daily"/date/"index.html").write_text("".join(f'<a href="/ai-daily/articles/{s}/">x</a>' for s in slugs))
    if guide:
        (Path(outdir)/"guides"/date).mkdir(parents=True); (Path(outdir)/"guides"/date/"index.html").write_text("u")
    (Path(outdir)/"index.xml").write_text(
        f"<rss><item><link>https://example.test/ai-daily/daily/{date}/</link></item></rss>"
    )
    return 0

def test_build_verify_flags_missing_rendered_post(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a"]))  # b missing
    assert any("2026-07-01-b" in e for e in publish.build_verify(gen))

def test_build_verify_flags_missing_guide_when_present(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    (root/"content"/"guides"/"2026-07-01.md").write_text("---\ntitle: U\n---\nu\n", encoding="utf-8")
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a","2026-07-01-b"], guide=False))
    assert any("guide" in e.lower() for e in publish.build_verify(gen))

def test_build_verify_passes_when_all_rendered(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    (root/"content"/"guides"/"2026-07-01.md").write_text("---\ntitle: U\n---\nu\n", encoding="utf-8")
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a","2026-07-01-b"], guide=True))
    assert publish.build_verify(gen) == []


def test_build_verify_passes_staging_content_directory_to_hugo(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    staging = root / "runs" / "2026-07-01" / "staging"
    (staging / "guides").mkdir(parents=True, exist_ok=True)
    (staging / "guides" / "2026-07-01.md").write_text("---\ntitle: U\n---\nu\n")
    seen = {}
    def build(outdir, content_dir=None):
        seen["content_dir"] = content_dir
        return _render(outdir, "2026-07-01", ["2026-07-01-a", "2026-07-01-b"], guide=True)
    monkeypatch.setattr(publish, "_hugo_build", build)
    assert publish.build_verify(gen, content_dir=staging) == []
    assert seen["content_dir"] == staging


def test_build_verify_rejects_non_daily_page_in_home_rss(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    def build(outdir):
        _render(outdir, "2026-07-01", ["2026-07-01-a", "2026-07-01-b"], guide=True)
        (Path(outdir) / "index.xml").write_text(
            "<rss><item><link>https://example.test/ai-daily/articles/2026-07-01-a/</link></item></rss>"
        )
        return 0
    monkeypatch.setattr(publish, "_hugo_build", build)
    assert any("RSS" in error for error in publish.build_verify(gen))


def test_build_verify_ignores_article_url_in_daily_rss_description(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    def build(outdir):
        _render(outdir, "2026-07-01", ["2026-07-01-a", "2026-07-01-b"], guide=True)
        (Path(outdir) / "index.xml").write_text(
            "<rss><channel><item>"
            "<link>https://example.test/ai-daily/daily/2026-07-01/</link>"
            "<guid>https://example.test/ai-daily/daily/2026-07-01/</guid>"
            "<description>관련 링크: https://example.test/ai-daily/articles/2026-07-01-a/</description>"
            "</item></channel></rss>"
        )
        return 0
    monkeypatch.setattr(publish, "_hugo_build", build)
    assert publish.build_verify(gen) == []

import pytest
def test_ledger_rows_fields(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen=_gen2()
    (root/"content"/"articles"/"2026-07-01-a.md").write_text(
        "---\ntitle: A\ndate: 2026-07-01\ntags: [ai, model]\nsource_url: https://x/a\n"
        "source_lang: en\nsource_type: article\nevidence_level: confirmed\nevent_key: a\n---\n## TL;DR\n- 요약 문장\n본문\n", encoding="utf-8")
    (root/"content"/"articles"/"2026-07-01-b.md").write_text(
        "---\ntitle: B\ndate: 2026-07-01\ntags: [x]\nsource_url: https://x/b\n"
        "source_lang: en\nsource_type: article\nevidence_level: confirmed\nevent_key: b\n---\n첫 문단.\n", encoding="utf-8")
    gen["results"][0]["title"]="A"; gen["results"][0]["source"]="OpenAI"
    rows = publish.ledger_rows(gen)
    ra = next(r for r in rows if r["event_key"]=="a")
    assert ra["canonical_key"]=="https://x/a" and "요약 문장" in ra["summary"] and ra["tags"]=="ai,model"
    assert ra["post_path"]=="articles/2026-07-01-a.md"
    assert next(r for r in rows if r["event_key"]=="b")["summary"].startswith("첫 문단")

def test_ledger_rows_raises_on_empty_summary(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); gen={"date":"2026-07-01","results":[_okres("a")]}
    (root/"content"/"articles"/"2026-07-01-a.md").write_text("---\ntitle: A\n---\n\n", encoding="utf-8")  # empty body
    with pytest.raises(ValueError):
        publish.ledger_rows(gen)

import json
def _stage_full(root, gen):
    d=root/"runs"/gen["date"]; _stage_posts(root, gen)
    (d/"generation.json").write_text(json.dumps(gen), encoding="utf-8"); return d

def test_run_publishes_low_volume_with_warning(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    gen={"date":"2026-07-01","results":[_res("a","confirmed","ok"), _res("b","exclude","excluded"), _res("c","exclude","excluded")]}
    _stage_full(root, gen)
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a"], guide=True))
    m=publish.run("2026-07-01")
    assert m["status"]=="published" and (root/"content"/"daily"/"2026-07-01.md").exists(), m
    assert m["volume_status"]=="warning" and m["degraded"]["article_volume"]=="warning"
    assert (root/"runs"/"2026-07-01"/"publish.json").exists()


def test_run_rejects_non_main_before_promote(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    _git_in(["checkout", "-q", "-b", "feature"], root)
    gen={"date":"2026-07-01","results":[_okres("a")]}
    _stage_full(root, gen)
    m=publish.run("2026-07-01")
    assert m["status"] == "failed" and "main branch" in m["reason"]
    assert not (root/"content"/"daily"/"2026-07-01.md").exists()


def test_hugo_build_timeout_is_bounded(monkeypatch, tmp_path):
    seen = {}
    def timeout(*args, **kwargs):
        seen.update(kwargs)
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
    monkeypatch.setattr(publish.subprocess, "run", timeout)
    assert publish._hugo_build(str(tmp_path / "public")) == 124
    assert seen["timeout"] == publish._HUGO_TIMEOUT

def test_run_publishes_and_writes_ledger_and_manifest(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a","2026-07-01-b","2026-07-01-c"], guide=True))
    gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")]}
    _stage_full(root, gen)
    m=publish.run("2026-07-01")
    assert m["status"]=="published" and m["commit_sha"]
    assert (root/"content"/"daily"/"2026-07-01.md").exists()
    led=(root/"data"/"published.csv").read_text(encoding="utf-8")
    assert "2026-07-01-a" in led and led.count("2026-07-01-a")==1
    # idempotent rerun -> still published, still one row, NO new commit (HEAD unchanged)
    head=_git_in(["rev-parse","HEAD"], root).stdout.strip()
    m2=publish.run("2026-07-01")
    assert m2["status"]=="published"
    assert (root/"data"/"published.csv").read_text(encoding="utf-8").count("2026-07-01-a")==1
    assert _git_in(["rev-parse","HEAD"], root).stdout.strip()==head and m2["commit_sha"]==head

def test_run_degraded_publishes_without_guide(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(publish, "_hugo_build", lambda o: _render(o, "2026-07-01", ["2026-07-01-a","2026-07-01-b","2026-07-01-c"], guide=False))
    gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")], "guide_error":"boom"}
    d=root/"runs"/gen["date"]; staging=d/"staging"
    for r in gen["results"]: _write_post(staging, r["slug"], r["event_key"], r["url"])
    _write_news(staging, [r["slug"] for r in gen["results"]])
    (d/"generation.json").write_text(json.dumps(gen), encoding="utf-8")
    m=publish.run("2026-07-01")
    assert m["status"]=="published" and m["degraded"].get("guide")
    assert not (root/"content"/"guides"/"2026-07-01.md").exists()
    assert (root/"content"/"daily"/"2026-07-01.md").exists()

def test_run_rolls_back_on_build_failure(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(publish, "_hugo_build", lambda o: 1)         # build fails
    gen={"date":"2026-07-01","results":[_okres("a"),_okres("b"),_okres("c")]}
    _stage_full(root, gen)
    m=publish.run("2026-07-01")
    assert m["status"]=="failed"
    assert not (root/"content"/"articles"/"2026-07-01-a.md").exists()   # rolled back
    assert _git_in(["status","--porcelain"], root).stdout.strip()==""  # clean tree/ledger

def _okresd(ek, date):
    s=f"{date}-{ek}"
    return {"event_key":ek,"evidence_level":"confirmed","status":"ok","slug":s,
            "url":f"https://x/{date}/{ek}","post_path":f"articles/{s}.md","title":"T","source":"S",
            "source_type":"article"}

def test_run_rerun_older_date_no_spurious_commit(tmp_path, monkeypatch):
    # Codex R1 MAJOR: rerunning an OLDER published day must be a no-op — the ledger must not
    # reorder rows (reorder = CSV diff = spurious commit).
    root=_init_repo(tmp_path, monkeypatch)
    def _mk(date): return {"date":date, "results":[_okresd("a",date),_okresd("b",date),_okresd("c",date)]}
    def _stub(date): return lambda o: _render(o, date, [f"{date}-{k}" for k in "abc"], guide=True)
    g1=_mk("2026-07-01"); _stage_full(root, g1)
    monkeypatch.setattr(publish, "_hugo_build", _stub("2026-07-01"))
    assert publish.run("2026-07-01")["status"]=="published"
    g2=_mk("2026-07-02"); _stage_full(root, g2)
    monkeypatch.setattr(publish, "_hugo_build", _stub("2026-07-02"))
    assert publish.run("2026-07-02")["status"]=="published"
    head=_git_in(["rev-parse","HEAD"], root).stdout.strip()
    monkeypatch.setattr(publish, "_hugo_build", _stub("2026-07-01"))   # rerun the OLDER day
    m=publish.run("2026-07-01")
    assert m["status"]=="published"
    assert _git_in(["rev-parse","HEAD"], root).stdout.strip()==head and m["commit_sha"]==head  # no new commit
    # ledger stays date-ordered: 07-01 rows before 07-02 rows
    led=(root/"data"/"published.csv").read_text(encoding="utf-8")
    assert led.index("2026-07-01-a") < led.index("2026-07-02-a")

def test_run_rejects_unsafe_slug(tmp_path, monkeypatch):
    # Codex R1 BLOCK: a traversal slug from generation.json must be rejected at the
    # completeness gate (before any promote/rollback), leaving the tree untouched.
    root=_init_repo(tmp_path, monkeypatch)
    evil={"event_key":"a","evidence_level":"confirmed","status":"ok","slug":"../evil",
          "url":"https://x/a","post_path":"articles/../evil.md","title":"T","source":"S","source_type":"article"}
    gen={"date":"2026-07-01","results":[evil, _okres("b"), _okres("c")]}
    d=root/"runs"/"2026-07-01"; staging=d/"staging"
    _write_post(staging,"2026-07-01-b","b","https://x/b"); _write_post(staging,"2026-07-01-c","c","https://x/c")
    _write_news(staging,["2026-07-01-b","2026-07-01-c"])
    d.mkdir(parents=True, exist_ok=True); (d/"generation.json").write_text(json.dumps(gen), encoding="utf-8")
    m=publish.run("2026-07-01")
    assert m["status"]=="failed" and "slug" in (m["error"] or "").lower()
    assert not (root/"content"/"_index.md").exists()                 # no traversal write
    assert not (root/"content"/"articles"/"2026-07-01-b.md").exists()   # nothing promoted
    assert _git_in(["status","--porcelain"], root).stdout.strip()==""

def test_run_rejects_traversal_gen_date(tmp_path, monkeypatch):
    # Codex R2 BLOCK: a corrupt generation.json "date" must not path-traverse; run() pins it
    # to the validated arg before any fs use.
    root=_init_repo(tmp_path, monkeypatch)
    (root/"content"/"_index.md").write_text("keep\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","idx"], root)
    gen={"date":"../_index","results":[_okres("a"),_okres("b"),_okres("c")]}
    d=root/"runs"/"2026-07-01"; d.mkdir(parents=True, exist_ok=True)
    (d/"generation.json").write_text(json.dumps(gen), encoding="utf-8")
    m=publish.run("2026-07-01")
    assert m["status"]=="failed" and "date" in (m["reason"]+ (m["error"] or "")).lower()
    assert (root/"content"/"_index.md").read_text()=="keep\n"         # tracked file untouched
    assert _git_in(["status","--porcelain"], root).stdout.strip()==""

def test_run_rejects_invalid_date_arg(tmp_path, monkeypatch):
    # Codex R2 BLOCK: an invalid date arg must be rejected BEFORE run_dir(date) (manifest path).
    root=_init_repo(tmp_path, monkeypatch)
    m=publish.run("../evil")
    assert m["status"]=="failed"
    assert not (root/"evil").exists()          # run_dir("../evil") would be ROOT/evil — no write

def test_completeness_rejects_cross_date_slug(tmp_path):
    # Codex R2 MAJOR: a charset-safe slug from ANOTHER day must be rejected (date-scoped).
    gen={"date":"2026-07-01","results":[{"event_key":"x","evidence_level":"confirmed","status":"ok",
         "slug":"2026-06-30-x","url":"https://x/x","post_path":"articles/2026-06-30-x.md","title":"T","source":"S","source_type":"article"}]}
    assert any("date-scoped" in e for e in check_completeness(gen, tmp_path/"s"))

def test_commit_message_does_not_attribute_codex_output_to_claude():
    message = publish._commit_msg("2026-07-01", {"results": []})
    assert "Claude" not in message and "anthropic.com" not in message and "claude.ai" not in message
    assert "Generated-By: Codex" in message
