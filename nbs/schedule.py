import os, subprocess, shutil, argparse
from pathlib import Path
from . import config
from . import orchestrate

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
