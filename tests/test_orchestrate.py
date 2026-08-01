import pytest
from nbs import orchestrate, config

@pytest.fixture(autouse=True)
def _no_real_email(monkeypatch):
    # NEVER fork the real `nbs.email` subprocess in unit tests (hermetic — no git/network/send).
    monkeypatch.setattr(orchestrate, "_default_email_runner",
                        lambda date, run_id: (0, {"status": "not_published", "reason": "stubbed"}))

def test_lock_is_exclusive(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrate, "ROOT", tmp_path)
    with orchestrate._lock():
        with pytest.raises(orchestrate.Busy):
            with orchestrate._lock():
                pass
    # released after the outer block — re-acquirable
    with orchestrate._lock():
        pass

import subprocess, json
import sys
from pathlib import Path

def _git_in(args, cwd): return subprocess.run(["git"]+args, cwd=str(cwd), capture_output=True, text=True)

def _init_repo(tmp_path, monkeypatch):
    # ROOT is a SUBDIR of tmp_path so the bare remote / clone helpers can live OUTSIDE the
    # worktree (else `git add -A` in ROOT would commit the bare remote's internals).
    root = tmp_path/"repo"; root.mkdir()
    monkeypatch.setattr(config, "ROOT", root)
    monkeypatch.setattr(orchestrate, "ROOT", root)
    monkeypatch.setattr(orchestrate, "run_dir", lambda d: root/"runs"/d)
    monkeypatch.setattr(orchestrate.publish_mod, "build_verify",
                        lambda gen, content_dir=None: [])
    _git_in(["init","-q"], root); _git_in(["config","user.email","t@t"], root); _git_in(["config","user.name","t"], root)
    (root/"content"/"daily").mkdir(parents=True)
    (root/".gitignore").write_text("runs/\n.orchestrate.lock\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","init"], root)
    return root

def _publish_news(root, date, pushed=None):
    (root/"content"/"daily").mkdir(parents=True, exist_ok=True)
    (root/"content"/"daily"/f"{date}.md").write_text("x\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm",f"publish {date}"], root)
    d = root/"runs"/date; d.mkdir(parents=True, exist_ok=True)
    pj = {"date": date, "status": "published",
          "commit_sha": _git_in(["rev-parse", "HEAD"], root).stdout.strip()}
    if pushed is not None: pj["pushed"] = pushed
    (d/"publish.json").write_text(json.dumps(pj), encoding="utf-8")

