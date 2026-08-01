import json

from nbs import collect
from nbs.models import Candidate, SourceHealth


def _candidate(url="https://example.com/ai"):
    return Candidate(
        source="example.com",
        source_type="article",
        title="AI update",
        url=url,
        canonical_url=url,
        published_at="2026-08-01T00:00:00+00:00",
        snippet="summary",
        raw_id=url,
        lane="official",
        discovered_via="https://example.com/feed",
    )


def test_failed_and_unconfigured_sources_do_not_drop_healthy_candidates(monkeypatch):
    secret = "do-not-record-this-token"
    monkeypatch.setenv("AI_DAILY_X_BEARER", secret)

    def failed():
        raise RuntimeError("Authorization: Bearer " + secret + " " + "x" * 600)

    def unconfigured():
        raise collect.Unconfigured("AI_DAILY_REDDIT_CLIENT_ID is not configured")

    candidates, health = collect.collect_with([
        {"name": "good", "lane": "official", "fetch": lambda: [_candidate()]},
        {"name": "x", "lane": "social", "fetch": failed},
        {"name": "reddit", "lane": "social", "fetch": unconfigured},
    ], "2026-08-01")

    by_name = {row.name: row for row in health}
    assert len(candidates) == 1
    assert by_name["good"].status == "ok"
    assert by_name["x"].status == "failed"
    assert by_name["reddit"].status == "unconfigured"
    assert secret not in by_name["x"].error
    assert len(by_name["x"].error) <= 500


def test_write_candidates_also_writes_source_health(tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "run_dir", lambda date: tmp_path / date)
    health = [SourceHealth("official", "feed", "ok", 1, 4)]

    candidates_path = collect.write_candidates("2026-08-01", [_candidate()], health)
    health_path = candidates_path.with_name("source_health.json")

    assert json.loads(candidates_path.read_text(encoding="utf-8"))[0]["url"] == "https://example.com/ai"
    assert json.loads(health_path.read_text(encoding="utf-8")) == [{
        "lane": "official",
        "name": "feed",
        "status": "ok",
        "candidate_count": 1,
        "elapsed_ms": 4,
        "error": "",
    }]


def test_degraded_source_keeps_partial_candidates():
    def partial():
        raise collect.Degraded([_candidate()], "one item failed")

    candidates, health = collect.collect_with([
        {"name": "partial", "lane": "web", "fetch": partial},
    ], "2026-08-01")

    assert len(candidates) == 1
    assert health[0].status == "degraded"
    assert health[0].candidate_count == 1


def test_error_redaction_does_not_corrupt_environment_variable_name():
    error = collect._safe_error(collect.Unconfigured(
        "AI_DAILY_X_BEARER is not configured"
    ))
    assert "AI_DAILY_X_BEARER is not configured" in error
