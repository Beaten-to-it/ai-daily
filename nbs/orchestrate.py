import fcntl
import subprocess, json, os, tempfile, re, argparse
from contextlib import contextmanager
from datetime import datetime
from .config import ROOT, run_dir
from . import config

class Busy(Exception):
    pass

@contextmanager
def _lock():
    # fd-based flock: exclusive, non-blocking; kernel auto-releases on process death
    # (crash-safe — a killed run never leaves a stale lock, unlike a bare pidfile).
    lock_path = ROOT / ".orchestrate.lock"
    f = open(lock_path, "w")
    try:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Busy("another orchestrate run holds the lock")
        yield
    finally:
        f.close()   # closing the fd releases the flock

def _git(args):
    return subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True)

def _head_has_news(date):
    return _git(["cat-file", "-e", f"HEAD:content/news/{date}.md"]).returncode == 0

def _publish_state(date):
    p = run_dir(date) / "publish.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None

def decide_action(date, *, force):
    # git-authoritative: HEAD having the day's news file is the reliable "published locally"
    # signal (survives runs/ scratch wipe). publish.json.pushed only optimizes skip vs re-push.
    if force:
        return "full"
    if _head_has_news(date):
        st = _publish_state(date) or {}
        return "skip" if st.get("pushed") is True else "push_only"
    return "full"

STAGES = ["collect", "select", "stage", "publish"]
_ARTIFACT = {"collect": "candidates.json", "select": "selection.json",
             "stage": "generation.json", "publish": "publish.json"}

def _default_runner(name, date):
    return subprocess.run(["python3", "-m", f"nbs.{name}", "--date", date],
                          cwd=str(ROOT)).returncode

def _stage_ok(name, date, rc):
    if rc != 0:
        return False, f"{name} exited {rc}"
    p = run_dir(date) / _ARTIFACT[name]
    if not p.exists():
        return False, f"{name} rc0 but {_ARTIFACT[name]} missing"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        return False, f"{name} artifact unreadable: {e}"
    if name == "stage" and data.get("status") not in ("ok", "skip-empty"):
        return False, f"stage status {data.get('status')!r}"
    return True, ""

def _mark_pushed(date, sha):
    p = run_dir(date) / "publish.json"
    st = _publish_state(date) or {"date": date, "status": "published"}
    st["pushed"] = True
    st["deployed_sha"] = sha
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        os.path.exists(tmp) and os.remove(tmp); raise

def _classify_push_failure(head):
    # classify a FAILED `git push` by querying the live remote (never parse git stderr).
    ls = _git(["ls-remote", "origin", "refs/heads/main"])
    if ls.returncode != 0 or not ls.stdout.strip():
        return "push_pending", None, "origin/main absent or ls-remote failed"
    remote_sha = ls.stdout.split()[0]
    if remote_sha == head:                       # push actually landed (client died post-update)
        return "published", remote_sha, "push rc!=0 but origin/main already equals HEAD"
    # non-fast-forward iff the remote tip is NOT an ancestor of our HEAD (origin diverged)
    if _git(["merge-base", "--is-ancestor", remote_sha, "HEAD"]).returncode != 0:
        return "push_rejected", None, f"origin/main diverged (remote {remote_sha[:12]} not ancestor of HEAD)"
    return "push_pending", None, "push failed but origin is behind (transient)"

def _push(date):
    # returns (status, sha_or_None, reason). status ∈ {published, push_pending, push_rejected}
    head = _git(["rev-parse", "HEAD"]).stdout.strip()
    if _git(["push", "origin", "main"]).returncode != 0:
        status, sha, reason = _classify_push_failure(head)
        if status == "published":                # remote already at HEAD → record it
            _mark_pushed(date, sha)
            return "published", sha, reason
        return status, None, reason
    if _git(["rev-parse", "origin/main"]).stdout.strip() != head:
        return "push_pending", None, "push reported success but origin/main did not advance"
    _mark_pushed(date, head)
    return "published", head, ""

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_STATUS_EXIT = {"published":0,"skipped":0,"held":1,"failed":1,
                "push_rejected":1,"push_pending":2,"busy":3}

