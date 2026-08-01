import json
import subprocess

from nbs import collect, config, orchestrate, select, stage
from nbs.models import Candidate, FetchResult, GenerationResult


DATE = "2026-08-01"


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _article(item):
    markdown = (
        "---\n"
        "title: 합성 AI 기사\n"
        f"date: {DATE}\n"
        "tags: [ai]\n"
        f"source_url: {item['url']}\n"
        f"source_name: {item['source']}\n"
        f"source_published_at: {item['published_at']}\n"
        "source_lang: en\n"
        "source_type: article\n"
        "evidence_level: confirmed\n"
        f"event_key: {item['event_key']}\n"
        "---\n"
        "## 무엇이 일어났나\n합성 발표가 있었다.\n\n"
        "## 왜 중요한가\n검증 경로를 확인한다.\n\n"
        "## 확인 범위\n주입한 근거만 사용했다.\n\n"
        f"## 출처\n- [원문]({item['url']})\n"
    )
    result = GenerationResult(
        event_key=item["event_key"], title=item["title"], url=item["url"],
        source=item["source"], source_type="article", evidence_level="confirmed",
        status="ok", post_path=f"articles/{DATE}-{item['event_key']}.md",
        slug=f"{DATE}-{item['event_key']}", rank=item["rank"],
        rationale=item["rationale"],
    )
    result._md = markdown
    return result


def test_shadow_prepare_builds_complete_manifest_without_external_changes(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "content").mkdir()
    (root / ".gitignore").write_text("runs/\n.orchestrate.lock\n", encoding="utf-8")
    _git(["init", "-q"], root)
    _git(["config", "user.email", "test@example.com"], root)
    _git(["config", "user.name", "Test"], root)
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "base"], root)
    before = _git(["rev-parse", "HEAD"], root).stdout.strip()

    run_dir = lambda date: root / "runs" / date
    monkeypatch.setattr(config, "ROOT", root)
    monkeypatch.setattr(orchestrate, "ROOT", root)
    monkeypatch.setattr(orchestrate, "run_dir", run_dir)
    monkeypatch.setattr(collect, "run_dir", run_dir)
    monkeypatch.setattr(select, "run_dir", run_dir)
    monkeypatch.setattr(stage, "run_dir", run_dir)

    verified = {}
    monkeypatch.setattr(
        orchestrate.publish_mod,
        "build_verify",
        lambda gen, content_dir=None: verified.update(content_dir=content_dir) or [],
    )

    def runner(name, date):
        if name == "collect":
            candidate = Candidate(
                source="OpenAI", source_type="article", title="Synthetic release",
                url="https://example.com/release", canonical_url="https://example.com/release",
                published_at="2026-08-01T00:00:00+00:00", snippet="evidence",
                raw_id="release-1", lane="official", discovered_via="https://example.com/feed",
            )
            candidates, health = collect.collect_with([
                {"name": "fixture", "lane": "official", "fetch": lambda: [candidate]}
            ], date)
            collect.write_candidates(date, candidates, health)
            return 0
        if name == "select":
            candidates = [select.normalize_candidate(row) for row in json.loads(
                (run_dir(date) / "candidates.json").read_text(encoding="utf-8")
            )]
            decision = {
                "candidate_id": candidates[0]["candidate_id"], "decision": "select",
                "dedup": "new", "prior_post_path": None, "rank": 1,
                "reason_code": "selected", "rationale": "meaningful",
            }
            result = select.materialize_selection(
                {"decisions": [decision], "generated_with": "fixture"}, candidates, date
            )
            (run_dir(date) / "selection.json").write_text(
                json.dumps(result, ensure_ascii=False), encoding="utf-8"
            )
            return 0
        if name == "stage":
            stage.run(
                date,
                fetch=lambda item: FetchResult(
                    item["event_key"], item["url"], "article", "fixture evidence",
                    "confirmed", "fixture", True,
                ),
                generate=lambda items, fetched, run_date: [_article(items[0])],
                guide=lambda *args: None,
                executive=lambda *args: None,
            )
            return 0
        raise AssertionError(f"unexpected stage: {name}")

    manifest = orchestrate.run(
        DATE, prepare_only=True, shadow=True, runner=runner,
        email_runner=lambda *args: (_ for _ in ()).throw(AssertionError("email called")),
    )

    assert manifest["status"] == "prepared"
    assert manifest["counts"] == {"candidates": 1, "selected": 1, "skipped": 0, "published": 1}
    assert manifest["decisions"] == {"select": 1, "skip": 0}
    assert manifest["source_health"][0]["status"] == "ok"
    assert manifest["warning_state"]["volume"] == "warning"
    assert manifest["codex_stderr_summary"] == {}
    assert manifest["git"]["prepared_head"] == before
    assert manifest["git"]["current_head"] == before
    assert all(manifest["stages"][name]["duration_ms"] >= 0
               for name in ("collect", "select", "stage", "validate"))
    assert verified["content_dir"] == run_dir(DATE) / "staging"
    assert _git(["rev-parse", "HEAD"], root).stdout.strip() == before
    assert _git(["status", "--porcelain"], root).stdout.strip() == ""
    assert not (root / "content" / "daily" / f"{DATE}.md").exists()
