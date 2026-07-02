import pytest
from nbs import orchestrate, config

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
        def g(args):
            if args[:2]==["ls-remote","origin"]:
                return type("R",(),{"returncode":0,"stdout":stdout})()
            return orig(args)
        monkeypatch.setattr(orchestrate, "_git", g)
    A=_git_in(["rev-parse","HEAD"], root).stdout.strip()
    (root/"b").write_text("b"); _git_in(["add","-A"], root); _git_in(["commit","-qm","B"], root)
    C=_git_in(["rev-parse","HEAD"], root).stdout.strip()
    stub(f"{C}\trefs/heads/main\n"); assert orchestrate._classify_push_failure(C)[0]=="published"     # equal
    stub(f"{A}\trefs/heads/main\n"); assert orchestrate._classify_push_failure(C)[0]=="push_pending"  # behind (direction!)
    stub("0"*40+"\trefs/heads/main\n"); assert orchestrate._classify_push_failure(C)[0]=="push_rejected"  # diverged
    stub(""); assert orchestrate._classify_push_failure(C)[0]=="push_pending"                          # empty/unreachable
