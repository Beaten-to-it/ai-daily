from nbs import assemble
from nbs.models import GenerationResult
def _r(k, status="ok", rank=1, rationale="hook-"):
    return GenerationResult(event_key=k, title=f"T-{k}", url="u", source="S",
        source_type="article", evidence_level="confirmed", status=status,
        post_path=f"posts/2026-07-01-{k}.md", slug=f"2026-07-01-{k}", rank=rank,
        rationale=f"{rationale}{k}")

def test_publishable_filters_non_ok():
    res=[_r("a"), _r("b", status="failed"), _r("c", status="excluded")]
    assert [r.event_key for r in assemble.publishable(res)] == ["a"]

def test_floor_blocks_below_n():
    assert assemble.floor_ok([_r("a"), _r("b")]) is False
    assert assemble.floor_ok([_r("a"), _r("b"), _r("c")]) is True

def test_news_index_only_ok_with_hook_and_category():
    res=[_r("a", rank=1), _r("b", status="failed", rank=2), _r("c", rank=3)]
    md=assemble.build_news_index(res, "2026-07-01")
    assert "T-a" in md and "T-c" in md and "T-b" not in md
    assert "2026-07-01-a" in md          # links post slug
    assert "hook-a" in md                # per-item hook from rationale
    assert "뉴스/블로그" in md            # category header for article

def _ok_with_md(k, body="이 도구로 요약을 자동화한다"):
    r=_r(k)
    r._md=f"---\ntitle: T-{k}\n---\n{body}\n"
    return r

def test_usecase_none_when_empty():
    assert assemble.build_usecase([_r("a", status="failed")], "2026-07-01") is None

def test_usecase_prompt_includes_titles_and_snippet():
    p=assemble.build_usecase_prompt([_ok_with_md("a")], "2026-07-01")
    assert "T-a" in p and "요약을 자동화" in p and "2026-07-01" in p

def test_usecase_uses_injected_run_and_validates():
    out=assemble.build_usecase([_ok_with_md("a")], "2026-07-01",
                               run=lambda t, timeout=180: "---\ntitle: U\ndate: 2026-07-01\ntags: [usecase]\n---\nbody\n")
    assert out.startswith("---")

def test_usecase_rejects_missing_frontmatter():
    import pytest
    with pytest.raises(ValueError):
        assemble.build_usecase([_ok_with_md("a")], "2026-07-01", run=lambda t, timeout=180: "no fm")
