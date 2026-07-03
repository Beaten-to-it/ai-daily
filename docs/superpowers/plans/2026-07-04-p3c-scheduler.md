# P3c Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an unattended daily-publish layer on top of P3a `orchestrate` — a systemd user timer fires a thin `nbs/schedule.py` driver that runs preflight, ensures Chrome for Reddit (degrading safely), delegates to `orchestrate.run`, and sends a once-a-day quiet-day alert if nothing published.

**Architecture:** `nbs/schedule.py` is a thin driver (zero publish logic — reuses `orchestrate.run` and `email.py` primitives). Each timer tick: non-blocking flock probe (busy → exit, no Chrome) → `preflight()` gate → `ensure_chrome()` (soft/degrade) → `orchestrate.run(today)` → teardown only its own Chrome PID. A separate 12:00 timer runs `--check-alert`: git-authoritative "published today?" (`email.published`), and if not (after a bounded wait for any in-flight run) sends one alert via `email.py`'s Gmail primitives with a separate alert-ledger. systemd units live in `deploy/systemd/` and are installed by `scripts/install_scheduler.sh`.

**Tech Stack:** Python 3 stdlib only (subprocess, fcntl, shutil, csv, os, time); reuse `nbs/orchestrate.py`, `nbs/email.py`, `nbs/config.py`; systemd user units; WSLg headful Chrome + `opencli` Browser-Bridge.

## Global Constraints

- **`python3`** only (no bare `python`). pip needs `--break-system-packages`.
- **Spec SSOT:** `docs/superpowers/specs/2026-07-01-nbs-news-blog-design.md` §15 "확정 (P3c…)". This plan implements that block.
- **Reddit invariant:** Reddit/Chrome must NEVER block or hang the daily publish. Every Chrome/opencli step is bounded and degrades to RSS+X on failure.
- **preflight hard-set = only what orchestrate can't self-handle:** write-set clean + git identity/creds. `hugo`/deps/network/display are SOFT (orchestrate's per-stage rc handles a real full-run dep miss; push_only/skip recovery must not be blocked by them).
- **Alert must NOT use `email.run_email()`** — it returns `not_published` on exactly the quiet-day condition. Reuse only `email.load_credentials` + `email.build_message` + `email._gmail_send` with a separate body and a separate alert-ledger.
- **Timezone:** OnCalendar lines pin `Asia/Seoul`; date math uses `config.KST`. No system-TZ preflight check.
- **flock:** the single lock is `orchestrate`'s `ROOT/.orchestrate.lock` (fd-flock, crash-safe). schedule.py probes the same lock; it never introduces a second lock.
- **Tests:** network/Chrome-free. Use injected seams (runner/launcher/probe/sender) + real temp git repos (mirror `tests/test_orchestrate.py`). Run tests via `python3 -c "import pytest,sys; sys.exit(pytest.main([...]))"` (the bare `pytest` binary is hook-blocked in this env).
- **Commits:** one per task, end message with the repo's Co-Authored-By + Claude-Session trailers.

---

## File Structure

- **Create `nbs/schedule.py`** — the unattended driver. Public surface: `preflight(root=config.ROOT) -> dict`, `ensure_chrome(*, launcher, probe, killer, timeout=30.0) -> dict | None`, `run_tick(date=None, *, orchestrate_run=orchestrate.run, chrome=ensure_chrome, pre=preflight) -> int`, `check_alert(date=None, *, is_published=email.published, sender=_send_alert, waiter=_wait_for_lock) -> int`, `main(argv=None) -> int`.
- **Create `tests/test_schedule.py`** — unit tests, network/Chrome-free.
- **Create `deploy/systemd/ai-daily.service`, `ai-daily.timer`, `ai-daily-alert.service`, `ai-daily-alert.timer`** — versioned unit templates.
- **Create `scripts/install_scheduler.sh`** — copies units to `~/.config/systemd/user/`, enables, `loginctl enable-linger`, prints Chrome-profile one-time setup.
- **No changes** to `orchestrate.py` / `email.py` (reuse only; if a needed primitive turns out private-and-unstable, promote it in the task that needs it, but the named primitives already exist).

---

### Task 1: `preflight()` — hard/soft environment gate

**Files:**
- Create: `nbs/schedule.py` (module + `preflight`)
- Test: `tests/test_schedule.py`

