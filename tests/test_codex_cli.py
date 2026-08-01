import json
import subprocess
from pathlib import Path

import pytest

from nbs import codex_cli


def _schema(path: Path) -> Path:
    path.write_text(
        json.dumps({
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        }),
        encoding="utf-8",
    )
    return path


def test_run_json_uses_isolated_read_only_exec_and_returns_output(tmp_path, monkeypatch):
    seen = {}

    def fake_run(args, **kwargs):
        seen.update(args=args, kwargs=kwargs)
        output = Path(args[args.index("--output-last-message") + 1])
        output.write_text('{"ok": true}', encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "", "progress")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(codex_cli, "_codex_executable", lambda: "codex.cmd")
    result = codex_cli.run_json("untrusted input", _schema(tmp_path / "schema.json"), tmp_path, 30)

    assert result == {"ok": True}
    assert seen["args"][:2] == ["codex.cmd", "exec"]
    assert "--ephemeral" in seen["args"]
    assert seen["args"][seen["args"].index("--sandbox") + 1] == "read-only"
    assert "--ignore-user-config" in seen["args"]
    assert "--ignore-rules" in seen["args"]
    assert "--skip-git-repo-check" in seen["args"]
    assert seen["args"][-1] == "-"
    assert seen["kwargs"]["input"] == "untrusted input"
    assert seen["kwargs"]["cwd"] == str(tmp_path)
    assert "OPENAI_API_KEY" not in seen["kwargs"]["env"]


def test_run_json_rejects_stale_output_after_failed_exec(tmp_path, monkeypatch):
    output = tmp_path / "last-message.json"
    output.write_text('{"ok": true}', encoding="utf-8")

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 1, "", "authentication failed"),
    )

    with pytest.raises(codex_cli.CodexExecError, match="authentication failed"):
        codex_cli.run_json("prompt", _schema(tmp_path / "schema.json"), tmp_path, 30)
    assert not output.exists()


def test_run_json_reports_timeout_without_output(tmp_path, monkeypatch):
    def timeout(args, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs["timeout"], stderr="too slow")

    monkeypatch.setattr(subprocess, "run", timeout)

    with pytest.raises(codex_cli.CodexExecError, match="timed out after 7s"):
        codex_cli.run_json("prompt", _schema(tmp_path / "schema.json"), tmp_path, 7)


def test_self_test_uses_boolean_schema_and_prints_result(monkeypatch, capsys):
    seen = {}
    def fake_run_json(prompt, schema, work_dir, timeout):
        seen.update(
            prompt=prompt,
            schema=json.loads(schema.read_text(encoding="utf-8")),
            work_dir=work_dir,
            timeout=timeout,
        )
        return {"ok": True}
    monkeypatch.setattr(codex_cli, "run_json", fake_run_json)

    assert codex_cli.main(["--self-test"]) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True}
    assert seen["schema"]["properties"]["ok"] == {"type": "boolean"}
    assert seen["work_dir"].name == "work"


def test_windows_resolves_the_executable_cmd_shim(monkeypatch):
    monkeypatch.setattr(codex_cli.os, "name", "nt")
    monkeypatch.setattr(
        codex_cli.shutil,
        "which",
        lambda name: r"C:\tools\codex.cmd" if name == "codex.cmd" else None,
    )
    assert codex_cli._codex_executable() == r"C:\tools\codex.cmd"
