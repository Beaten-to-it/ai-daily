import base64
import importlib.util
import json as _json
import os as _os
import stat as _stat
import subprocess
from email import message_from_bytes
from pathlib import Path

import pytest

from nbs import config


# --- helpers -----------------------------------------------------------------

def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _init_repo_with_origin(tmp_path):
    """work repo + a bare 'origin'; return work path. origin/main tracks pushes."""
    bare = tmp_path / "origin.git"; work = tmp_path / "work"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    subprocess.run(["git", "init", str(work)], check=True, capture_output=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _git(work, "config", k, v)
    _git(work, "remote", "add", "origin", str(bare))
    for section in ("daily", "guides", "executive"):
        (work / "content" / section).mkdir(parents=True)
    return work


def _publish_day(work, date, *, derived=True):
    # mirror real content: YAML front matter with a title (subject_for reads it)
    (work / "content" / "daily" / f"{date}.md").write_text(
        f'---\ntitle: "{date} Daily"\ntags: ["daily"]\n---\n\n오늘의 항목:\n- x\n', encoding="utf-8")
    if derived:
        (work / "content" / "guides" / f"{date}.md").write_text(
            f'---\ntitle: "{date} Guide"\n---\n\n- y\n', encoding="utf-8")
    _git(work, "add", "-A"); _git(work, "commit", "-m", "pub")
    _git(work, "push", "origin", "HEAD:refs/heads/main")


def _decode(raw_dict):
    return message_from_bytes(base64.urlsafe_b64decode(raw_dict["raw"]))


# --- Task 1: config + paths --------------------------------------------------

def test_site_baseurl_matches_hugo():
    assert config.SITE_BASEURL == "https://beaten-to-it.github.io/ai-daily/"


def test_paths_default_outside_repo(monkeypatch):
    from nbs import email as em
    for v in ("AI_DAILY_CONFIG_DIR", "AI_DAILY_GOOGLE_TOKEN", "AI_DAILY_GOOGLE_CLIENT_SECRET", "AI_DAILY_EMAIL_LOG"):
        monkeypatch.delenv(v, raising=False)
    base = em.config_dir()
    assert em.token_path() == base / "google_token.json"
    assert em.client_secret_path() == base / "client_secret.json"
    assert em.ledger_path() == base / "email_delivery_log.csv"
    assert config.ROOT not in em.token_path().parents


@pytest.mark.skipif(_os.name != "nt", reason="Windows path contract")
def test_windows_config_dir_uses_localappdata(monkeypatch, tmp_path):
    from nbs import email as em
    monkeypatch.delenv("AI_DAILY_CONFIG_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert em.config_dir() == tmp_path / "ai-daily"


def test_paths_env_override(monkeypatch, tmp_path):
    from nbs import email as em
    monkeypatch.setenv("AI_DAILY_GOOGLE_TOKEN", str(tmp_path / "t.json"))
    monkeypatch.setenv("AI_DAILY_EMAIL_LOG", str(tmp_path / "log.csv"))
    assert em.token_path() == tmp_path / "t.json"
    assert em.ledger_path() == tmp_path / "log.csv"


# --- Task 2: git-authoritative content ---------------------------------------

def test_published_true_only_after_push(tmp_path, monkeypatch):
    from nbs import email as em, publish
    work = _init_repo_with_origin(tmp_path)
    monkeypatch.setattr(publish, "ROOT", work)   # email reuses publish._git(cwd=ROOT)
    assert em.published("2026-07-03") is False           # nothing pushed yet
    _publish_day(work, "2026-07-03")
    assert em.published("2026-07-03") is True


def test_read_content_from_origin_main(tmp_path, monkeypatch):
    from nbs import email as em, publish
    work = _init_repo_with_origin(tmp_path)
    monkeypatch.setattr(publish, "ROOT", work)
    _publish_day(work, "2026-07-03", derived=True)
    # mutate working tree AFTER push: read must come from origin/main, not disk
    (work / "content" / "daily" / "2026-07-03.md").write_text("TAMPERED", encoding="utf-8")
    daily = em.read_content("2026-07-03")
    assert "Daily" in daily and "TAMPERED" not in daily


def test_read_content_daily_without_derived_pages(tmp_path, monkeypatch):
    from nbs import email as em, publish
    work = _init_repo_with_origin(tmp_path)
    monkeypatch.setattr(publish, "ROOT", work)
    _publish_day(work, "2026-07-03", derived=False)
    assert "Daily" in em.read_content("2026-07-03")


def test_read_content_ignores_guides_and_executive(tmp_path, monkeypatch):
    from nbs import email as em, publish
    work = _init_repo_with_origin(tmp_path)
    monkeypatch.setattr(publish, "ROOT", work)
    _publish_day(work, "2026-07-03", derived=True)
    (work / "content" / "executive" / "2026-07-03.md").write_text(
        "---\ntitle: Executive\n---\n경영 본문\n", encoding="utf-8")
    _git(work, "add", "-A"); _git(work, "commit", "-m", "executive"); _git(work, "push", "origin", "HEAD:refs/heads/main")
    daily = em.read_content("2026-07-03")
    assert "Daily" in daily and "Guide" not in daily and "경영 본문" not in daily


def test_default_email_reads_daily_only(monkeypatch):
    from nbs import email as em
    seen = []
    monkeypatch.setattr(em, "_origin_show", lambda path: seen.append(path) or "DAILY")
    assert em.read_content("2026-08-01") == "DAILY"
    assert seen == ["content/daily/2026-08-01.md"]


# --- Task 3: preprocess ------------------------------------------------------

def test_strip_front_matter():
    from nbs import email as em
    md = '---\ntitle: "2026-07-03 News"\ntags: ["news"]\n---\n\n오늘의 항목:\n- x\n'
    body = em.strip_front_matter(md)
    assert body.lstrip().startswith("오늘의 항목")
    assert "title:" not in body


def test_rewrite_relref_to_absolute():
    from nbs import email as em
    md = '- **A** [자세히 →]({{< relref "/articles/2026-07-03-foo.md" >}})\n'
    out = em.rewrite_relref(md)
    assert "https://beaten-to-it.github.io/ai-daily/articles/2026-07-03-foo/" in out
    assert "relref" not in out


def test_rewrite_relref_fails_on_residue():
    from nbs import email as em
    with pytest.raises(ValueError):
        em.rewrite_relref('see [x]({{% relref "/articles/y.md" %}})')


def test_rewrite_relref_allows_non_ref_shortcode():
    # A non-link shortcode remains literal text; only broken ref/relref links are fatal.
    from nbs import email as em
    out = em.rewrite_relref("예시: {{< highlight py >}}code{{< /highlight >}}")
    assert "highlight" in out   # left as literal text, no raise


def test_subject_from_frontmatter_title():
    from nbs import email as em
    md = '---\ntitle: "2026-07-03 News"\n---\n본문\n'
    assert em.subject_for(md, "2026-07-03") == "2026-07-03 News"


def test_subject_fallback_when_no_title():
    from nbs import email as em
    assert em.subject_for("본문만\n", "2026-07-03") == "[AI Daily] 2026-07-03"


def test_rewrite_relref_on_real_assemble_output():
    # contract: rewrite the EXACT output of assemble.build_daily, not a copy.
    from nbs import email as em, assemble
    from nbs.models import GenerationResult
    r = GenerationResult(event_key="e1", title="T", url="http://x", source="s",
                         source_type="article", evidence_level="confirmed", status="ok",
                         post_path="articles/2026-07-03-foo.md", slug="2026-07-03-foo",
                         rank=1, rationale="hook")
    news = assemble.build_daily([r], "2026-07-03")
    out = em.rewrite_relref(em.strip_front_matter(news))
    assert "https://beaten-to-it.github.io/ai-daily/articles/2026-07-03-foo/" in out
    assert "relref" not in out


# --- Task 4: render ----------------------------------------------------------

def test_render_html_640_and_structure():
    from nbs import email as em
    html = em.render_html("# T\n- a\n", "T", "https://beaten-to-it.github.io/ai-daily/daily/2026-07-03/")
    assert "max-width:640px" in html
    assert "<h1>" in html and "<li>" in html
    assert "daily/2026-07-03/" in html


def test_render_html_neutralizes_javascript_href():
    from nbs import email as em
    html = em.render_html("[x](javascript:alert(1))\n", "T", "")
    assert "javascript:alert" not in html
    assert 'href="#"' in html


def test_render_html_neutralizes_entity_and_schemeless():
    from nbs import email as em
    html = em.render_html("[a](jav&#x61;script:alert(1)) [b](/rel/only)\n", "T", "")
    assert "javascript" not in html.lower().replace("&#x", "")
    assert 'href="#"' in html


def test_render_html_href_quote_escaped():
    from nbs import email as em
    html = em.render_html('[x](https://e.com/a"onmouseover="x)\n', "T", "")
    assert 'onmouseover="x' not in html


def test_render_html_code_span_not_a_link():
    from nbs import email as em
    html = em.render_html("`[x](javascript:bad)`\n", "T", "")
    assert "<code>" in html and "javascript:bad" in html
    assert "<a href" not in html


def test_web_url_button_validated():
    from nbs import email as em
    html = em.render_html("hi\n", "T", "javascript:alert(1)")
    assert "javascript:alert" not in html


def test_render_text_has_url_footer():
    from nbs import email as em
    txt = em.render_text("body\n", "https://site/daily/2026-07-03/")
    assert "body" in txt and "https://site/daily/2026-07-03/" in txt
    assert "<" not in txt


# --- Task 5: MIME message + recipients ---------------------------------------

def test_default_recipient():
    from nbs import email as em
    assert em.resolve_recipients("") == ["kimhyo75@gmail.com", "hyesun83.kim@samsung.com"]


def test_recipient_override_split_dedupe():
    from nbs import email as em
    assert em.resolve_recipients("a@x.com, b@x.com , a@x.com") == ["a@x.com", "b@x.com"]


def test_recipient_rejects_crlf():
    from nbs import email as em
    with pytest.raises(ValueError):
        em.resolve_recipients("a@x.com\nBcc: evil@x.com")


def test_build_message_is_multipart_two_parts():
    from nbs import email as em
    msg = _decode(em.build_message("me@gmail.com", ["a@x.com"], "S", "<p>hi</p>", "hi"))
    assert msg.get_content_type() == "multipart/alternative"
    parts = msg.get_payload()
    assert {p.get_content_type() for p in parts} == {"text/plain", "text/html"}


def test_build_message_strips_subject_crlf():
    from nbs import email as em
    msg = _decode(em.build_message("me@gmail.com", ["a@x.com"], "S\r\nBcc: evil@x.com", "<p>h</p>", "h"))
    assert "evil@x.com" not in str(msg["Subject"])
    assert msg["From"] == "me@gmail.com"


# --- Task 6: credentials -----------------------------------------------------

def test_send_scope_is_single():
    from nbs import email as em
    assert em.SEND_SCOPES == ["https://www.googleapis.com/auth/gmail.send"]


def test_atomic_write_sets_600(tmp_path):
    from nbs import email as em
    p = tmp_path / "sub" / "t.json"
    em._atomic_write(p, '{"a":1}')
    assert p.read_text() == '{"a":1}'
    if _os.name != "nt":
        assert (p.stat().st_mode & 0o777) == 0o600


def test_require_600_rejects_loose(tmp_path):
    from nbs import email as em
    p = tmp_path / "t.json"; p.write_text("x"); _os.chmod(p, 0o644)
    if _os.name == "nt":
        em._require_600(p)
    else:
        with pytest.raises(PermissionError):
            em._require_600(p)


def test_assert_send_only_rejects_broad_token(tmp_path):
    from nbs import email as em
    p = tmp_path / "t.json"
    p.write_text(_json.dumps({"scopes": [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/drive"]}))
    with pytest.raises(em.TokenInvalid):
        em._assert_send_only(p)
    p.write_text(_json.dumps({"scopes": ["https://www.googleapis.com/auth/gmail.send"]}))
    em._assert_send_only(p)   # send-only → OK (no raise)


def test_ensure_config_dir_is_700(tmp_path, monkeypatch):
    from nbs import email as em
    monkeypatch.setattr(em, "config_dir", lambda: tmp_path / "cfg")
    em._ensure_config_dir()
    assert (tmp_path / "cfg").is_dir()
    if _os.name != "nt":
        assert ((tmp_path / "cfg").stat().st_mode & 0o777) == 0o700


def test_load_credentials_rejects_token_inside_repo_before_imports(tmp_path, monkeypatch):
    from nbs import email as em
    token = tmp_path / "token.json"
    token.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    with pytest.raises(em.TokenInvalid, match="outside"):
        em.load_credentials(token)


# --- Task 7: ledger + run_email + CLI ----------------------------------------

def test_already_sent_gate(tmp_path, monkeypatch):
    from nbs import email as em
    log = tmp_path / "log.csv"
    monkeypatch.setenv("AI_DAILY_EMAIL_LOG", str(log))
    assert em.already_sent("2026-07-03") is False
    em.record_sent("2026-07-03", "rid", ["a@x.com"], "S", ["id1"], "mid1", "sent")
    assert em.already_sent("2026-07-03") is True


def test_run_email_not_published_is_benign(tmp_path, monkeypatch):
    from nbs import email as em, publish
    work = _init_repo_with_origin(tmp_path)
    monkeypatch.setattr(publish, "ROOT", work)
    monkeypatch.setenv("AI_DAILY_EMAIL_LOG", str(tmp_path / "log.csv"))
    r = em.run_email("2026-07-03", dry_run=False)   # nothing pushed
    assert r["status"] == "not_published"


def test_run_email_dry_run_composes_but_does_not_send(tmp_path, monkeypatch):
    from nbs import email as em, publish
    work = _init_repo_with_origin(tmp_path)
    monkeypatch.setattr(publish, "ROOT", work)
    monkeypatch.setenv("AI_DAILY_EMAIL_LOG", str(tmp_path / "log.csv"))
    _publish_day(work, "2026-07-03")
    r = em.run_email("2026-07-03", dry_run=True)
    assert r["status"] == "dry_run"
    assert r["subject"] == "2026-07-03 Daily"
    assert em.already_sent("2026-07-03") is False   # dry-run must not record


def test_run_email_already_sent_skips(tmp_path, monkeypatch):
    from nbs import email as em, publish
    work = _init_repo_with_origin(tmp_path)
    monkeypatch.setattr(publish, "ROOT", work)
    monkeypatch.setenv("AI_DAILY_EMAIL_LOG", str(tmp_path / "log.csv"))
    _publish_day(work, "2026-07-03")
    em.record_sent("2026-07-03", "rid", ["a@x.com"], "S", ["x"], "mid", "sent")
    r = em.run_email("2026-07-03", dry_run=False)   # would send, but ledger says done
    assert r["status"] == "already_sent"


def test_run_email_sends_via_injected_sender(tmp_path, monkeypatch):
    from nbs import email as em, publish
    work = _init_repo_with_origin(tmp_path)
    monkeypatch.setattr(publish, "ROOT", work)
    monkeypatch.setenv("AI_DAILY_EMAIL_LOG", str(tmp_path / "log.csv"))
    _publish_day(work, "2026-07-03")
    sent = []
    monkeypatch.setattr(em, "load_credentials", lambda path=None: object())
    monkeypatch.setattr(em, "_gmail_send", lambda creds, msg, sender: (sent.append(msg) or f"gid{len(sent)}"))
    r = em.run_email("2026-07-03", dry_run=False)
    assert r["status"] == "sent" and len(sent) == 1
    assert r["message_id"].startswith("<") and "@ai-daily" in r["message_id"]
    assert em.already_sent("2026-07-03") is True


def test_dry_run_bypasses_already_sent_gate(tmp_path, monkeypatch):
    from nbs import email as em, publish
    work = _init_repo_with_origin(tmp_path)
    monkeypatch.setattr(publish, "ROOT", work)
    monkeypatch.setenv("AI_DAILY_EMAIL_LOG", str(tmp_path / "log.csv"))
    _publish_day(work, "2026-07-03")
    em.record_sent("2026-07-03", "rid", ["a@x.com"], "S", ["x"], "mid", "sent")
    assert em.run_email("2026-07-03", dry_run=True)["status"] == "dry_run"


# --- Task 8: reauth_google.py ------------------------------------------------

def test_reauth_uses_send_only_scope_and_external_path():
    from nbs import email as em
    spec = importlib.util.spec_from_file_location(
        "reauth_google", Path(config.ROOT) / "scripts" / "reauth_google.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    assert mod.SCOPES == em.SEND_SCOPES                 # NO broad scope inheritance
    assert not hasattr(mod, "existing_scopes")          # removed — never reads old token's scopes