**Interfaces:**
- Consumes: `config.ROOT`; `git` via `subprocess`.
- Produces: `preflight(root=config.ROOT) -> dict` returning `{"ok": bool, "reason": str, "reddit_ok": bool}`. `ok=False` only on a HARD failure (dirty write-set, or missing git identity/creds). `reddit_ok=False` when the WSLg display env is absent (soft — publish proceeds without Reddit).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schedule.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_schedule.py']))"`
Expected: FAIL — `ModuleNotFoundError: No module named 'nbs.schedule'` (or `AttributeError: preflight`).

- [ ] **Step 3: Write minimal implementation**

```python
# nbs/schedule.py
import os, subprocess, shutil
from pathlib import Path
from . import config

def _git(root, *args):
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True)

def _git_credentials_present():
    return (Path.home() / ".git-credentials").exists()

def _display_present():
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

def _writeset(date):
    # EXACTLY mirror publish.date_writeset (nbs/publish.py:98-106) — the set rollback touches.
    # Broader (e.g. `{date}*`) would abort today over a same-date-PREFIX non-write-set draft;
    # narrower would miss a file rollback clobbers. posts are `{date}-*.md`; news/usecase/ax are
    # the exact `{date}.md`; published.csv (date's rows rewritten by rollback) is always included.
    return [f"content/posts/{date}-*.md", f"content/news/{date}.md",
            f"content/usecase/{date}.md", f"content/ax/{date}.md", "data/published.csv"]

def preflight(root=config.ROOT, date=None):
    date = date or "0000-00-00"   # caller (run_tick) passes the tick date; guard against None
    # HARD (only what orchestrate can't cleanly self-handle):
    # 1) THIS date's write-set must be clean — orchestrate's rollback `git checkout` would else
    #    destroy the user's uncommitted changes (spec §172).
    dirty = _git(root, "status", "--porcelain", "--", *_writeset(date)).stdout.strip()
    if dirty:
        return {"ok": False, "reason": f"write-set dirty: {dirty.splitlines()[0]}", "reddit_ok": False}
    # 2) git identity + credentials (commit/push preconditions; push_only path needs these too).
    name = _git(root, "config", "user.name").stdout.strip()
    email = _git(root, "config", "user.email").stdout.strip()
    if not (name and email):
        return {"ok": False, "reason": "git identity missing", "reddit_ok": False}
    if not _git_credentials_present():
        return {"ok": False, "reason": "~/.git-credentials missing", "reddit_ok": False}
    # SOFT (warn, never abort): a real hugo/deps miss is caught cleanly by orchestrate's
    # per-stage rc, and push_only/skip recovery doesn't need hugo — so these never gate the tick.
    if not shutil.which("hugo"):
        print("[preflight] warn: hugo not on PATH (a full run's build-verify would fail this tick)")
    # display absence only disables Reddit (publish proceeds RSS+X).
    return {"ok": True, "reason": "", "reddit_ok": _display_present()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_schedule.py']))"`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add nbs/schedule.py tests/test_schedule.py
git commit -m "feat(p3c): preflight hard/soft gate (write-set clean + git identity)"
```

---

### Task 2: driver tick — flock probe → preflight → `orchestrate.run`

**Files:**
- Modify: `nbs/schedule.py` (add `_probe_free`, `run_tick`, `main`)
- Test: `tests/test_schedule.py`

**Interfaces:**
- Consumes: `orchestrate._lock`, `orchestrate.Busy`, `orchestrate.run`, `orchestrate._today`, `orchestrate._STATUS_EXIT`.
- Produces: `run_tick(date=None, *, orchestrate_run=orchestrate.run, pre=preflight) -> int` (exit code); `main(argv=None) -> int` dispatching `--check-alert` (Task 4) vs a tick. Chrome wiring is added in Task 3 (this task runs with Reddit off).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_schedule.py
from nbs import orchestrate

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
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_schedule.py','-k','run_tick']))"`
Expected: FAIL — `AttributeError: run_tick`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to nbs/schedule.py — insert ABOVE the `if __name__ == "__main__"` guard (keep guard last)
import argparse
from . import orchestrate

BUSY_EXIT = 3   # matches orchestrate._STATUS_EXIT["busy"]

