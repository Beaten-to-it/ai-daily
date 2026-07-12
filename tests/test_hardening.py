"""Regression tests for the 2026-07-12 Codex adversarial-review hardening pass.
Each test pins one accepted fix so it can't silently regress."""
import json, subprocess
import pytest
from nbs import fetch, select, stage, orchestrate
from nbs.models import FetchResult, GenerationResult


# --- H1: SSRF — candidate URLs resolving to non-global IPs are blocked -------

def test_host_is_public_blocks_internal_ranges():
    for bad in ("http://127.0.0.1/x", "http://10.0.0.5/", "http://169.254.169.254/latest",
                "http://192.168.1.1/", "http://[::1]/", "http://100.64.1.1/"):   # incl. CGNAT
        assert fetch._host_is_public(bad) is False, bad
    assert fetch._host_is_public("http://8.8.8.8/") is True    # public IP literal (no DNS needed)
    assert fetch._host_is_public("not a url") is False         # no hostname


def test_http_get_never_opens_internal_host(monkeypatch):
    # the guard must short-circuit BEFORE any socket is opened
    def boom(*a, **k):
        raise AssertionError("urlopen must not be called for a non-global host")
    monkeypatch.setattr(fetch.urllib.request, "urlopen", boom)
    assert fetch._http_get("http://127.0.0.1/") == ("", False)


# --- C2: per-fetch byte cap bounds memory (drip time bound is deadline-based)-

def test_read_capped_enforces_byte_ceiling(monkeypatch):
    monkeypatch.setattr(fetch, "MAX_FETCH_BYTES", 100)
    class _Reader:                       # returns forever; only the cap can stop it
        def read(self, n): return b"x" * 80
    assert len(fetch._read_capped(_Reader())) == 100


# --- H4: selection count is hard-capped before generation --------------------

def test_recount_caps_to_max_selected():
    n = select.MAX_SELECTED + 7
    obj = {"items": [{"event_key": f"k{i}", "dedup": "new", "rank": i} for i in range(n)]}
    select.recount(obj)
    assert obj["selected_count"] == select.MAX_SELECTED
    assert [it["rank"] for it in obj["items"]] == list(range(select.MAX_SELECTED))  # kept top ranks


# --- H3: a null event_key isolates ONE item, never crashes the stage ---------

def test_null_event_key_isolated_not_crashing(tmp_path, monkeypatch):
    monkeypatch.setattr(stage, "run_dir", lambda date: tmp_path / date)
    date = "2026-07-12"; d = tmp_path / date; d.mkdir(parents=True)
    items = [
        {"event_key": None, "title": "bad", "url": "https://x/0", "source": "S",
         "source_type": "article", "evidence_type": "article", "dedup": "new",
         "prior_post_path": None, "rank": 0, "rationale": "r"},
        {"event_key": "good", "title": "ok", "url": "https://x/1", "source": "S",
         "source_type": "article", "evidence_type": "article", "dedup": "new",
         "prior_post_path": None, "rank": 1, "rationale": "r"},
    ]
    (d / "selection.json").write_text(json.dumps(
        {"date": date, "items": items, "selected_count": 2, "skipped_count": 0,
         "generated_with": "test"}), encoding="utf-8")

    captured = {}
    def _gen(items, fetched_map, date, **kw):
        captured["fmap"] = fetched_map                      # inspect isolation
        out = []
        for it in items:
            ek = it["event_key"]
            fr = fetched_map[ek]
            out.append(GenerationResult(
                event_key=ek, title=it["title"], url=it["url"], source="S", source_type="article",
                evidence_level=fr.evidence_level,
                status="excluded" if fr.evidence_level == "exclude" else "ok",
                post_path=None if fr.evidence_level == "exclude" else f"posts/{date}-{ek}.md",
                slug=f"{date}-{ek}", rank=it["rank"], rationale="r"))
        return out

    def _fetch(item):
        return FetchResult(item["event_key"], item["url"], "article", "t" * 50, "confirmed", "http", True)

    out = stage.run(date, fetch=_fetch, generate=_gen,
                    usecase=lambda *a, **k: None, ax=lambda *a, **k: None)   # no crash
    assert out["status"] == "ok"
    assert captured["fmap"][None].evidence_level == "exclude"
    assert captured["fmap"][None].via == "invalid-key"
    assert captured["fmap"]["good"].evidence_level == "confirmed"


# --- C3: a git subprocess timeout surfaces as rc=124, never an exception -----

def test_git_timeout_returns_124(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="git", timeout=1)
    monkeypatch.setattr(orchestrate.subprocess, "run", boom)
    r = orchestrate._git(["push", "origin", "HEAD:refs/heads/main"])
    assert r.returncode == 124                              # treated as ordinary git failure


def test_git_sets_terminal_prompt_off(monkeypatch):
    seen = {}
    class _R: returncode = 0; stdout = ""; stderr = ""
    def cap(cmd, **k):
        seen["env"] = k.get("env"); seen["timeout"] = k.get("timeout"); return _R()
    monkeypatch.setattr(orchestrate.subprocess, "run", cap)
    orchestrate._git(["status"])
    assert seen["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert seen["timeout"] == orchestrate._GIT_TIMEOUT


# --- H5: --no-commit threads through only to publish, and implies --no-push --

def test_default_runner_appends_no_commit_only_for_publish(monkeypatch):
    seen = {}
    class _R: returncode = 0
    def cap(argv, **k): seen["argv"] = argv; return _R()
    monkeypatch.setattr(orchestrate.subprocess, "run", cap)
    orchestrate._default_runner("publish", "2026-07-12", no_commit=True)
    assert "--no-commit" in seen["argv"]
    orchestrate._default_runner("collect", "2026-07-12", no_commit=True)
    assert "--no-commit" not in seen["argv"]


def test_no_commit_implies_no_push(tmp_path, monkeypatch):
    # a no_commit run must never call _push (committing nothing then pushing = pushing unchanged HEAD)
    monkeypatch.setattr(config_mod := __import__("nbs.config", fromlist=["x"]), "ROOT", tmp_path)
    monkeypatch.setattr(orchestrate, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrate, "_default_email_runner",
                        lambda date, run_id: (0, {"status": "not_published"}))
    monkeypatch.setattr(orchestrate, "decide_action", lambda date, *, force: "full")
    def _pushed(date): raise AssertionError("_push must not run under no_commit")
    monkeypatch.setattr(orchestrate, "_push", _pushed)
    # runner: every stage 'succeeds' and writes the artifact orchestrate checks
    art = {"collect": "candidates.json", "select": "selection.json",
           "stage": "generation.json", "publish": "publish.json"}
    def runner(name, date):
        d = tmp_path / "runs" / date; d.mkdir(parents=True, exist_ok=True)
        payload = {"date": date, "status": "ok"}
        if name == "stage": payload["status"] = "ok"
        if name == "publish": payload = {"date": date, "status": "published", "reason": "ok"}
        (d / art[name]).write_text(json.dumps(payload), encoding="utf-8")
        return 0
    monkeypatch.setattr(orchestrate, "run_dir", lambda date: tmp_path / "runs" / date)
    m = orchestrate.run("2026-07-12", no_commit=True, runner=runner)
    assert m["status"] == "published"
    assert m["stages"]["push"]["status"] == "skipped"
