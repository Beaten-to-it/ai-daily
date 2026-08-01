import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


_ENV_ALLOWLIST = {
    "APPDATA",
    "CODEX_HOME",
    "COMSPEC",
    "HOME",
    "LANG",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "USERPROFILE",
    "WINDIR",
}


class CodexExecError(RuntimeError):
    pass


def _clean_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key.upper() in _ENV_ALLOWLIST}


def _codex_executable() -> str:
    if os.name == "nt":
        return shutil.which("codex.cmd") or shutil.which("codex.exe") or "codex.cmd"
    return shutil.which("codex") or "codex"


def _message(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def run_json(prompt: str, schema: Path, work_dir: Path, timeout: int) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    output = work_dir / "last-message.json"
    output.unlink(missing_ok=True)
    args = [
        _codex_executable(),
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--cd",
        str(work_dir),
        "--output-schema",
        str(schema.resolve()),
        "--output-last-message",
        str(output),
        "-",
    ]
    try:
        result = subprocess.run(
            args,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(work_dir),
            env=_clean_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise CodexExecError(f"codex exec timed out after {timeout}s: {_message(exc.stderr)[-2000:]}") from exc
    except OSError as exc:
        raise CodexExecError(f"codex exec could not start: {exc}") from exc

    if result.returncode != 0:
        raise CodexExecError(f"codex exec failed ({result.returncode}): {_message(result.stderr)[-2000:]}")
    if not output.exists():
        raise CodexExecError("codex exec succeeded without structured output")
    try:
        data = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CodexExecError(f"codex exec returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CodexExecError("codex exec output root is not an object")
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if not args.self_test:
        parser.error("--self-test is required")

    with tempfile.TemporaryDirectory(prefix="ai-daily-codex-") as temp:
        base = Path(temp)
        schema = base / "self-test.schema.json"
        schema.write_text(json.dumps({
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        }), encoding="utf-8")
        result = run_json(
            'Return JSON with "ok" set to true.', schema, base / "work", timeout=120
        )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
