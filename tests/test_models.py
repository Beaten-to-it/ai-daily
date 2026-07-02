from nbs.models import validate_selection, validate_against_candidates

BASE_ITEM = {"event_key":"k","title":"T","url":"https://x/y","source":"s",
             "source_type":"article","evidence_type":"article","dedup":"new",
             "prior_post_path":None,"rank":1,"rationale":"why"}

def _obj(items): return {"date":"2026-07-01","items":items,"selected_count":len(items),
                         "skipped_count":0,"generated_with":"claude-p"}

def test_valid_selection_passes():
    assert validate_selection(_obj([dict(BASE_ITEM)])) == []

def test_bad_dedup_value_flagged():
    it = dict(BASE_ITEM, dedup="MAYBE")
    assert any("dedup" in e for e in validate_selection(_obj([it])))

def test_followup_requires_prior_path():
    it = dict(BASE_ITEM, dedup="followup", prior_post_path=None)
    errs = validate_selection(_obj([it]))
    assert any("prior_post_path" in e for e in errs)

def test_canonicalize_url_query_order():
    # Fix 3: reordered query params canonicalize equal
    from nbs.models import canonicalize_url
    assert canonicalize_url("https://x.com/p?b=2&a=1") == canonicalize_url("https://x.com/p?a=1&b=2")

def test_validate_selection_items_not_list():
    # Fix 2: items as dict → error list, no raise
    bad = {"date":"d","items":{},"selected_count":0,"skipped_count":0,"generated_with":"x"}
    errs = validate_selection(bad)
    assert errs and not any(isinstance(e, Exception) for e in errs)
    assert any("items not a list" in e for e in errs)

def test_validate_selection_item_not_dict():
    # Fix 2: item is not a dict → error, no raise
    bad = {"date":"d","items":[123],"selected_count":1,"skipped_count":0,"generated_with":"x"}
    errs = validate_selection(bad)
    assert errs and any("not a dict" in e for e in errs)

def test_membership_and_uniqueness():
    it = dict(BASE_ITEM, url="https://x/y")
    cand = {"https://x/y"}
    assert validate_against_candidates(_obj([it]), cand) == []
    # url not in candidates
    bad = dict(BASE_ITEM, url="https://x/z")
    assert any("not in candidates" in e for e in validate_against_candidates(_obj([bad]), cand))
    # duplicate event_key
    dup = _obj([dict(BASE_ITEM), dict(BASE_ITEM, url="https://x/y")])
    assert any("duplicate" in e for e in validate_against_candidates(dup, cand))

from nbs.models import validate_blog_output, parse_frontmatter
_GOOD = """---
title: 테스트 제목
date: 2026-07-01
tags: [ai]
source_url: https://x.test/a
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
def test_missing_frontmatter_key():
    bad = _GOOD.replace("event_key: x-launch\n", "")
    assert any("event_key" in e for e in validate_blog_output(bad))
def test_empty_body_flagged():
    head = _GOOD[:_GOOD.rindex("---")+3]
    assert any("body" in e for e in validate_blog_output(head + "\n   \n"))
def test_bad_evidence_level():
    bad = _GOOD.replace("evidence_level: confirmed", "evidence_level: unverified")
    assert any("evidence_level" in e for e in validate_blog_output(bad))
def test_no_frontmatter_at_all():
    assert validate_blog_output("just text") == ["missing front matter block"]

from nbs.models import parse_frontmatter_strict

def test_parse_frontmatter_strict_unquotes_and_lists():
    md = ('---\ntitle: "Claude: 5"\nsource_url: \'https://x/a\'\n'
          'tags: [ai, "model release"]\nempty: []\n---\nbody\n')
    fm = parse_frontmatter_strict(md)
    assert fm["title"] == "Claude: 5"
    assert fm["source_url"] == "https://x/a"
    assert fm["tags"] == ["ai", "model release"]
    assert fm["empty"] == []
