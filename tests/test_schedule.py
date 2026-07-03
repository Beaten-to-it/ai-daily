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

def test_ensure_chrome_ready_returns_pid():
    launched = {"n": 0}
    def fake_launch(): launched["n"] += 1; return 4242
    calls = {"n": 0}
    def fake_probe():           # not ready first call, ready second
        calls["n"] += 1; return calls["n"] >= 2
    h = schedule.ensure_chrome(launcher=fake_launch, probe=fake_probe, timeout=5.0)
    assert h == {"pid": 4242} and launched["n"] == 1

def test_ensure_chrome_degrades_when_bridge_never_ready():
    killed = {"pid": None}
    h = schedule.ensure_chrome(launcher=lambda: 99, probe=lambda: False,
                               killer=lambda handle: killed.__setitem__("pid", handle["pid"]), timeout=0.05)
    assert h is None and killed["pid"] == 99     # timed out -> kill launched chrome, degrade

def test_run_tick_launches_chrome_only_when_reddit_ok(monkeypatch):
    monkeypatch.setattr(schedule, "_probe_free", lambda: True)
    monkeypatch.setattr(schedule, "preflight", lambda root=None, date=None: {"ok": True, "reason": "", "reddit_ok": False})
    launched = {"n": 0}
    schedule.run_tick("2026-07-04",
                      orchestrate_run=lambda d, **k: {"status": "published"},
                      chrome=lambda **k: launched.__setitem__("n", 1) or {"pid": 1})
    assert launched["n"] == 0    # reddit_ok False -> no Chrome

def test_run_tick_tears_down_chrome_pid(monkeypatch):
    monkeypatch.setattr(schedule, "_probe_free", lambda: True)
    monkeypatch.setattr(schedule, "preflight", lambda root=None, date=None: {"ok": True, "reason": "", "reddit_ok": True})
    killed = {"pid": None}
    schedule.run_tick("2026-07-04",
                      orchestrate_run=lambda d, **k: {"status": "published"},
                      chrome=lambda **k: {"pid": 777},
                      kill=lambda h: killed.__setitem__("pid", h["pid"]))
    assert killed["pid"] == 777   # only its own launched pid

def test_check_alert_sends_once_when_unpublished(tmp_path, monkeypatch):
    monkeypatch.setattr(schedule, "_alert_ledger", lambda: tmp_path / "alert_log.csv")
    sent = {"n": 0}
    rc = schedule.check_alert("2026-07-04",
                              is_published=lambda d: False,
                              sender=lambda date, reason: sent.__setitem__("n", sent["n"] + 1),
                              waiter=lambda: None)
    assert rc == 0 and sent["n"] == 1
    # idempotent: second call same day does NOT resend
    schedule.check_alert("2026-07-04", is_published=lambda d: False,
                         sender=lambda date, reason: sent.__setitem__("n", sent["n"] + 1),
                         waiter=lambda: None)
    assert sent["n"] == 1

def test_check_alert_no_send_when_published(tmp_path, monkeypatch):
    monkeypatch.setattr(schedule, "_alert_ledger", lambda: tmp_path / "alert_log.csv")
    sent = {"n": 0}
    rc = schedule.check_alert("2026-07-04", is_published=lambda d: True,
                              sender=lambda date, reason: sent.__setitem__("n", 1), waiter=lambda: None)
    assert rc == 0 and sent["n"] == 0

def test_check_alert_waits_for_busy_run_then_rechecks(tmp_path, monkeypatch):
    # a run is in flight at alert time; after the bounded wait the run has published -> no alert
    monkeypatch.setattr(schedule, "_alert_ledger", lambda: tmp_path / "alert_log.csv")
    state = {"published": False}
    def waiter(): state["published"] = True        # the wait "observes" the run finishing published
    sent = {"n": 0}
    schedule.check_alert("2026-07-04",
                         is_published=lambda d: state["published"],
                         sender=lambda date, reason: sent.__setitem__("n", 1),
                         waiter=waiter)
    assert sent["n"] == 0

def test_send_alert_uses_gmail_primitives_not_run_email(monkeypatch):
    # spec: the alert must NOT use email.run_email (returns not_published on the quiet-day
    # condition -> would send nothing). Verify _send_alert = load_credentials + build_message + _gmail_send.
    from nbs import email as em
    calls = {"build": 0, "send": 0}
    monkeypatch.setattr(em, "load_credentials", lambda path=None: "CREDS")
    monkeypatch.setattr(em, "build_message", lambda *a, **k: calls.__setitem__("build", 1) or {"raw": "x", "message_id": "m"})
    monkeypatch.setattr(em, "_gmail_send", lambda creds, msg, sender: calls.__setitem__("send", 1) or "gid")
    monkeypatch.setattr(em, "run_email", lambda *a, **k: (_ for _ in ()).throw(AssertionError("run_email must not be called")))
    schedule._send_alert("2026-07-04", "failed: boom")
    assert calls == {"build": 1, "send": 1}

def test_main_dispatches_check_alert(monkeypatch):
    seen = {"n": 0}
    monkeypatch.setattr(schedule, "check_alert", lambda date=None: seen.__setitem__("n", 1) or 0)
    rc = schedule.main(["--check-alert", "--date", "2026-07-04"])
    assert rc == 0 and seen["n"] == 1   # main dispatches to check_alert (also proves it's defined)

def test_main_guard_is_last_line():
    # Static regression for the __main__ NameError (Codex R2): running `python3 -m nbs.schedule`
    # executes top-to-bottom and calls main() AT the guard, so the guard must be the file's final
    # code — all defs above it. Import-based tests can't catch a misplaced guard; this can.
    import inspect
    lines = [ln for ln in inspect.getsource(schedule).splitlines() if ln.strip()]
    assert lines[-1].strip() == "raise SystemExit(main())"
    assert lines[-2].strip() == 'if __name__ == "__main__":'
