from nbs.models import (
    Candidate,
    candidate_id,
    materialize_selected,
    parse_frontmatter,
    parse_frontmatter_strict,
    validate_blog_output,
    validate_decision_coverage,
    validate_decisions,
    validate_selection,
)


def _candidate(url="https://x/y", source="OpenAI", source_type="article"):
    return Candidate(
        source=source,
        source_type=source_type,
        title="Local title",
        url=url,
        canonical_url=url,
        published_at="2026-07-01T00:00:00+00:00",
        snippet="local snippet",
        raw_id="raw-1",
        lane="official",
        discovered_via="https://feed.example/rss",
    ).to_dict()


def _decision(candidate, decision="select", **overrides):
    row = {
        "candidate_id": candidate["candidate_id"],
        "decision": decision,
        "dedup": "new" if decision == "select" else "skip",
        "prior_post_path": None,
        "rank": 1,
        "reason_code": "selected" if decision == "select" else "low_significance",
        "rationale": "why",
    }
    row.update(overrides)
    return row


def test_candidate_id_is_stable_for_canonical_url():
    assert candidate_id("HTTPS://X.COM/a/?b=2&a=1&utm_source=rss") == candidate_id(
        "https://x.com/a?a=1&b=2"
    )
    assert len(candidate_id("https://x.com/a")) == 20


def test_candidate_dict_contains_provenance_and_id():
    candidate = _candidate()
    assert candidate["candidate_id"] == candidate_id(candidate["url"])
    assert candidate["lane"] == "official"
    assert candidate["discovered_via"] == "https://feed.example/rss"


def test_selection_requires_exactly_one_decision_per_candidate():
    candidates = [_candidate("https://a.example/x"), _candidate("https://b.example/y")]
    model = {"date": "2026-08-01", "decisions": [_decision(candidates[0])],
             "generated_with": "codex-exec"}
    assert validate_decision_coverage(model, candidates) == [
        "missing decision: " + candidates[1]["candidate_id"]
    ]


def test_decision_coverage_rejects_duplicate_and_unknown_ids():
    candidate = _candidate()
    unknown = _candidate("https://unknown.example/x")
    row = _decision(candidate)
    model = {"decisions": [row, dict(row), _decision(unknown)]}
    errors = validate_decision_coverage(model, [candidate])
    assert any("duplicate decision" in error for error in errors)
    assert any("unexpected decision" in error for error in errors)


def test_selected_source_fields_come_from_candidate_not_model():
    candidate = _candidate(source="OpenAI", source_type="article")
    decision = _decision(candidate)
    decision.update(source="Evil", source_type="sns", url="https://evil.example/x", title="Fake")
    item = materialize_selected(candidate, decision)
    assert item["source"] == "OpenAI"
    assert item["source_type"] == "article"
    assert item["url"] == candidate["url"]
    assert item["title"] == "Local title"
    assert item["snippet"] == "local snippet"
    assert item["event_key"] == candidate["candidate_id"]


def test_model_decision_rejects_candidate_owned_fields():
    candidate = _candidate()
    decision = _decision(candidate)
    decision.update(source="Evil", url="https://evil.example/x")
    errors = validate_decisions({"date": "2026-08-01", "decisions": [decision],
                                 "generated_with": "codex-exec"})
    assert any("unexpected" in error and "source" in error and "url" in error for error in errors)


def test_decision_semantics_are_validated():
    candidate = _candidate()
    assert validate_decisions({"date": "2026-08-01", "decisions": [_decision(candidate)],
                               "generated_with": "codex-exec"}) == []
    bad = _decision(candidate, decision="select", dedup="skip", reason_code="duplicate")
    errors = validate_decisions({"date": "2026-08-01", "decisions": [bad],
                                 "generated_with": "codex-exec"})
    assert any("select requires" in error for error in errors)


def test_materialized_selection_counts_match_decisions():
    candidate = _candidate()
    decision = _decision(candidate)
    item = materialize_selected(candidate, decision)
    obj = {
        "date": "2026-08-01",
        "decisions": [decision],
        "items": [item],
        "selected_count": 1,
        "skipped_count": 0,
        "generated_with": "codex-exec",
    }
    assert validate_selection(obj) == []
    obj["selected_count"] = 99
    assert any("selected_count mismatch" in error for error in validate_selection(obj))


_GOOD = """---
title: 테스트 제목
date: 2026-07-01
tags: [ai]
source_url: https://x.test/a
source_name: X
source_published_at: 2026-07-01T00:00:00+00:00
source_lang: en
source_type: article
evidence_level: confirmed
event_key: x-launch
---
본문 내용이 여기 있다. 충분히 길다.
"""


def test_parse_frontmatter_reads_keys():
    fm = parse_frontmatter(_GOOD)
    assert fm["event_key"] == "x-launch" and fm["source_url"] == "https://x.test/a"


def test_valid_blog_passes():
    assert validate_blog_output(_GOOD) == []


def test_frontmatter_closes_only_on_its_own_fence_line():
    markdown = _GOOD.replace("title: 테스트 제목", "title: 테스트 --- 제목")
    frontmatter = parse_frontmatter(markdown)
    assert frontmatter["event_key"] == "x-launch"
    assert validate_blog_output(markdown) == []


def test_article_frontmatter_rejects_unknown_keys_after_inline_dashes():
    markdown = _GOOD.replace(
        "title: 테스트 제목",
        "title: 테스트 --- 제목\naliases: [/takeover/]",
    )
    errors = validate_blog_output(markdown)
    assert any("unknown" in error and "aliases" in error for error in errors)


def test_missing_frontmatter_key():
    bad = _GOOD.replace("event_key: x-launch\n", "")
    assert any("event_key" in error for error in validate_blog_output(bad))


def test_missing_source_metadata_is_flagged():
    bad = _GOOD.replace("source_name: X\n", "").replace(
        "source_published_at: 2026-07-01T00:00:00+00:00\n", ""
    )
    errors = validate_blog_output(bad)
    assert any("source_name" in error for error in errors)
    assert any("source_published_at" in error for error in errors)


def test_empty_body_flagged():
    head = _GOOD[:_GOOD.rindex("---") + 3]
    assert any("body" in error for error in validate_blog_output(head + "\n   \n"))


def test_bad_evidence_level():
    bad = _GOOD.replace("evidence_level: confirmed", "evidence_level: unverified")
    assert any("evidence_level" in error for error in validate_blog_output(bad))


def test_no_frontmatter_at_all():
    assert validate_blog_output("just text") == ["missing front matter block"]


def test_parse_frontmatter_strict_unquotes_and_lists():
    markdown = ('---\ntitle: "Claude: 5"\nsource_url: \'https://x/a\'\n'
                'tags: [ai, "model release"]\nempty: []\n---\nbody\n')
    frontmatter = parse_frontmatter_strict(markdown)
    assert frontmatter["title"] == "Claude: 5"
    assert frontmatter["source_url"] == "https://x/a"
    assert frontmatter["tags"] == ["ai", "model release"]
    assert frontmatter["empty"] == []
