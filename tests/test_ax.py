import json as _json
import re

import pytest

from nbs import assemble
from nbs.models import GenerationResult


def _res(slug, title="T", status="ok"):
    return GenerationResult(event_key=slug.split("2026-07-03-")[-1], title=title, url="http://x",
                            source="s", source_type="article", evidence_level="confirmed",
                            status=status, post_path=f"content/posts/{slug}.md", slug=slug, rank=1)


def _fm(body):  # valid front matter + given body
    return f"---\ntitle: AI 경영 브리핑 2026-07-03\ndate: 2026-07-03\ntags: [ax]\n---\n\n{body}\n"


# --- Task 1: build_ax + grounding gate ---------------------------------------

def test_build_ax_none_when_no_publishable():
    assert assemble.build_ax([_res("2026-07-03-a", status="failed")], "2026-07-03", run=lambda p: "x") is None


def test_build_ax_ok_with_anchored_relref():
    results = [_res("2026-07-03-a"), _res("2026-07-03-b")]
    body = '오픈AI 지분 소식은 조직에 X를 시사 [자세히]({{< relref "/posts/2026-07-03-a.md" >}}).'
    md = assemble.build_ax(results, "2026-07-03", run=lambda p: _fm(body))
    assert md.startswith("---") and "relref" in md


def test_build_ax_rejects_zero_anchor():  # (a)
    results = [_res("2026-07-03-a")]
    with pytest.raises(ValueError):
        assemble.build_ax(results, "2026-07-03", run=lambda p: _fm("일반론만 있고 항목 링크가 없다."))


def test_build_ax_rejects_hallucinated_slug():  # (b)
    results = [_res("2026-07-03-a")]
    body = '[x]({{< relref "/posts/2026-07-03-a.md" >}}) [y]({{< relref "/posts/2026-07-03-ZZZ.md" >}})'
    with pytest.raises(ValueError):
        assemble.build_ax(results, "2026-07-03", run=lambda p: _fm(body))


def test_build_ax_rejects_non_angle_shortcode():  # (c) — email would fail on {{% %}}
    results = [_res("2026-07-03-a")]
    body = '[x]({{< relref "/posts/2026-07-03-a.md" >}}) 그리고 {{% relref "/posts/2026-07-03-a.md" %}}'
    with pytest.raises(ValueError):
        assemble.build_ax(results, "2026-07-03", run=lambda p: _fm(body))


def test_build_ax_rejects_missing_front_matter():
    with pytest.raises(ValueError):
        assemble.build_ax([_res("2026-07-03-a")], "2026-07-03",
                          run=lambda p: '본문만 {{< relref "/posts/2026-07-03-a.md" >}}')


def test_gate_pass_body_is_email_safe():
    # positive seam (advisor): gate condition (c) means gate-pass ⟹ email-safe. A body whose
    # only shortcode is the angle relref build_ax accepts must survive email.rewrite_relref
    # (no raise) — guards against the two mirrored-but-separate regexes drifting apart.
    from nbs import email as em
    results = [_res("2026-07-03-a")]
    body = '오픈AI 지분 소식 [자세히]({{< relref "/posts/2026-07-03-a.md" >}}).'
    md = assemble.build_ax(results, "2026-07-03", run=lambda p: _fm(body))   # passes the gate
    ax_body = md.split("---", 2)[2]                                          # strip front matter
    out = em.rewrite_relref(ax_body)                                        # must NOT raise
    assert "https://beaten-to-it.github.io/ai-daily/posts/2026-07-03-a/" in out
    assert "relref" not in out


# --- Task 2: stage ax wiring (§5 isolation) ----------------------------------

from nbs import stage as stage_mod


def _seed_selection(tmp_path, date, monkeypatch):
    from nbs import config
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(stage_mod, "run_dir", lambda d: tmp_path / "runs" / d)
    d = tmp_path / "runs" / date; d.mkdir(parents=True)
    (d / "selection.json").write_text(_json.dumps({"items": [
        {"event_key": "a", "url": "http://x", "source_type": "article", "title": "T"}]}), encoding="utf-8")
    return d