def _probe_free():
    # Non-blocking probe of orchestrate's lock: acquire-and-release. If busy, a run is in
    # progress -> caller must not launch Chrome. Tiny race (probe releases before
    # orchestrate.run re-acquires) is covered by no-manual-run-in-window; if it still races,
    # orchestrate.run returns status "busy" and run_tick propagates BUSY_EXIT anyway.
    try:
        with orchestrate._lock():
            return True
    except orchestrate.Busy:
        return False

def run_tick(date=None, *, orchestrate_run=None, pre=None):
    # IMPORTANT: default seams are None and resolved to module globals at CALL time, so that
    # `monkeypatch.setattr(schedule, "preflight", ...)` in tests actually takes effect. A
    # keyword default like `pre=preflight` binds the ORIGINAL function object at def time and
    # would ignore the monkeypatch (and on the dev box run real preflight -> launch real Chrome).
    orchestrate_run = orchestrate_run or orchestrate.run
    pre = pre or preflight
    date = date or orchestrate._today()
    if not _probe_free():
        return BUSY_EXIT
    pf = pre(root=config.ROOT, date=date)
    if not pf["ok"]:
        # hard fail: abort THIS tick (no partial writes); next tick retries.
        print(f"[preflight] abort: {pf['reason']}")
        return 2
    manifest = orchestrate_run(date)
    status = (manifest or {}).get("status", "failed")
    return orchestrate._STATUS_EXIT.get(status, 1)

def main(argv=None):
    ap = argparse.ArgumentParser(prog="schedule")
    ap.add_argument("--date", default=None)
    ap.add_argument("--check-alert", action="store_true")
    a = ap.parse_args(argv)
    if a.check_alert:
        return check_alert(a.date)     # defined in Task 4
    return run_tick(a.date)

if __name__ == "__main__":
    raise SystemExit(main())
```

**⚠️ PLACEMENT (critical — Codex R1 #1):** The `if __name__ == "__main__": raise SystemExit(main())` guard MUST be the **final two lines of the file**. When run as `python3 -m nbs.schedule`, Python executes top-to-bottom and hits the guard *in place* — so anything the guard's `main()` transitively calls (`check_alert` from Task 4, `ensure_chrome`/`_kill` from Task 3) must already be defined **above** the guard. Later tasks that say "add to `nbs/schedule.py`" INSERT their definitions **above this guard**, never append after it. (Import/pytest never triggers this, so tests won't catch a misplaced guard — only the systemd `ExecStart` path would.)

- [ ] **Step 4: Run to verify pass**

Run: `python3 -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_schedule.py']))"`
Expected: PASS (previous 5 + 3 new = 8 passed).

- [ ] **Step 5: Commit**

```bash
git add nbs/schedule.py tests/test_schedule.py
git commit -m "feat(p3c): driver tick — flock probe, preflight gate, orchestrate delegation"
```

---

### Task 3: `ensure_chrome()` + teardown, wired into the tick

**Files:**
- Modify: `nbs/schedule.py` (`ensure_chrome`, `_launch_chrome`, `_bridge_ready`, `_kill`, wire into `run_tick`)
- Test: `tests/test_schedule.py`

**Interfaces:**
- Consumes: `subprocess`, `shutil`, `time`, `config.config_dir` via `email.config_dir` for the profile dir.
- Produces: `ensure_chrome(*, launcher=_launch_chrome, probe=_bridge_ready, timeout=30.0) -> dict | None`. Returns `{"pid": int}` when the bridge became ready, else `None` (degrade — Reddit off). `_kill(handle)` tears down only that pid. `run_tick` gains `chrome=ensure_chrome, kill=_kill` params and only launches when `preflight` said `reddit_ok`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_schedule.py
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
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_schedule.py','-k','chrome']))"`
Expected: FAIL — `AttributeError: ensure_chrome`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to nbs/schedule.py — insert ABOVE the `if __name__ == "__main__"` guard (keep guard last)
import shutil, time, signal
from . import email as _email

_CHROME_PROFILE = _email.config_dir() / "chrome-profile"

