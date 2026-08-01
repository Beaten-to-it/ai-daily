import json as _json
import re

import pytest

from nbs import assemble
from nbs.models import GenerationResult


def _res(slug, title="T", status="ok"):
    return GenerationResult(event_key=slug.split("2026-07-03-")[-1], title=title, url="http://x",
                            source="s", source_type="article", evidence_level="confirmed",
                            status=status, post_path=f"articles/{slug}.md", slug=slug, rank=1)


def _fm(body):  # valid front matter + given body
    return f"---\ntitle: AI 경영 브리핑 2026-07-03\ndate: 2026-07-03\ntags: [executive]\n---\n\n{body}\n"


# --- Task 1: build_ax + grounding gate ---------------------------------------

def test_build_executive_none_when_no_publishable():
    assert assemble.build_executive([_res("2026-07-03-a", status="failed")], "2026-07-03", run=lambda p: "x") is None


def test_build_ax_ok_with_anchored_relref():
    results = [_res("2026-07-03-a"), _res("2026-07-03-b")]
    body = '오픈AI 지분 소식은 조직에 X를 시사 [자세히]({{< relref "/articles/2026-07-03-a.md" >}}).'
    md = assemble.build_executive(results, "2026-07-03", run=lambda p: _fm(body))
    assert md.startswith("---") and "relref" in md


def test_build_ax_rejects_zero_anchor():  # (a)
    results = [_res("2026-07-03-a")]
    with pytest.raises(ValueError):
        assemble.build_executive(results, "2026-07-03", run=lambda p: _fm("일반론만 있고 항목 링크가 없다."))


def test_build_ax_rejects_hallucinated_slug():  # (b)
    results = [_res("2026-07-03-a")]
    body = '[x]({{< relref "/articles/2026-07-03-a.md" >}}) [y]({{< relref "/articles/2026-07-03-ZZZ.md" >}})'
    with pytest.raises(ValueError):
        assemble.build_executive(results, "2026-07-03", run=lambda p: _fm(body))


def test_build_ax_rejects_non_angle_shortcode():  # (c) — email would fail on {{% %}}
    results = [_res("2026-07-03-a")]
    body = '[x]({{< relref "/articles/2026-07-03-a.md" >}}) 그리고 {{% relref "/articles/2026-07-03-a.md" %}}'
    with pytest.raises(ValueError):
        assemble.build_executive(results, "2026-07-03", run=lambda p: _fm(body))


def test_build_ax_rejects_missing_front_matter():
    with pytest.raises(ValueError):
        assemble.build_executive([_res("2026-07-03-a")], "2026-07-03",
                          run=lambda p: '본문만 {{< relref "/articles/2026-07-03-a.md" >}}')


def test_build_ax_default_run_uses_long_timeout(monkeypatch):
    # daily stage calls build_ax with run=None → must use AX_TIMEOUT (>300), else it ax_errors
    # every day (AX synthesis overruns the 300s GEN_TIMEOUT).
    from nbs import generate as gen
    seen = {}
    def fake(text, date, operation, timeout=None):
        seen.update(date=date, operation=operation, timeout=timeout)
        return {"publish": True, "markdown": _fm('[x]({{< relref "/articles/2026-07-03-a.md" >}})')}
    monkeypatch.setattr(gen, "run_codex_derived", fake)
    assemble.build_executive([_res("2026-07-03-a")], "2026-07-03")   # run=None → real default path
    assert seen["timeout"] == assemble.EXECUTIVE_TIMEOUT
    assert seen["date"] == "2026-07-03" and seen["operation"] == "executive"
    assert assemble.EXECUTIVE_TIMEOUT >= 600


def test_gate_pass_body_uses_only_article_slugs():
    # positive seam (advisor): gate condition (c) means gate-pass ⟹ email-safe. A body whose
    # only shortcode is the angle relref build_ax accepts must survive email.rewrite_relref
    # (no raise) — guards against the two mirrored-but-separate regexes drifting apart.
    results = [_res("2026-07-03-a")]
    body = '오픈AI 지분 소식 [자세히]({{< relref "/articles/2026-07-03-a.md" >}}).'
    md = assemble.build_executive(results, "2026-07-03", run=lambda p: _fm(body))   # passes the gate
    assert '/articles/2026-07-03-a.md' in md and '/posts/' not in md


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
                         post_path="articles/2026-07-03-a.md", slug="2026-07-03-a", rank=1)
    r._md = "---\nx: 1\n---\nbody"
    return [r, r, r]  # >=FLOOR_N publishable so floor passes


