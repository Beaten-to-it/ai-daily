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