def _blank_stages():
    return {s: {"status": "skipped", "reason": ""} for s in STAGES + ["push"]}

def _write_run(date, payload):
    (run_dir(date)).mkdir(parents=True, exist_ok=True)
    (run_dir(date)/"run.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

def run(date, *, force=False, no_push=False, runner=None, now=None):
    runner = runner or _default_runner
    now = now or datetime.now(config.KST)
    run_id = now.strftime("%Y%m%dT%H%M%S%z")
    started = now.isoformat()
    base = {"date": date, "run_id": run_id, "started_at": started,
            "status": "failed", "stages": _blank_stages(), "reason": "", "force": force}
    if not _DATE.fullmatch(date or ""):
        base["status"] = "failed"; base["reason"] = "invalid date (must be YYYY-MM-DD)"
        return base   # do NOT write run.json under an unvalidated path
    def finish(status, reason=""):
        base["status"] = status; base["reason"] = reason
        return _write_run(date, base)
    try:
        with _lock():
            action = decide_action(date, force=force)
            if action == "skip":
                return finish("skipped", "already published and pushed")
            if action == "push_only":
                st, sha, reason = _push(date)
                base["stages"]["push"] = {"status": st, "reason": reason or "push-only recovery"}
                top = "re-pushed without regeneration" if st == "published" else f"push-only recovery failed: {reason}"
                return finish("published" if st == "published" else st, top)
            # action == "full"
            for name in STAGES:
                rc = runner(name, date)
                if name == "publish":
                    # publish exits 0 even for held/failed — but a CRASHED publish (rc!=0) must
                    # NOT be read as a stale prior publish.json{published}. Gate on rc+artifact first.
                    ok, reason = _stage_ok("publish", date, rc)
                    if not ok:
                        base["stages"]["publish"] = {"status": "failed", "reason": reason}
                        return finish("failed", f"publish: {reason}")
                    pj = _publish_state(date) or {}
                    pstatus = pj.get("status")
                    if pstatus not in ("published", "held", "failed"):
                        base["stages"]["publish"] = {"status": "failed", "reason": f"unknown publish status {pstatus!r}"}
                        return finish("failed", f"unknown publish status {pstatus!r}")
                    preason = pj.get("reason", "")   # publish.py records the held/failed cause here
                    base["stages"]["publish"] = {"status": pstatus, "reason": preason}
                    if pstatus != "published":
                        return finish(pstatus, preason or f"publish {pstatus}")   # held/failed -> no push
                    break
                ok, reason = _stage_ok(name, date, rc)
                base["stages"][name] = {"status": "ok" if ok else "failed", "reason": reason}
                if not ok:
                    return finish("failed", f"{name}: {reason}")
            if no_push:
                base["stages"]["push"] = {"status": "skipped", "reason": "--no-push"}
                return finish("published", "published (push skipped)")
            st, sha, reason = _push(date)
            base["stages"]["push"] = {"status": st, "reason": reason}
            return finish("published" if st == "published" else st, reason)
    except Busy:
        base["status"] = "busy"; base["reason"] = "another run in progress"
        return base   # do not clobber the other run's run.json

def _today():
    return datetime.now(config.KST).strftime("%Y-%m-%d")

def main(argv=None):
    ap = argparse.ArgumentParser(prog="orchestrate")
    ap.add_argument("--date", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args(argv)
    date = a.date or _today()
    m = run(date, force=a.force, no_push=a.no_push)
    push = (m.get("stages", {}) or {}).get("push", {}).get("status", "-")
    print(f"[{m['status']}] {date} push={push} reason={m.get('reason','')}")
    return _STATUS_EXIT.get(m["status"], 1)

if __name__ == "__main__":
    raise SystemExit(main())