def _ok_fetch(it):
    from nbs.models import FetchResult
    return FetchResult(event_key=it["event_key"], url=it["url"], source_type="article",
                       text="body", evidence_level="confirmed", via="t", fetch_ok=True)


def test_stage_executive_isolated_failure_records_error(tmp_path, monkeypatch):
    d = _seed_selection(tmp_path, "2026-07-03", monkeypatch)
    def boom_ax(results, date): raise RuntimeError("ax boom")
    payload = stage_mod.run("2026-07-03", fetch=_ok_fetch, generate=_ok_gen,
                            guide=lambda r, dt: None, executive=boom_ax)
    assert payload["executive_error"] == "ax boom"[:200]
    assert payload["status"] == "ok"                       # ax failure did NOT abort
    assert not (d / "staging" / "executive" / "2026-07-03.md").exists()


def test_stage_writes_executive_when_ok(tmp_path, monkeypatch):
    d = _seed_selection(tmp_path, "2026-07-03", monkeypatch)
    stage_mod.run("2026-07-03", fetch=_ok_fetch, generate=_ok_gen,
                  guide=lambda r, dt: None, executive=lambda r, dt: "AX-MD")
    assert (d / "staging" / "executive" / "2026-07-03.md").read_text() == "AX-MD"


# --- Task 3: publish ax touchpoints ------------------------------------------

from pathlib import Path


def test_writeset_includes_executive():
    from nbs import publish as P
    ws = P.date_writeset({"date": "2026-07-03", "results": []})
    assert "content/executive/2026-07-03.md" in ws


def test_degraded_includes_executive_error():
    from nbs import publish as P
    assert P._degraded({"date": "2026-07-03", "results": [], "executive_error": "boom"}).get("executive") == "boom"


def test_promote_copies_executive_optional(tmp_path, monkeypatch):
    from nbs import publish as P
    monkeypatch.setattr(P, "ROOT", tmp_path)
    (tmp_path / "content" / "articles").mkdir(parents=True)
    (tmp_path / "content" / "daily").mkdir(parents=True)
    staging = tmp_path / "staging"
    for sub in ("articles", "daily", "executive"):
        (staging / sub).mkdir(parents=True)
    (staging / "daily" / "2026-07-03.md").write_text("daily")
    (staging / "executive" / "2026-07-03.md").write_text("executive")
    touched = P.promote({"date": "2026-07-03", "results": []}, staging)
    assert (tmp_path / "content" / "executive" / "2026-07-03.md").read_text() == "executive"
    assert "content/executive/2026-07-03.md" in touched


def test_build_verify_flags_missing_executive_page(tmp_path, monkeypatch):
    from nbs import publish as P
    monkeypatch.setattr(P, "ROOT", tmp_path)
    (tmp_path / "content" / "executive").mkdir(parents=True)
    (tmp_path / "content" / "executive" / "2026-07-03.md").write_text("executive", encoding="utf-8")
    def fake_build(outdir):
        o = Path(outdir); (o / "daily" / "2026-07-03").mkdir(parents=True)
        (o / "daily" / "2026-07-03" / "index.html").write_text("<html></html>")
        return 0
    monkeypatch.setattr(P, "_hugo_build", fake_build)
    errs = P.build_verify({"date": "2026-07-03", "results": []})
    assert any("executive page not rendered" in e for e in errs)


# --- Task 4: hugo.toml menu + mainSections -----------------------------------

def test_hugo_config_separates_new_sections():
    from nbs import config as _cfg
    toml = (Path(_cfg.ROOT) / "hugo.toml").read_text(encoding="utf-8")
    assert 'mainSections = ["daily"]' in toml
    assert all(f'url = "{section}/"' in toml for section in ("daily", "articles", "executive", "guides"))
