import os, subprocess, pytest
from pathlib import Path
from nbs import schedule
from nbs import orchestrate

def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)

def _repo(tmp_path):
    r = tmp_path / "repo"
    (r / "content" / "news").mkdir(parents=True)
    (r / "data").mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "user.email", "t@t")
    (r / "data" / "published.csv").write_text("header\n")
    _git(r, "add", "-A"); _git(r, "commit", "-q", "-m", "base")
    return r

def test_preflight_ok_on_clean_repo_with_identity(tmp_path, monkeypatch):
    r = _repo(tmp_path)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(schedule, "_git_credentials_present", lambda: True)
    res = schedule.preflight(root=r, date="2026-07-04")
    assert res["ok"] is True and res["reddit_ok"] is True

def test_preflight_hard_fails_on_dirty_writeset(tmp_path, monkeypatch):
    r = _repo(tmp_path)
    monkeypatch.setattr(schedule, "_git_credentials_present", lambda: True)
    (r / "content" / "news" / "2026-07-04.md").write_text("dirty")  # untracked write-set file for THIS date
    res = schedule.preflight(root=r, date="2026-07-04")
    assert res["ok"] is False and "write-set" in res["reason"]

def test_preflight_ignores_other_date_dirty(tmp_path, monkeypatch):
    # spec §241: write-set is date-scoped. An unrelated day's dirty draft must NOT abort today.
    r = _repo(tmp_path)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(schedule, "_git_credentials_present", lambda: True)
    (r / "content" / "news" / "2026-07-05.md").write_text("dirty next-day draft")
    res = schedule.preflight(root=r, date="2026-07-04")
    assert res["ok"] is True

def test_preflight_ignores_same_date_non_writeset(tmp_path, monkeypatch):
    # news write-set is EXACT `{date}.md`; a same-date-PREFIX file (`{date}-notes.md`) is NOT
    # in the write-set rollback touches, so it must not abort (mirrors publish.date_writeset).
    r = _repo(tmp_path)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(schedule, "_git_credentials_present", lambda: True)
    (r / "content" / "news" / "2026-07-04-notes.md").write_text("scratch, not the published news file")
    res = schedule.preflight(root=r, date="2026-07-04")
    assert res["ok"] is True

def test_preflight_soft_when_no_display(tmp_path, monkeypatch):
    r = _repo(tmp_path)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(schedule, "_git_credentials_present", lambda: True)
    res = schedule.preflight(root=r, date="2026-07-04")
    assert res["ok"] is True and res["reddit_ok"] is False  # soft: publish still proceeds

def test_preflight_hard_fails_on_missing_identity(tmp_path, monkeypatch):
    # Neutralize the GLOBAL/SYSTEM gitconfig so a real dev machine's identity can't leak in and
    # mask the missing-identity branch under test.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
    r = tmp_path / "repo"
    (r / "content" / "news").mkdir(parents=True)
    (r / "data").mkdir()
    _git(r, "init", "-q")
    (r / "data" / "published.csv").write_text("header\n")
    _git(r, "add", "-A")
    # commit with a one-off author (-c) so the repo itself never gets a LOCAL user.name/email —
    # keeps the write-set clean while leaving identity genuinely unset for preflight to detect.
    _git(r, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "base")
    monkeypatch.setattr(schedule, "_git_credentials_present", lambda: True)
    res = schedule.preflight(root=r, date="2026-07-04")
    assert res["ok"] is False
    assert "identity" in res["reason"]

def test_preflight_hard_fails_on_missing_credentials(tmp_path, monkeypatch):
    r = _repo(tmp_path)
    monkeypatch.setattr(schedule, "_git_credentials_present", lambda: False)
    res = schedule.preflight(root=r, date="2026-07-04")
    assert res["ok"] is False
    assert "git-credentials" in res["reason"]

def test_preflight_hard_fails_on_dirty_post(tmp_path, monkeypatch):
    r = _repo(tmp_path)
    monkeypatch.setattr(schedule, "_git_credentials_present", lambda: True)
    (r / "content" / "posts").mkdir(parents=True)
    (r / "content" / "posts" / "2026-07-04-slug.md").write_text("dirty post")
    res = schedule.preflight(root=r, date="2026-07-04")
    assert res["ok"] is False and "write-set" in res["reason"]

def test_preflight_fails_closed_on_git_status_error(tmp_path, monkeypatch):
    r = _repo(tmp_path)
    monkeypatch.setattr(schedule, "_git_credentials_present", lambda: True)
    real_git = schedule._git
    def fake_git(root, *args):
        if args and args[0] == "status":
            return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="boom")
        return real_git(root, *args)
    monkeypatch.setattr(schedule, "_git", fake_git)
    res = schedule.preflight(root=r, date="2026-07-04")
    assert res["ok"] is False
    assert "git status failed" in res["reason"]

def test_run_tick_busy_probe_exits_without_running(monkeypatch):
    called = {"run": 0}
    monkeypatch.setattr(schedule, "_probe_free", lambda: False)   # a run holds the lock
    monkeypatch.setattr(schedule, "preflight", lambda root=None, date=None: {"ok": True, "reason": "", "reddit_ok": True})
    rc = schedule.run_tick("2026-07-04", orchestrate_run=lambda *a, **k: called.__setitem__("run", 1) or {})
    assert rc == 3 and called["run"] == 0    # busy exit code, orchestrate never called

def test_run_tick_preflight_hard_fail_aborts(monkeypatch):
    monkeypatch.setattr(schedule, "_probe_free", lambda: True)
    monkeypatch.setattr(schedule, "preflight", lambda root=None, date=None: {"ok": False, "reason": "write-set dirty", "reddit_ok": False})
    ran = {"n": 0}
    rc = schedule.run_tick("2026-07-04", orchestrate_run=lambda *a, **k: ran.__setitem__("n", 1) or {})
    assert rc != 0 and ran["n"] == 0

def test_run_tick_delegates_and_propagates_exit(monkeypatch):
    monkeypatch.setattr(schedule, "_probe_free", lambda: True)
    # reddit_ok=False so that after Task 3 wires Chrome in, this test never launches a real one.
    monkeypatch.setattr(schedule, "preflight", lambda root=None, date=None: {"ok": True, "reason": "", "reddit_ok": False})
    rc = schedule.run_tick("2026-07-04",
                           orchestrate_run=lambda date, **k: {"status": "published"})
    assert rc == 0   # orchestrate _STATUS_EXIT["published"] == 0
