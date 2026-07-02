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
