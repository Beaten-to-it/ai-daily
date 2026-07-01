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