def _launch_chrome():
    # Dedicated automation profile (isolated from daily browsing). Display env is pinned by
    # the systemd unit (Environment=DISPLAY=:0 ...). start_new_session=True puts chrome in its
    # OWN process group so teardown can reap the whole tree (chrome forks a browser + renderers;
    # SIGTERM to just the launcher pid orphans children that keep the profile's SingletonLock,
    # wedging every subsequent launch -> Reddit silently dead forever). Returns the launched pid.
    p = subprocess.Popen(
        ["google-chrome", f"--user-data-dir={_CHROME_PROFILE}",
         "--no-first-run", "--no-default-browser-check", "--start-minimized"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return p.pid

def _bridge_ready():
    # opencli talks to Chrome via the Browser-Bridge extension (NOT a debug port). Ready iff a
    # cheap opencli call does NOT emit BROWSER_CONNECT. (collect.py uses the same signal.)
    # Bounded + errors swallowed so a hung/broken opencli can NEVER block the tick.
    if not shutil.which("opencli"):
        return False
    try:
        r = subprocess.run(["opencli", "reddit", "subreddit", "test", "--limit", "1", "-f", "json"],
                           capture_output=True, text=True, timeout=15)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return "BROWSER_CONNECT" not in (r.stdout + r.stderr)

def _kill(handle):
    # Kill the whole process group WE started (dedicated launch, start_new_session) so chrome's
    # children die too and release the profile lock. Still "only ours" — never touches a
    # browser another run/human started.
    if handle and handle.get("pid"):
        try:
            os.killpg(os.getpgid(handle["pid"]), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass

def ensure_chrome(*, launcher=_launch_chrome, probe=_bridge_ready, killer=_kill, timeout=30.0):
    # MUST NEVER raise or hang the caller — Reddit must never block the daily publish. Any
    # launcher/probe failure or timeout => tear down our Chrome (if launched) and degrade to
    # RSS+X by returning None.
    pid = None
    try:
        pid = launcher()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if probe():
                return {"pid": pid}
            time.sleep(1.0)
    except Exception:
        pass
    if pid is not None:
        try:
            killer({"pid": pid})   # bridge never came up / error -> degrade, don't hang the run
        except Exception:
            pass                   # even teardown must not raise out of ensure_chrome
    return None
```

Then modify `run_tick` to launch/teardown Chrome around the run:

```python
def run_tick(date=None, *, orchestrate_run=None, pre=None, chrome=None, kill=None):
    # None-defaults resolved at call time (see Task 2 note) so monkeypatch on the module
    # globals works and no real Chrome launches in a unit test.
    orchestrate_run = orchestrate_run or orchestrate.run
    pre = pre or preflight
    chrome = chrome or ensure_chrome
    kill = kill or _kill
    date = date or orchestrate._today()
    if not _probe_free():
        return BUSY_EXIT
    pf = pre(root=config.ROOT, date=date)
    if not pf["ok"]:
        print(f"[preflight] abort: {pf['reason']}")
        return 2
    handle = chrome() if pf["reddit_ok"] else None   # launch BEFORE orchestrate (collect connects to it)
    try:
        manifest = orchestrate_run(date)
    finally:
        kill(handle)                                  # tear down only our own pid group
    status = (manifest or {}).get("status", "failed")
    return orchestrate._STATUS_EXIT.get(status, 1)
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_schedule.py']))"`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add nbs/schedule.py tests/test_schedule.py
git commit -m "feat(p3c): ensure_chrome bounded launch/degrade + self-pid teardown"
```

---

### Task 4: `check_alert()` — quiet-day alert (git-authoritative, bounded wait, own ledger)

**Files:**
- Modify: `nbs/schedule.py` (`check_alert`, `_wait_for_lock`, `_send_alert`, `_alert_ledger`, `_alert_sent`, `_record_alert`)
- Test: `tests/test_schedule.py`

**Interfaces:**
- Consumes: `email.published(date) -> bool` (git-authoritative), `email.load_credentials`, `email.build_message`, `email._gmail_send`, `email.EMAIL_SENDER`, `email.DEFAULT_RECIPIENTS`, `email.config_dir`, `orchestrate._today`.
- Produces: `check_alert(date=None, *, is_published=email.published, sender=None, waiter=None) -> int`. Sends at most one alert/day (separate ledger `config_dir()/alert_log.csv`). Returns 0 always (observational).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_schedule.py
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
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_schedule.py','-k','check_alert']))"`
Expected: FAIL — `AttributeError: check_alert`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to nbs/schedule.py — insert ABOVE the `if __name__ == "__main__"` guard (keep guard last)
import csv

def _alert_ledger():
    return _email.config_dir() / "alert_log.csv"

def _alert_sent(date):
    # Only a SUCCESSFUL send suppresses a resend. An "error:" row must NOT count as delivered,
    # else one failed attempt permanently blocks the alert for that day.
    p = _alert_ledger()
    if not p.exists():
        return False
    with open(p, newline="") as f:
        return any(len(row) >= 2 and row[0] == date and row[1] == "sent" for row in csv.reader(f))

def _record_alert(date, status):
    p = _alert_ledger()
    p.parent.mkdir(parents=True, exist_ok=True)   # the ledger's own dir (monkeypatched in tests)
    try:
        os.chmod(p.parent, 0o700)
    except OSError:
        pass
    new = not p.exists()
    with open(p, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "status"])
        w.writerow([date, status])
    os.chmod(p, 0o600)

def _wait_for_lock(timeout=300.0):
    # If a run is in flight at alert time, wait (bounded) for it to release the lock, so we
    # don't false-alarm a run that finishes just after 12:00. If it never releases within the
    # bound the run is stuck — itself an alertable failure, so we return and let the check proceed.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _probe_free():
            return
        time.sleep(5.0)

def _last_run_reason(date):
    p = config.run_dir(date) / "run.json"
    if p.exists():
        import json
        try:
            m = json.loads(p.read_text())
            return f"{m.get('status','?')}: {m.get('reason','')}"
        except Exception:
            pass
    return "no run.json (tick may not have run)"

def _send_alert(date, reason):
    creds = _email.load_credentials()
    subject = f"[AI Daily] MISSED publish {date}"
    body = f"ai-daily did not publish {date} by 12:00 KST.\nlast run: {reason}\n"
    msg = _email.build_message(_email.EMAIL_SENDER, _email.DEFAULT_RECIPIENTS, subject,
                               f"<pre>{body}</pre>", body)
    _email._gmail_send(creds, msg, _email.EMAIL_SENDER)

def check_alert(date=None, *, is_published=None, sender=None, waiter=None):
    date = date or orchestrate._today()
    is_published = is_published or _email.published
    sender = sender or _send_alert
    waiter = waiter or _wait_for_lock
    waiter()                                  # let any in-flight run finish first (bounded)
    if is_published(date):
        return 0                              # published -> nothing to alert
    if _alert_sent(date):
        return 0                              # already alerted today -> idempotent
    try:
        sender(date, _last_run_reason(date))
        _record_alert(date, "sent")           # record AFTER send succeeds
    except Exception as e:
        _record_alert(date, f"error:{str(e)[:80]}")
    return 0
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -c "import pytest,sys; sys.exit(pytest.main(['-q','tests/test_schedule.py']))"`
Expected: PASS (18 passed).

- [ ] **Step 5: Commit**

```bash
git add nbs/schedule.py tests/test_schedule.py
git commit -m "feat(p3c): quiet-day alert — git-authoritative, bounded wait, own ledger"
```

---

### Task 5: systemd units + install script

**Files:**
- Create: `deploy/systemd/ai-daily.service`, `deploy/systemd/ai-daily.timer`, `deploy/systemd/ai-daily-alert.service`, `deploy/systemd/ai-daily-alert.timer`
- Create: `scripts/install_scheduler.sh`
- Test: manual `systemd-analyze --user verify` (documented in the step)

**Interfaces:**
- Consumes: `python3 -m nbs.schedule` (tick) and `python3 -m nbs.schedule --check-alert`.
- Produces: installed user timers. No Python interface.

- [ ] **Step 1: Write the unit files**

`deploy/systemd/ai-daily.service`:
```ini
[Unit]
Description=ai-daily unattended publish tick

[Service]
Type=oneshot
WorkingDirectory=%h/project/NBs
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=DISPLAY=:0
Environment=WAYLAND_DISPLAY=wayland-0
ExecStart=/usr/bin/python3 -m nbs.schedule
```

`deploy/systemd/ai-daily.timer`:
```ini
[Unit]
Description=ai-daily publish window (07/09/11 KST)

[Timer]
OnCalendar=*-*-* 07:00:00 Asia/Seoul
OnCalendar=*-*-* 09:00:00 Asia/Seoul
OnCalendar=*-*-* 11:00:00 Asia/Seoul
Persistent=true

[Install]
WantedBy=timers.target
```

`deploy/systemd/ai-daily-alert.service`:
```ini
[Unit]
Description=ai-daily quiet-day alert check

[Service]
Type=oneshot
WorkingDirectory=%h/project/NBs
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/python3 -m nbs.schedule --check-alert
```

`deploy/systemd/ai-daily-alert.timer`:
```ini
[Unit]
Description=ai-daily quiet-day alert (12:00 KST)

[Timer]
OnCalendar=*-*-* 12:00:00 Asia/Seoul
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 2: Write the install script**

`scripts/install_scheduler.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
UNIT_DIR="$HOME/.config/systemd/user"
SRC="$(cd "$(dirname "$0")/../deploy/systemd" && pwd)"
mkdir -p "$UNIT_DIR"
cp "$SRC"/ai-daily.service "$SRC"/ai-daily.timer \
   "$SRC"/ai-daily-alert.service "$SRC"/ai-daily-alert.timer "$UNIT_DIR/"
systemctl --user daemon-reload
systemctl --user enable --now ai-daily.timer ai-daily-alert.timer
# Run user timers without an interactive login session (required for WSL unattended).
loginctl enable-linger "$USER" || echo "[warn] enable-linger failed — run: sudo loginctl enable-linger $USER"
echo "installed. timers:"
systemctl --user list-timers 'ai-daily*' --no-pager || true
cat <<'EOF'

[one-time manual, for Reddit]
  Launch Chrome once with the automation profile, install the OpenCLI Browser-Bridge
  extension, and log into Reddit in it:
    google-chrome --user-data-dir="$HOME/.config/ai-daily/chrome-profile"
  (A fresh profile has NO extensions — logging into Reddit alone is not enough.)
EOF
```

- [ ] **Step 3: Verify the units parse**

Run:
```bash
chmod +x scripts/install_scheduler.sh
python3 - <<'PY'
import subprocess, glob, sys
bad = 0
for u in glob.glob("deploy/systemd/*.timer") + glob.glob("deploy/systemd/*.service"):
    r = subprocess.run(["systemd-analyze", "--user", "verify", u], capture_output=True, text=True)
    # verify emits warnings for [Install] on templates run out-of-tree; fail only on parse errors
    if "Failed to parse" in (r.stderr + r.stdout):
        print("PARSE ERROR", u, r.stderr); bad = 1
print("units OK" if not bad else "units FAILED"); sys.exit(bad)
PY
```
Expected: `units OK`.

- [ ] **Step 4: Full suite green**

Run: `python3 -c "import pytest,sys; sys.exit(pytest.main(['-q','tests']))"`
Expected: PASS (all prior + P3c tests; no regressions).

- [ ] **Step 5: Commit**

```bash
git add deploy/systemd scripts/install_scheduler.sh
git commit -m "feat(p3c): systemd user timers (07/09/11 + 12:00 alert) + install script"
```

---

## Real smoke (after all tasks — manual / Codex, Claude env)

Unit tests never touch real Chrome/opencli/systemd. Before merge, run ONE real smoke (documented, not automated — [[smoke-tests-via-codex]]):
1. One-time: launch Chrome with the automation profile, install Browser-Bridge extension, log into Reddit.
2. `bash scripts/install_scheduler.sh` then `systemctl --user start ai-daily.service` — observe a real tick: preflight passes, Chrome launches, `orchestrate.run` publishes (or idempotent-skips), Chrome torn down.
3. Force a quiet day (e.g. temporarily point at a date with no origin news) → `python3 -m nbs.schedule --check-alert` → confirm one alert email, second call no resend.

## Self-Review (completed during authoring)

- **Spec coverage:** systemd timer (Task 5) ✓; idempotent catchup via orchestrate reuse (Task 2) ✓; preflight hard/soft narrowed set (Task 1) ✓; Reddit Chrome degrade + self-pid teardown + bridge probe (Task 3) ✓; quiet-day alert 12:00 + bounded wait + gmail primitives + own ledger, NOT run_email (Task 4) ✓; install + linger + Chrome one-time note (Task 5) ✓; flock probe reuse of orchestrate lock (Task 2) ✓.
- **Placeholder scan:** none — every code step is complete and runnable.
- **Type consistency:** `run_tick(chrome=, kill=)` seams match Task 3; `preflight` returns `{"ok","reason","reddit_ok"}` used consistently; `ensure_chrome` returns `{"pid":int}|None` consumed by `_kill`; `check_alert(is_published=,sender=,waiter=)` seams match tests.
