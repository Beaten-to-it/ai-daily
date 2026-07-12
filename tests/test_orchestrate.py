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
from pathlib import Path

def _git_in(args, cwd): return subprocess.run(["git"]+args, cwd=str(cwd), capture_output=True, text=True)

def _init_repo(tmp_path, monkeypatch):
    # ROOT is a SUBDIR of tmp_path so the bare remote / clone helpers can live OUTSIDE the
    # worktree (else `git add -A` in ROOT would commit the bare remote's internals).
    root = tmp_path/"repo"; root.mkdir()
    monkeypatch.setattr(config, "ROOT", root)
    monkeypatch.setattr(orchestrate, "ROOT", root)
    monkeypatch.setattr(orchestrate, "run_dir", lambda d: root/"runs"/d)
    _git_in(["init","-q"], root); _git_in(["config","user.email","t@t"], root); _git_in(["config","user.name","t"], root)
    (root/"content"/"news").mkdir(parents=True)
    (root/".gitignore").write_text("runs/\n.orchestrate.lock\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm","init"], root)
    return root

def _publish_news(root, date, pushed=None):
    (root/"content"/"news").mkdir(parents=True, exist_ok=True)
    (root/"content"/"news"/f"{date}.md").write_text("x\n", encoding="utf-8")
    _git_in(["add","-A"], root); _git_in(["commit","-qm",f"publish {date}"], root)
    d = root/"runs"/date; d.mkdir(parents=True, exist_ok=True)
    pj = {"date": date, "status": "published"}
    if pushed is not None: pj["pushed"] = pushed
    (d/"publish.json").write_text(json.dumps(pj), encoding="utf-8")

def test_decide_action_full_when_never_published(tmp_path, monkeypatch):
    root=_init_repo(tmp_path, monkeypatch)
    assert orchestrate.decide_action("2026-07-01", force=False) == "full"

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
    assert rc==0 and calls["argv"]==["python3","-m","nbs.collect","--date","2026-07-01"]

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
    # and for a successful publish, commits content/news/<date>.md so head_has_news becomes true.
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
                (root/"content"/"news").mkdir(parents=True, exist_ok=True)
                (root/"content"/"news"/f"{date}.md").write_text("x\n")
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
    assert code == 1   # held -> 1

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
    orchestrate.main(["--date","2026-07-01","--force","--no-push"])
    assert seen["kw"]["force"] is True and seen["kw"]["no_push"] is True

# --- Codex code-review coverage gaps ---

def test_push_pushes_head_not_local_main(tmp_path, monkeypatch):
    # BLOCK: _push must push the actual HEAD commit to origin main, even off a non-main branch
    root, bare = _init_repo_with_remote(tmp_path, monkeypatch)   # on main
    _git_in(["checkout","-q","-b","feature"], root)              # move HEAD off main
    _publish_news(root, "2026-07-01", pushed=False)              # commit news on feature
    head=_git_in(["rev-parse","HEAD"], root).stdout.strip()
    status, sha, _ = orchestrate._push("2026-07-01")
    assert status=="published" and sha==head
    assert _git_in(["ls-remote","origin","refs/heads/main"], root).stdout.split()[0]==head

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
    calls = []
    m = orch.run("2026-07-03", runner=_email_full_runner(orch, "held"),
                 email_runner=lambda d, r: calls.append(1) or (0, {}))
    assert m["status"] == "held" and calls == []
