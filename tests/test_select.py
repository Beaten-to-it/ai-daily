import json

import pytest

from nbs import select
from nbs.models import Candidate


def test_main_rejects_invalid_date_before_creating_run_path(tmp_path, monkeypatch):
    monkeypatch.setattr(select, "run_dir", lambda date: tmp_path / date)
    with pytest.raises(SystemExit):
        select.main(["--date", "../evil"])
    assert not (tmp_path.parent / "evil").exists()


def _candidate(index):
    return Candidate(
        source="OpenAI",
        source_type="article",
        title=f"Title {index}",
        url=f"https://example.com/{index}",
        canonical_url=f"https://example.com/{index}",
        published_at=None,
        snippet="snippet",
        raw_id=str(index),
        lane="official",
        discovered_via="feed",
    ).to_dict()


def _decision(candidate, rank=1):
    return {
        "candidate_id": candidate["candidate_id"],
        "decision": "select",
        "dedup": "new",
        "prior_post_path": None,
        "rank": rank,
        "reason_code": "selected",
        "rationale": "important",
    }


def test_parse_strips_fences_for_archived_responses():
    raw = '설명\n```json\n{"date":"2026-07-01","decisions":[],"generated_with":"codex-exec"}\n```\n끝'
    assert select.parse_selection(raw)["date"] == "2026-07-01"


def test_build_input_has_ledger_candidates_and_candidate_id():
    candidate = _candidate(1)
    text = select.build_prompt_input(
        [candidate],
        [{"event_key": "old", "title": "O", "summary": "s",
          "date": "2026-06-30", "post_path": "posts/old"}],
        "2026-07-01",
    )
    assert "OpenAI" in text and "old" in text and candidate["candidate_id"] in text
    assert "```" not in text


def test_run_codex_uses_selection_schema_and_isolated_workdir(monkeypatch, tmp_path):
    seen = {}
    expected = {"date": "2026-07-01", "decisions": [], "generated_with": "codex-exec"}
    def fake_run_json(prompt, schema, work_dir, timeout):
        seen.update(prompt=prompt, schema=schema, work_dir=work_dir, timeout=timeout)
        return expected
    monkeypatch.setattr(select, "run_dir", lambda date: tmp_path / date)
    monkeypatch.setattr(select.codex_cli, "run_json", fake_run_json)

    assert select.run_codex("hello", "2026-07-01", timeout=7) == expected
    assert seen["prompt"] == "hello" and seen["timeout"] == 7
    assert seen["schema"].name == "selection.schema.json"
    assert seen["work_dir"] == tmp_path / "2026-07-01" / "codex-work" / "selection"


def test_materialize_selection_does_not_cap_31_items():
    candidates = [_candidate(index) for index in range(31)]
    model = {"date": "2026-08-01",
             "decisions": [_decision(candidate, rank=index + 1)
                           for index, candidate in enumerate(candidates)],
             "generated_with": "codex-exec"}
    result = select.materialize_selection(model, candidates, "2026-08-01")
    assert result["selected_count"] == 31
    assert len(result["items"]) == 31


def test_normalize_candidate_rejects_tampered_candidate_id():
    import pytest
    candidate = _candidate(1)
    candidate["candidate_id"] = "0" * 20
    with pytest.raises(ValueError, match="candidate_id mismatch"):
        select.normalize_candidate(candidate)


def test_select_rejects_missing_decision_before_writing_selection(tmp_path, monkeypatch):
    date = "2026-08-01"
    directory = tmp_path / date
    directory.mkdir(parents=True)
    candidates = [_candidate(1), _candidate(2)]
    (directory / "candidates.json").write_text(json.dumps(candidates), encoding="utf-8")
    model = {"date": date, "decisions": [_decision(candidates[0])],
             "generated_with": "codex-exec"}
    monkeypatch.setattr(select, "run_dir", lambda value: directory)
    monkeypatch.setattr(select, "run_codex", lambda prompt, value: model)
    monkeypatch.setattr(select.ledger_mod, "read_recent", lambda **kwargs: [])

    import pytest
    with pytest.raises(ValueError, match="missing decision"):
        select.select(date)
    assert not (directory / "selection.json").exists()


def test_select_materializes_immutable_candidate_fields(tmp_path, monkeypatch):
    date = "2026-08-01"
    directory = tmp_path / date
    directory.mkdir(parents=True)
    candidate = _candidate(1)
    (directory / "candidates.json").write_text(json.dumps([candidate]), encoding="utf-8")
    decision = _decision(candidate)
    model = {"date": date, "decisions": [decision], "generated_with": "codex-exec"}
    monkeypatch.setattr(select, "run_dir", lambda value: directory)
    monkeypatch.setattr(select, "run_codex", lambda prompt, value: model)
    monkeypatch.setattr(select.ledger_mod, "read_recent", lambda **kwargs: [])

    result = select.select(date)
    item = result["items"][0]
    assert item["title"] == candidate["title"]
    assert item["snippet"] == candidate["snippet"]
    assert item["url"] == candidate["url"]
    assert item["source"] == candidate["source"]
    assert result["decisions"] == [decision]
