import os, subprocess, pytest
from pathlib import Path
from nbs import schedule

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