def test_decide_action_full_when_never_published(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    assert orchestrate.decide_action("2026-07-01", force=False) == "full"

def test_head_has_daily_uses_new_route(monkeypatch):
    seen = {}
    def fake_git(args, timeout=None):
        seen["args"] = args
        return type("R", (), {"returncode": 0, "stdout": ""})()
    monkeypatch.setattr(orchestrate, "_git", fake_git)
    assert orchestrate._head_has_daily("2026-08-01") is False
    assert seen["args"][-1] == "content/daily/2026-08-01.md"

def test_decide_action_skip_when_pushed(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); _publish_news(root, "2026-07-01", pushed=True)
    assert orchestrate.decide_action("2026-07-01", force=False) == "skip"

def test_decide_action_pushonly_when_published_not_pushed(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); _publish_news(root, "2026-07-01", pushed=False)
    assert orchestrate.decide_action("2026-07-01", force=False) == "push_only"

def test_decide_action_pushonly_when_scratch_wiped(tmp_path, monkeypatch):
    # news committed to HEAD but publish.json gone (runs/ wiped) -> push_only, NOT full
    root=_init_repo(tmp_path, monkeypatch); _publish_news(root, "2026-07-01", pushed=None)
    (root/"runs"/"2026-07-01"/"publish.json").unlink()
    assert orchestrate.decide_action("2026-07-01", force=False) == "push_only"

def test_decide_action_force_is_always_full(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch); _publish_news(root, "2026-07-01", pushed=True)
    assert orchestrate.decide_action("2026-07-01", force=True) == "full"

def _mk(root, date, name, payload):
    d = root/"runs"/date; d.mkdir(parents=True, exist_ok=True)
    (d/f"{ {'collect':'candidates','select':'selection','stage':'generation','publish':'publish'}[name] }.json"
     ).write_text(json.dumps(payload), encoding="utf-8")

def test_stage_ok_rejects_nonzero_rc(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    ok, _ = orchestrate._stage_ok("collect", "2026-07-01", 1)
    assert ok is False

def test_stage_ok_collect_needs_artifact(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    ok, _ = orchestrate._stage_ok("collect", "2026-07-01", 0)   # rc0 but no candidates.json
    assert ok is False
    _mk(root, "2026-07-01", "collect", [])
    assert orchestrate._stage_ok("collect", "2026-07-01", 0)[0] is True   # empty list is OK

def test_stage_ok_stage_status(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    _mk(root, "2026-07-01", "stage", {"date":"2026-07-01","status":"skip-empty"})
    assert orchestrate._stage_ok("stage", "2026-07-01", 0)[0] is True
    _mk(root, "2026-07-01", "stage", {"date":"2026-07-01","status":"weird"})
    assert orchestrate._stage_ok("stage", "2026-07-01", 0)[0] is False

def test_default_runner_shape(monkeypatch):
    calls = {}
    def fake_run(argv, cwd=None, **kw):
        calls["argv"]=argv; calls["cwd"]=cwd
        class R: returncode=0
        return R()
    monkeypatch.setattr(orchestrate.subprocess, "run", fake_run)
    rc = orchestrate._default_runner("collect", "2026-07-01")
    assert rc==0 and calls["argv"]==[sys.executable,"-m","nbs.collect","--date","2026-07-01"]

import os

def _init_repo_with_remote(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)           # root = tmp_path/repo
    bare = tmp_path/"remote.git"                      # SIBLING of root — outside the worktree
    _git_in(["init","--bare","-q",str(bare)], tmp_path)
    _git_in(["remote","add","origin",str(bare)], root)
    _git_in(["branch","-M","main"], root)
    return root, bare

def test_push_success_marks_pushed(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    _publish_news(root, "2026-07-01", pushed=False)
    status, sha, _ = orchestrate._push("2026-07-01")
    assert status=="published" and sha
    st = json.loads((root/"runs"/"2026-07-01"/"publish.json").read_text())
    assert st["pushed"] is True and st["deployed_sha"]==sha

def test_push_rejected_on_divergence(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    # seed origin/main with an unrelated commit so local push is non-fast-forward
    other = tmp_path/"other"; _git_in(["clone","-q",str(bare),str(other)], tmp_path)
    _git_in(["config","user.email","o@o"], other); _git_in(["config","user.name","o"], other)
    (other/"x.txt").write_text("o\n"); _git_in(["add","-A"], other)
    _git_in(["commit","-qm","other"], other); _git_in(["branch","-M","main"], other); _git_in(["push","-q","origin","main"], other)
    _publish_news(root, "2026-07-01", pushed=False)
    status, sha, _ = orchestrate._push("2026-07-01")
    assert status=="push_rejected" and sha is None

def test_mark_pushed_creates_when_absent(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    orchestrate._mark_pushed("2026-07-01", "deadbeef")
    st = json.loads((root/"runs"/"2026-07-01"/"publish.json").read_text())
    assert st["pushed"] is True and st["deployed_sha"]=="deadbeef" and st["status"]=="published"

def test_classify_push_failure_discriminates(tmp_path, monkeypatch):
    # discriminates the merge-base DIRECTION: a remote that is BEHIND (ancestor of HEAD) must be
    # push_pending, not push_rejected. Reversing the is-ancestor args would break this case.
    root=_init_repo(tmp_path, monkeypatch)
    orig = orchestrate._git
    def stub(stdout):
        def g(args, **kw):
            if args[:2]==["ls-remote","origin"]:
                return type("R",(),{"returncode":0,"stdout":stdout})()
            return orig(args, **kw)
        monkeypatch.setattr(orchestrate, "_git", g)
    A=_git_in(["rev-parse","HEAD"], root).stdout.strip()
    (root/"b").write_text("b"); _git_in(["add","-A"], root); _git_in(["commit","-qm","B"], root)
    C=_git_in(["rev-parse","HEAD"], root).stdout.strip()
    stub(f"{C}\trefs/heads/main\n"); assert orchestrate._classify_push_failure(C)[0]=="published"     # equal
    stub(f"{A}\trefs/heads/main\n"); assert orchestrate._classify_push_failure(C)[0]=="push_pending"  # behind (direction!)
    stub("0"*40+"\trefs/heads/main\n"); assert orchestrate._classify_push_failure(C)[0]=="push_rejected"  # diverged
    stub(""); assert orchestrate._classify_push_failure(C)[0]=="push_pending"                          # empty/unreachable

from datetime import datetime

def _fixed_now(): return datetime(2026,7,1,9,0,0, tzinfo=config.KST)

def _fake_runner_factory(root, *, outcomes):
    # outcomes: dict stage-> ("ok"|"rc1"|"held"|"empty"). Writes the artifact a real stage would,
    # and for a successful publish, commits content/daily/<date>.md so head_has_news becomes true.
    def runner(name, date):
        d = root/"runs"/date; d.mkdir(parents=True, exist_ok=True)
        o = outcomes.get(name, "ok")
        if name=="collect":
            (d/"candidates.json").write_text(json.dumps([] if o=="empty" else [{"url":"u"}])); return 0 if o!="rc1" else 1
        if name=="select":
            (d/"selection.json").write_text(json.dumps({"date":date,"items":[],"selected_count":0 if o=="empty" else 3})); return 0 if o!="rc1" else 1
        if name=="stage":
            (d/"generation.json").write_text(json.dumps({"date":date,"status":"skip-empty" if o=="empty" else "ok"})); return 0 if o!="rc1" else 1
        if name=="publish":
            if o=="rc1":                      # crashed publish: leave any stale publish.json, rc!=0
                return 1
            status = "held" if o=="held" else "published"
            (d/"publish.json").write_text(json.dumps({"date":date,"status":status,"commit_sha":"abc"}))
            if status=="published":
                (root/"content"/"daily").mkdir(parents=True, exist_ok=True)
                (root/"content"/"daily"/f"{date}.md").write_text("x\n")
                _git_in(["add","-A"], root); _git_in(["commit","-qm",f"pub {date}"], root)
            return 0
    return runner

def test_run_full_publishes_and_pushes(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    m = orchestrate.run("2026-07-01", runner=_fake_runner_factory(root, outcomes={}), now=_fixed_now())
    assert m["status"]=="published"
    assert m["stages"]["push"]["status"]=="published"
    st = json.loads((root/"runs"/"2026-07-01"/"publish.json").read_text())
    assert st["pushed"] is True
    assert (root/"runs"/"2026-07-01"/"run.json").exists() and m["run_id"] and m["started_at"]

def _spy_push(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(orchestrate, "_push",
                        lambda date: (calls.__setitem__("n", calls["n"]+1) or ("published", "sha", "")))
    return calls

def test_run_held_does_not_push(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    pushes = _spy_push(monkeypatch)
    m = orchestrate.run("2026-07-01", runner=_fake_runner_factory(root, outcomes={"publish":"held"}), now=_fixed_now())
    assert m["status"]=="held" and m["stages"]["push"]["status"]=="skipped" and pushes["n"]==0


def test_run_empty_generation_is_held_before_validate_or_publish(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    calls = []
    runner = _fake_runner_factory(root, outcomes={"stage": "empty"})
    m = orchestrate.run(
        "2026-07-01", prepare_only=True,
        runner=lambda name, date: calls.append(name) or runner(name, date),
        now=_fixed_now(),
    )
    assert m["status"] == "held" and calls == ["collect", "select", "stage"]
    assert m["stages"]["validate"]["status"] == "skipped"
    assert m["stages"]["publish"]["status"] == "skipped"

def test_run_publish_crash_not_reported_published(tmp_path, monkeypatch):
    # a stale publish.json{published} + a crashed publish (rc!=0) must be FAILED, never pushed
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    d = root/"runs"/"2026-07-01"; d.mkdir(parents=True, exist_ok=True)
    (d/"publish.json").write_text(json.dumps({"date":"2026-07-01","status":"published"}))  # stale from prior run
    pushes = _spy_push(monkeypatch)
    m = orchestrate.run("2026-07-01", runner=_fake_runner_factory(root, outcomes={"publish":"rc1"}), now=_fixed_now())
    assert m["status"]=="failed" and m["stages"]["publish"]["status"]=="failed" and pushes["n"]==0

def test_run_aborts_on_stage_failure(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    m = orchestrate.run("2026-07-01", runner=_fake_runner_factory(root, outcomes={"select":"rc1"}), now=_fixed_now())
    assert m["status"]=="failed" and m["stages"]["select"]["status"]=="failed"
    assert m["stages"]["stage"]["status"]=="skipped"   # never ran

def test_run_skips_when_already_pushed(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    orchestrate.run("2026-07-01", runner=_fake_runner_factory(root, outcomes={}), now=_fixed_now())  # publishes+pushes
    called = {"n":0}
    def spy(name, date): called["n"]+=1; return 0
    m = orchestrate.run("2026-07-01", runner=spy, now=_fixed_now())
    assert m["status"]=="skipped" and called["n"]==0   # no stage ran

def test_run_pushonly_recovers_without_regen(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    # simulate published-locally-but-not-pushed: commit news, publish.json pushed=false, origin empty
    _publish_news(root, "2026-07-01", pushed=False)
    called = {"n":0}
    def spy(name, date): called["n"]+=1; return 0
    m = orchestrate.run("2026-07-01", runner=spy, now=_fixed_now())
    assert m["status"]=="published" and called["n"]==0   # push-only, no regeneration
    assert json.loads((root/"runs"/"2026-07-01"/"publish.json").read_text())["pushed"] is True

def test_run_no_push_flag(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    pushes = _spy_push(monkeypatch)
    m = orchestrate.run("2026-07-01", runner=_fake_runner_factory(root, outcomes={}), no_push=True, now=_fixed_now())
    assert m["status"]=="published" and m["stages"]["push"]["status"]=="skipped" and pushes["n"]==0
    assert json.loads((root/"runs"/"2026-07-01"/"publish.json").read_text()).get("pushed") is None

def test_run_pushonly_respects_no_push(tmp_path, monkeypatch):
    # advisor: --no-push MUST be honored on the push_only recovery path too, else a dry-run
    # smoke on a published-locally-not-pushed day pushes to the real origin.
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    _publish_news(root, "2026-07-01", pushed=False)   # recovery state
    m = orchestrate.run("2026-07-01", runner=(lambda n, d: 0), no_push=True, now=_fixed_now())
    assert m["stages"]["push"]["status"]=="skipped"
    assert _git_in(["ls-remote","origin","refs/heads/main"], root).stdout.strip()==""   # NOT pushed

def test_run_rejects_bad_date(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    m = orchestrate.run("../evil", now=_fixed_now())
    assert m["status"]=="failed" and not (tmp_path/"evil").exists()

def test_main_returns_exit_code(tmp_path, monkeypatch, capsys):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    monkeypatch.setattr(orchestrate, "run", lambda date, **kw: {"status":"held","stages":{},"reason":"floor","date":date})
    code = orchestrate.main(["--date","2026-07-01"])
    assert code == 2   # held/failed -> 2

def test_main_defaults_to_today(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    seen = {}
    monkeypatch.setattr(orchestrate, "run", lambda date, **kw: seen.update(date=date, kw=kw) or {"status":"published","stages":{},"reason":"","date":date})
    monkeypatch.setattr(orchestrate, "_today", lambda: "2026-07-09")
    orchestrate.main([])
    assert seen["date"]=="2026-07-09" and seen["kw"]["force"] is False and seen["kw"]["no_push"] is False

def test_main_passes_flags(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    seen = {}
    monkeypatch.setattr(orchestrate, "run", lambda date, **kw: seen.update(kw=kw) or {"status":"published","stages":{},"reason":"","date":date})
    orchestrate.main(["--date","2026-07-01","--force","--no-push","--shadow"])
    assert seen["kw"]["force"] is True and seen["kw"]["no_push"] is True
    assert seen["kw"]["shadow"] is True and seen["kw"]["prepare_only"] is False


def test_main_publish_only_not_ready_exit_code(tmp_path, monkeypatch):
    _init_repo(tmp_path, monkeypatch)
    seen = {}
    monkeypatch.setattr(
        orchestrate,
        "run",
        lambda date, **kw: seen.update(kw=kw) or
        {"status":"not_ready","stages":{},"reason":"checkpoint missing","date":date},
    )
    assert orchestrate.main(["--date","2026-07-01","--publish-only"]) == 4
    assert seen["kw"]["publish_only"] is True


def test_prepare_only_never_calls_publish_push_or_email(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    calls=[]; emails=[]
    base=_fake_runner_factory(root, outcomes={})
    m=orchestrate.run(
        "2026-08-01",
        prepare_only=True,
        shadow=True,
        runner=lambda name, date: calls.append(name) or base(name, date),
        email_runner=lambda date, run_id: emails.append(date) or (0, {"status":"sent"}),
        now=_fixed_now(),
    )
    assert m["status"] == "prepared"
    assert calls == ["collect", "select", "stage"]
    assert m["stages"]["validate"]["status"] == "ok"
    assert m["stages"]["publish"]["status"] == "skipped"
    assert m["stages"]["push"]["status"] == "skipped" and emails == []
    checkpoint=json.loads((root/"runs"/"2026-08-01"/"checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["date"] == "2026-08-01" and checkpoint["status"] == "validated"
    assert checkpoint["input_hash"] and checkpoint["git_head"]


def test_publish_only_requires_validated_checkpoint(tmp_path, monkeypatch):
    _init_repo(tmp_path, monkeypatch)
    calls=[]
    m=orchestrate.run("2026-08-01", publish_only=True,
                      runner=lambda name, date: calls.append(name) or 0, now=_fixed_now())
    assert m["status"] == "not_ready" and calls == []


def test_publish_only_resumes_at_publish_from_matching_checkpoint(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    base=_fake_runner_factory(root, outcomes={})
    assert orchestrate.run("2026-08-01", prepare_only=True, runner=base, now=_fixed_now())["status"] == "prepared"
    calls=[]
    m=orchestrate.run("2026-08-01", publish_only=True, no_push=True,
                      runner=lambda name, date: calls.append(name) or base(name, date), now=_fixed_now())
    assert m["status"] == "published" and calls == ["publish"]
    assert m["stages"]["validate"]["status"] == "ok"


def test_publish_only_rejects_changed_input_or_git_head(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    base=_fake_runner_factory(root, outcomes={})
    assert orchestrate.run("2026-08-01", prepare_only=True, runner=base, now=_fixed_now())["status"] == "prepared"
    generation=root/"runs"/"2026-08-01"/"generation.json"
    generation.write_text(generation.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert orchestrate.run("2026-08-01", publish_only=True, runner=base, now=_fixed_now())["status"] == "not_ready"
    assert orchestrate.run("2026-08-02", prepare_only=True,
                           runner=_fake_runner_factory(root, outcomes={}), now=_fixed_now())["status"] == "prepared"
    (root/"head-change").write_text("x", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","head change"], root)
    assert orchestrate.run("2026-08-02", publish_only=True, runner=base, now=_fixed_now())["status"] == "not_ready"


def test_publish_only_retry_pushes_existing_publish_commit(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    base = _fake_runner_factory(root, outcomes={})
    assert orchestrate.run("2026-08-01", prepare_only=True,
                           runner=base, now=_fixed_now())["status"] == "prepared"
    _publish_news(root, "2026-08-01", pushed=False)
    calls = []
    monkeypatch.setattr(
        orchestrate,
        "_push",
        lambda date: calls.append(date) or ("published", "deployed", "retry recovery"),
    )
    manifest = orchestrate.run(
        "2026-08-01", publish_only=True,
        runner=lambda name, date: (_ for _ in ()).throw(AssertionError("must not regenerate")),
        email_runner=lambda date, run_id: (0, {"status": "already_sent"}),
        now=_fixed_now(),
    )
    assert manifest["status"] == "published" and calls == ["2026-08-01"]
    assert manifest["stages"]["push"]["status"] == "published"


def test_prepare_checkpoint_runs_hugo_against_staging(tmp_path, monkeypatch):
    root = _init_repo(tmp_path, monkeypatch)
    date = "2026-08-01"
    directory = root / "runs" / date
    (directory / "staging").mkdir(parents=True)
    (directory / "generation.json").write_text(
        json.dumps({"date": date, "status": "ok", "results": []}), encoding="utf-8"
    )
    seen = {}
    monkeypatch.setattr(
        orchestrate.publish_mod,
        "build_verify",
        lambda gen, content_dir=None: seen.update(gen=gen, content_dir=content_dir) or [],
    )
    ok, reason, checkpoint = orchestrate._prepare_checkpoint(date, _fixed_now().isoformat())
    assert ok, reason
    assert seen["content_dir"] == directory / "staging"
    assert checkpoint["validation"]["hugo"] == "ok"


def test_prepare_checkpoint_rejects_dirty_site_configuration(tmp_path, monkeypatch):
    root = _init_repo(tmp_path, monkeypatch)
    date = "2026-08-01"
    directory = root / "runs" / date
    (directory / "staging").mkdir(parents=True)
    (directory / "generation.json").write_text(
        json.dumps({"date": date, "status": "ok", "results": []}), encoding="utf-8"
    )
    (root / "hugo.toml").write_text('baseURL = "https://example.test/"\n', encoding="utf-8")
    ok, reason, checkpoint = orchestrate._prepare_checkpoint(date, _fixed_now().isoformat())
    assert not ok and "site configuration dirty" in reason and checkpoint is None

# --- Codex code-review coverage gaps ---

def test_push_rejects_non_main_branch(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)   # on main
    _git_in(["checkout","-q","-b","feature"], root)              # move HEAD off main
    _publish_news(root, "2026-07-01", pushed=False)              # commit news on feature
    status, sha, reason = orchestrate._push("2026-07-01")
    assert status=="push_rejected" and sha is None and "main" in reason
    assert _git_in(["ls-remote","origin","refs/heads/main"], root).stdout.strip()==""


def test_publish_only_without_date_adopts_today_or_yesterday_checkpoint(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    for date in ("2026-08-01", "2026-08-02"):
        directory=root/"runs"/date; directory.mkdir(parents=True)
        (directory/"checkpoint.json").write_text(json.dumps({
            "version": 1, "date": date, "status": "validated"
        }), encoding="utf-8")
    assert orchestrate._latest_checkpoint_date("2026-08-02") == "2026-08-02"
    (root/"runs"/"2026-08-02"/"checkpoint.json").unlink()
    assert orchestrate._latest_checkpoint_date("2026-08-02") == "2026-08-01"
    assert orchestrate._latest_checkpoint_date("2026-08-03") is None


def test_main_publish_only_without_date_uses_latest_checkpoint(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    directory=root/"runs"/"2026-08-01"; directory.mkdir(parents=True)
    (directory/"checkpoint.json").write_text(json.dumps({
        "version": 1, "date": "2026-08-01", "status": "validated"
    }), encoding="utf-8")
    seen = {}
    monkeypatch.setattr(orchestrate, "_today", lambda: "2026-08-02")
    monkeypatch.setattr(orchestrate, "run", lambda date, **kw: seen.update(date=date) or {
        "status":"published", "stages":{}, "reason":"", "date":date
    })
    assert orchestrate.main(["--publish-only"]) == 0
    assert seen["date"] == "2026-08-01"


def test_site_tree_gate_includes_section_indexes(monkeypatch):
    calls = []
    def fake_git(args, timeout=None):
        calls.append(args)
        return type("R", (), {"returncode": 0, "stdout": ""})()
    monkeypatch.setattr(orchestrate, "_git", fake_git)
    assert orchestrate._site_tree_ready() == (True, "")
    assert "content/daily/_index.md" in calls[0]
    assert "content/articles/_index.md" in calls[0]


def test_site_tree_gate_rejects_uninitialized_theme(monkeypatch):
    def fake_git(args, timeout=None):
        if args[:2] == ["ls-files", "--stage"]:
            return type("R", (), {"returncode": 0, "stdout": "160000 abcdef 0\tthemes/PaperMod\n"})()
        if args[:2] == ["submodule", "status"]:
            return type("R", (), {"returncode": 0, "stdout": "-abcdef themes/PaperMod\n"})()
        return type("R", (), {"returncode": 0, "stdout": ""})()
    monkeypatch.setattr(orchestrate, "_git", fake_git)
    assert orchestrate._site_tree_ready() == (
        False, "PaperMod submodule is not initialized at the pinned commit"
    )

def test_decide_action_full_when_manifest_held(tmp_path, monkeypatch):
    # MAJOR: news in HEAD but publish.json says held (a later --force run) -> full, not push_only
    root=_init_repo(tmp_path, monkeypatch); _publish_news(root, "2026-07-01", pushed=None)
    (root/"runs"/"2026-07-01"/"publish.json").write_text(json.dumps({"date":"2026-07-01","status":"held"}))
    assert orchestrate.decide_action("2026-07-01", force=False) == "full"

def test_run_busy_when_locked(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    with orchestrate._lock():
        m = orchestrate.run("2026-07-01", runner=(lambda n,d:0), now=_fixed_now())
    assert m["status"]=="busy" and not (root/"runs"/"2026-07-01"/"run.json").exists()

def test_main_busy_exit_code(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(orchestrate, "run", lambda date, **kw: {"status":"busy","stages":{},"reason":"x","date":date})
    assert orchestrate.main(["--date","2026-07-01"]) == 3

def test_run_force_republishes_already_published(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    orchestrate.run("2026-07-01", runner=_fake_runner_factory(root, outcomes={}), now=_fixed_now())  # published+pushed
    calls={"n":0}
    base=_fake_runner_factory(root, outcomes={})
    def counting(name,date): calls["n"]+=1; return base(name,date)
    m = orchestrate.run("2026-07-01", force=True, runner=counting, now=_fixed_now())
    assert m["status"]=="published" and calls["n"]==4   # force re-ran the full pipeline (would skip without force)

def test_run_pushonly_reports_push_pending(tmp_path, monkeypatch):
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)
    _publish_news(root, "2026-07-01", pushed=False)   # push_only state
    monkeypatch.setattr(orchestrate, "_push", lambda date: ("push_pending", None, "network"))
    m = orchestrate.run("2026-07-01", runner=(lambda n,d:0), now=_fixed_now())
    assert m["status"]=="push_pending" and m["stages"]["push"]["status"]=="push_pending"


# --- P3b email seam ---------------------------------------------------------

def _email_full_runner(orch, publish_status):
    def fake_runner(name, date):
        orch.run_dir(date).mkdir(parents=True, exist_ok=True)
        art = {"collect": "candidates.json", "select": "selection.json",
               "stage": "generation.json", "publish": "publish.json"}[name]
        payload = {"status": "ok"} if name == "stage" else (
            {"status": publish_status, "reason": "r"} if name == "publish" else {"x": 1})
        (orch.run_dir(date) / art).write_text(json.dumps(payload)); return 0
    return fake_runner

def test_email_called_on_published(tmp_path, monkeypatch):
    from nbs import orchestrate as orch, config
    monkeypatch.setattr(config, "ROOT", tmp_path); monkeypatch.setattr(orch, "ROOT", tmp_path)
    monkeypatch.setattr(orch, "run_dir", lambda d: tmp_path / "runs" / d)
    monkeypatch.setattr(orch, "decide_action", lambda date, *, force: "full")
    monkeypatch.setattr(orch, "_prepare_checkpoint", lambda date, validated_at: (True, "", {}))
    monkeypatch.setattr(orch, "_push", lambda date: ("published", "abc", ""))
    calls = []
    m = orch.run("2026-07-03", runner=_email_full_runner(orch, "published"),
                 email_runner=lambda d, r: calls.append((d, r)) or (0, {"status": "sent"}))
    assert m["status"] == "published"
    assert len(calls) == 1 and calls[0][0] == "2026-07-03"
    assert m["stages"]["email"]["status"] == "sent"

def test_email_failure_maps_to_failed_and_does_not_demote(tmp_path, monkeypatch):
    from nbs import orchestrate as orch, config
    monkeypatch.setattr(config, "ROOT", tmp_path); monkeypatch.setattr(orch, "ROOT", tmp_path)
    monkeypatch.setattr(orch, "run_dir", lambda d: tmp_path / "runs" / d)
    monkeypatch.setattr(orch, "decide_action", lambda date, *, force: "skip")
    m = orch.run("2026-07-03", email_runner=lambda d, r: (1, {"status": "error", "reason": "boom"}))
    assert m["status"] == "skipped"                       # NOT demoted
    assert m["stages"]["email"]["status"] == "failed"     # rc!=0 normalized to failed (P3d alert)

def test_email_not_called_on_no_push(tmp_path, monkeypatch):
    from nbs import orchestrate as orch, config
    monkeypatch.setattr(config, "ROOT", tmp_path); monkeypatch.setattr(orch, "ROOT", tmp_path)
    monkeypatch.setattr(orch, "run_dir", lambda d: tmp_path / "runs" / d)
    monkeypatch.setattr(orch, "decide_action", lambda date, *, force: "skip")
    calls = []
    m = orch.run("2026-07-03", no_push=True, email_runner=lambda d, r: calls.append(1) or (0, {}))
    assert m["status"] == "skipped" and calls == []

def test_email_not_called_on_held(tmp_path, monkeypatch):
    from nbs import orchestrate as orch, config
    monkeypatch.setattr(config, "ROOT", tmp_path); monkeypatch.setattr(orch, "ROOT", tmp_path)
    monkeypatch.setattr(orch, "run_dir", lambda d: tmp_path / "runs" / d)
    monkeypatch.setattr(orch, "decide_action", lambda date, *, force: "full")
    monkeypatch.setattr(orch, "_prepare_checkpoint", lambda date, validated_at: (True, "", {}))
    calls = []
    m = orch.run("2026-07-03", runner=_email_full_runner(orch, "held"),
                 email_runner=lambda d, r: calls.append(1) or (0, {}))
    assert m["status"] == "held" and calls == []
