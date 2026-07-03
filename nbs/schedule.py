import os, subprocess, shutil, time, signal, argparse, csv
from pathlib import Path
from . import config
from . import orchestrate
from . import email as _email

_CHROME_PROFILE = _email.config_dir() / "chrome-profile"

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
    st = _git(root, "status", "--porcelain", "--", *_writeset(date))
    if st.returncode != 0:
        # fail CLOSED: a git error must not be silently read as "clean" (spec §172's rollback
        # guard only holds if we actually know the write-set state).
        return {"ok": False, "reason": f"git status failed: {st.stderr[:80]}", "reddit_ok": False}
    dirty = st.stdout.strip()
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

def run_tick(date=None, *, orchestrate_run=None, pre=None, chrome=None, kill=None):
    # IMPORTANT: default seams are None and resolved to module globals at CALL time, so that
    # `monkeypatch.setattr(schedule, "preflight", ...)` in tests actually takes effect. A
    # keyword default like `pre=preflight` binds the ORIGINAL function object at def time and
    # would ignore the monkeypatch (and on the dev box run real preflight -> launch real Chrome).
    orchestrate_run = orchestrate_run or orchestrate.run
    pre = pre or preflight
    chrome = chrome or ensure_chrome
    kill = kill or _kill
    date = date or orchestrate._today()
    if not _probe_free():
        return BUSY_EXIT
    pf = pre(root=config.ROOT, date=date)
    if not pf["ok"]:
        # hard fail: abort THIS tick (no partial writes); next tick retries.
        print(f"[preflight] abort: {pf['reason']}")
        return 2
    handle = chrome() if pf["reddit_ok"] else None   # launch BEFORE orchestrate (collect connects to it)
    try:
        manifest = orchestrate_run(date)
    finally:
        kill(handle)                                  # tear down only our own pid group
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

if __name__ == "__main__":
    raise SystemExit(main())