def _ok_gen(items, fetched, date):
    from nbs.models import GenerationResult
    r = GenerationResult(event_key="a", title="T", url="http://x", source="s", source_type="article",
                         evidence_level="confirmed", status="ok",
                         post_path="content/posts/2026-07-03-a.md", slug="2026-07-03-a", rank=1)
    r._md = "---\nx: 1\n---\nbody"
    return [r, r, r]  # >=FLOOR_N publishable so floor passes


def _ok_fetch(it):
    from nbs.models import FetchResult
    return FetchResult(event_key=it["event_key"], url=it["url"], source_type="article",
                       text="body", evidence_level="confirmed", via="t", fetch_ok=True)


def test_stage_ax_isolated_failure_records_ax_error(tmp_path, monkeypatch):
    d = _seed_selection(tmp_path, "2026-07-03", monkeypatch)
    def boom_ax(results, date): raise RuntimeError("ax boom")
    payload = stage_mod.run("2026-07-03", fetch=_ok_fetch, generate=_ok_gen,
                            usecase=lambda r, dt: None, ax=boom_ax)
    assert payload["ax_error"] == "ax boom"[:200]
    assert payload["status"] == "ok"                       # ax failure did NOT abort
    assert not (d / "staging" / "ax" / "2026-07-03.md").exists()


def test_stage_writes_ax_when_ok(tmp_path, monkeypatch):
    d = _seed_selection(tmp_path, "2026-07-03", monkeypatch)
    stage_mod.run("2026-07-03", fetch=_ok_fetch, generate=_ok_gen,
                  usecase=lambda r, dt: None, ax=lambda r, dt: "AX-MD")
    assert (d / "staging" / "ax" / "2026-07-03.md").read_text() == "AX-MD"


# --- Task 3: publish ax touchpoints ------------------------------------------

from pathlib import Path


def test_writeset_includes_ax():
    from nbs import publish as P
    ws = P.date_writeset({"date": "2026-07-03", "results": []})
    assert "content/ax/2026-07-03.md" in ws


def test_degraded_includes_ax_error():
    from nbs import publish as P
    assert P._degraded({"date": "2026-07-03", "results": [], "ax_error": "ax boom"}).get("ax") == "ax boom"


def test_promote_copies_ax_optional(tmp_path, monkeypatch):
    from nbs import publish as P
    monkeypatch.setattr(P, "ROOT", tmp_path)
    (tmp_path / "content" / "posts").mkdir(parents=True)
    (tmp_path / "content" / "news").mkdir(parents=True)
    staging = tmp_path / "staging"
    for sub in ("posts", "news", "ax"):
        (staging / sub).mkdir(parents=True)
    (staging / "news" / "2026-07-03.md").write_text("news")
    (staging / "ax" / "2026-07-03.md").write_text("axmd")
    touched = P.promote({"date": "2026-07-03", "results": []}, staging)
    assert (tmp_path / "content" / "ax" / "2026-07-03.md").read_text() == "axmd"
    assert "content/ax/2026-07-03.md" in touched


def test_build_verify_flags_missing_ax_page(tmp_path, monkeypatch):
    # implementer must not omit the build_verify ax check — mock hugo, render news but NOT ax
    from nbs import publish as P
    monkeypatch.setattr(P, "ROOT", tmp_path)
    (tmp_path / "content" / "ax").mkdir(parents=True)
    (tmp_path / "content" / "ax" / "2026-07-03.md").write_text("ax", encoding="utf-8")
    def fake_build(outdir):
        o = Path(outdir); (o / "news" / "2026-07-03").mkdir(parents=True)
        (o / "news" / "2026-07-03" / "index.html").write_text("<html></html>")
        return 0   # deliberately does NOT create ax/2026-07-03/index.html
    monkeypatch.setattr(P, "_hugo_build", fake_build)
    errs = P.build_verify({"date": "2026-07-03", "results": []})
    assert any("ax page not rendered" in e for e in errs)


# --- Task 4: hugo.toml menu + mainSections -----------------------------------

def test_hugo_config_has_ax_section_and_menu():
    from nbs import config as _cfg
    toml = (Path(_cfg.ROOT) / "hugo.toml").read_text(encoding="utf-8")
    assert '"ax"' in toml.split("mainSections")[1].split("]")[0]   # ax in mainSections
    assert 'url = "ax/"' in toml                                    # menu entry
