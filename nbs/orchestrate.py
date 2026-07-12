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

# Only NETWORK git ops (push, ls-remote) can hang — a stalled peer/credential-helper would otherwise
# block the run forever AFTER the commit, holding both locks. They pass an explicit timeout below
# (=CRITICAL-3 guard). LOCAL ops get NO timeout: git fails fast on lock/disk, it never hangs, and a
# synthetic timeout rc would be indistinguishable from a real "clean"/"absent" answer and silently
# read as success by callers. GIT_TERMINAL_PROMPT=0 everywhere: a credential prompt fails fast
# instead of hanging on stdin. A network timeout surfaces as rc=124, handled at the two call sites.
_GIT_NET_TIMEOUT = 120

def _git(args, timeout=None):
    # env built PER CALL (not snapshotted at import) so runtime GIT_CONFIG_*/env overrides are honored.
    try:
        return subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True,
                              timeout=timeout, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, returncode=124, stdout="", stderr="git timed out")

def _head_has_news(date):
    # tri-state: True = in HEAD, False = CONFIRMED absent, None = git error (caller fails closed).
    # ls-tree (not cat-file): cat-file returns rc 128 for BOTH a missing path AND a corrupt repo, so
    # a git error would masquerade as "not published" and drive a re-publish. ls-tree returns rc 0
    # for present AND absent (differing only by stdout) and rc != 0 only on a genuine error.
    r = _git(["ls-tree", "HEAD", "--", f"content/news/{date}.md"])
    if r.returncode != 0:
        return None
    return bool(r.stdout.strip())

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
    hn = _head_has_news(date)
    if hn is None:                              # can't determine publish state (git error) -> abort,
        return "error"                          # never guess: guessing "unpublished" re-publishes a live day
    if hn:
        st = _publish_state(date)
        if st is None:                          # scratch wiped but news in HEAD → recover by re-push
            return "push_only"
        if st.get("status") != "published":     # a held/failed manifest (e.g. a later --force run)
            return "full"                       # means this day is NOT cleanly published → regenerate
        return "skip" if st.get("pushed") is True else "push_only"
    return "full"

STAGES = ["collect", "select", "stage", "publish"]
_ARTIFACT = {"collect": "candidates.json", "select": "selection.json",
             "stage": "generation.json", "publish": "publish.json"}

def _default_runner(name, date, no_commit=False):
    argv = ["python3", "-m", f"nbs.{name}", "--date", date]
    if name == "publish" and no_commit:
        argv.append("--no-commit")     # promote into content/ but DON'T commit (smoke-safe)
    return subprocess.run(argv, cwd=str(ROOT)).returncode

def _default_email_runner(date, run_id):
    try:
        p = subprocess.run(["python3", "-m", "nbs.email", "--date", date, "--run-id", run_id],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:            # never hang the run (and the flock) on a stuck send
        return 1, {"status": "error", "reason": "email timed out (120s)"}
    try:
        res = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
    except (ValueError, IndexError):
        res = {"status": "error", "reason": "unparseable email output"}
    return p.returncode, res

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
    st = _publish_state(date) or {"date": date}
    st["status"] = "published"   # we only mark after pushing a published HEAD; never keep held/failed
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
    ls = _git(["ls-remote", "origin", "refs/heads/main"], timeout=_GIT_NET_TIMEOUT)   # network: bound it
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
    # push the ACTUAL published commit (HEAD) to remote main — NOT the local `main` branch,
    # which may be stale/unrelated on a non-main or detached checkout.
    head = _git(["rev-parse", "HEAD"]).stdout.strip()
    if _git(["push", "origin", "HEAD:refs/heads/main"], timeout=_GIT_NET_TIMEOUT).returncode != 0:
        status, sha, reason = _classify_push_failure(head)   # rc=124 on timeout -> ls-remote decides
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
    return {s: {"status": "skipped", "reason": ""} for s in STAGES + ["push", "email"]}

def _write_run(date, payload):
    d = run_dir(date); d.mkdir(parents=True, exist_ok=True)
    p = d/"run.json"
    fd, tmp = tempfile.mkstemp(dir=str(d), suffix=".json")   # atomic: no truncated manifest on crash
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        os.path.exists(tmp) and os.remove(tmp); raise
    return payload

def run(date, *, force=False, no_push=False, no_commit=False, runner=None, now=None, email_runner=None):
    if no_commit:
        no_push = True   # nothing committed -> a push would send an unchanged HEAD; skip it (smoke-safe)
    runner = runner or (lambda n, d: _default_runner(n, d, no_commit=no_commit))
    email_runner = email_runner or _default_email_runner
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
        _write_run(date, base)                          # persist publish+push BEFORE the network email
        # email only when the day is genuinely published to origin AND this is not a dry-run.
        if status in ("published", "skipped") and not no_push:
            try:
                rc, res = email_runner(date, run_id)
                # a failed email is a P3d ALERT — normalize rc!=0 to "failed" (§12/§15).
                estatus = "failed" if rc != 0 else res.get("status", "failed")
                est = {"status": estatus, "reason": res.get("reason", "")}
            except Exception as e:                      # seam/subprocess failure must not crash the run
                est = {"status": "failed", "reason": str(e)}
            base["stages"]["email"] = est
            _write_run(date, base)                      # best-effort re-write with the email stage
        return base
    try:
        with _lock():
            if no_commit and _head_has_news(date) is not False:
                # a no-commit PREVIEW must never overwrite the recovery manifest of an already-
                # published date: publish would write publish.json{status:published, commit_sha:null}
                # with no actual commit, so the next real run does push_only on the STALE HEAD and
                # records the preview as deployed. Refuse on True (published) OR None (state
                # unverifiable via git) — fail closed. No run/publish state is touched.
                base["status"] = "skipped"
                base["reason"] = "no-commit preview refused: date published or state unverifiable"
                return base
            action = decide_action(date, force=force)
            if action == "error":
                # decide_action could not determine publish state (git error) -> abort, don't guess.
                return finish("failed", "cannot determine publish state (git error)")
            if action == "skip":
                return finish("skipped", "already published and pushed")
            if action == "push_only":
                if no_push:   # honor dry-run on the recovery path too (else smoke pushes to origin)
                    base["stages"]["push"] = {"status": "skipped", "reason": "--no-push"}
                    return finish("published", "already published locally (push skipped)")
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
    ap.add_argument("--no-commit", action="store_true")   # promote but don't commit/push (smoke)
    a = ap.parse_args(argv)
    date = a.date or _today()
    m = run(date, force=a.force, no_push=a.no_push, no_commit=a.no_commit)
    push = (m.get("stages", {}) or {}).get("push", {}).get("status", "-")
    print(f"[{m['status']}] {date} push={push} reason={m.get('reason','')}")
    return _STATUS_EXIT.get(m["status"], 1)

if __name__ == "__main__":
    raise SystemExit(main())
