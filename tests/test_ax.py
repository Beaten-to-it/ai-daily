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
