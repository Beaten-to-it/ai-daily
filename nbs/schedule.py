import os, subprocess, shutil, time, argparse, csv
from pathlib import Path
from . import config, locking
from . import orchestrate
from . import email as _email

def _git(root, *args):
    # schedule runs only LOCAL git ops (status/config) — they fail fast, never hang, so no timeout.
    # GIT_TERMINAL_PROMPT=0 so a credential prompt fails fast. env per call (not import-snapshotted).
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})

def _git_credentials_present():
    if any(os.environ.get(name) for name in ("GITHUB_TOKEN", "GH_TOKEN", "GIT_ASKPASS")):
        return True
    helper = _git(config.ROOT, "config", "--get-all", "credential.helper")
    if helper.returncode == 0 and helper.stdout.strip():
        return True
    remote = _git(config.ROOT, "remote", "get-url", "origin")
    return remote.returncode == 0 and remote.stdout.strip().startswith(("ssh://", "git@"))

def _writeset(date):
    # Date-scoped paths publish can promote, delete, or restore. Keep exact daily/derived names
    # while allowing every same-date article that stale cleanup may remove.
    return [f"content/articles/{date}-*.md", f"content/daily/{date}.md",
            f"content/guides/{date}.md", f"content/executive/{date}.md", "data/published.csv"]

def preflight(root=config.ROOT, date=None):
    date = date or "0000-00-00"   # caller (run_tick) passes the tick date; guard against None
    # HARD (only what orchestrate can't cleanly self-handle):
    # 1) THIS date's write-set must be clean — orchestrate's rollback `git checkout` would else
    #    destroy the user's uncommitted changes (spec §172).
    st = _git(root, "status", "--porcelain", "--", *_writeset(date))
    if st.returncode != 0:
        # fail CLOSED: a git error must not be silently read as "clean" (spec §172's rollback
        # guard only holds if we actually know the write-set state).
        return {"ok": False, "reason": f"git status failed: {st.stderr[:80]}"}
    dirty = st.stdout.strip()
    if dirty:
        return {"ok": False, "reason": f"write-set dirty: {dirty.splitlines()[0]}"}
    # 2) git identity + credentials (commit/push preconditions; push_only path needs these too).
    name = _git(root, "config", "user.name").stdout.strip()
    email = _git(root, "config", "user.email").stdout.strip()
    if not (name and email):
        return {"ok": False, "reason": "git identity missing"}
    if not _git_credentials_present():
        return {"ok": False, "reason": "Git credential helper or token missing"}
    # SOFT (warn, never abort): a real hugo/deps miss is caught cleanly by orchestrate's
    # per-stage rc, and push_only/skip recovery doesn't need hugo — so these never gate the tick.
    if not shutil.which("hugo"):
        print("[preflight] warn: hugo not on PATH (a full run's build-verify would fail this tick)")
    return {"ok": True, "reason": ""}

BUSY_EXIT = 3   # matches orchestrate._STATUS_EXIT["busy"]

def _probe_free():
    # Non-blocking probe of orchestrate's lock: acquire-and-release. If busy, a run is in
    # progress. Tiny race (probe releases before
    # orchestrate.run re-acquires) is covered by no-manual-run-in-window; if it still races,
    # orchestrate.run returns status "busy" and run_tick propagates BUSY_EXIT anyway.
    try:
        with orchestrate._lock():
            return True
    except orchestrate.Busy:
        return False

_SCHEDULE_LOCK = config.ROOT / ".schedule.lock"

def _schedule_lock():
    return locking.exclusive_lock(_SCHEDULE_LOCK)

def _schedule_busy():
    try:
        with _schedule_lock():
            return False
    except orchestrate.Busy:
        return True

def run_tick(date=None, *, orchestrate_run=None, pre=None):
    # IMPORTANT: default seams are None and resolved to module globals at CALL time, so that
    # `monkeypatch.setattr(schedule, "preflight", ...)` in tests actually takes effect. A
    # keyword default like `pre=preflight` binds the ORIGINAL function object at def time and
    # would ignore the monkeypatch.
    orchestrate_run = orchestrate_run or orchestrate.run
    pre = pre or preflight
    date = date or orchestrate._today()
    try:
        with _schedule_lock():
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
    except orchestrate.Busy:               # another schedule tick already running
        return BUSY_EXIT

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
    if os.name != "nt":
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
    if os.name != "nt":
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass

def _wait_for_lock(timeout=300.0):
    # If a run is in flight at alert time, wait (bounded) for it to release the lock, so we
    # don't false-alarm a run that finishes just after 12:00. If it never releases within the
    # bound the run is stuck — itself an alertable failure, so we return and let the check proceed.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _probe_free() and not _schedule_busy():   # orchestrate AND schedule tick both idle
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
    _email._gmail_send(creds, msg, "me")          # Gmail API userId="me" = authenticated account

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
        # the missed-publish alert is the LAST line of defense; a swallowed send failure (token
        # invalid / transient Gmail) must not look like a healthy check. Return nonzero so the
        # ai-daily-alert unit is marked failed and the operator actually notices.
        _record_alert(date, f"error:{str(e)[:80]}")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
