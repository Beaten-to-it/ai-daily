import subprocess
from pathlib import Path

from nbs import config


SCRIPTS = Path(config.ROOT) / "scripts"


def _parse_powershell(path):
    command = (
        "$errors=$null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{path}',[ref]$null,[ref]$errors)>$null; "
        "if($errors.Count){$errors | ForEach-Object {$_.Message}; exit 1}"
    )
    return subprocess.run(["powershell", "-NoProfile", "-Command", command],
                          capture_output=True, text=True)


def test_windows_scripts_parse_and_do_not_depend_on_wsl():
    for name in ("run_daily.ps1", "install_scheduler.ps1"):
        path = SCRIPTS / name
        result = _parse_powershell(path)
        assert result.returncode == 0, result.stderr + result.stdout
        text = path.read_text(encoding="utf-8")
        assert "/home/" not in text and "wsl.exe" not in text and "bash" not in text


def test_run_daily_routes_prepare_publish_and_alert():
    text = (SCRIPTS / "run_daily.ps1").read_text(encoding="utf-8")
    assert "ValidateSet('Prepare','Publish','Alert')" in text
    assert "--prepare-only" in text and "--publish-only" in text and "--check-alert" in text
    assert "--shadow" in text and "Get-Command python" in text
    assert "PSNativeCommandUseErrorActionPreference" in text
    assert "[string]$Python" in text
    assert "@('-m', 'nbs.orchestrate', '--publish-only')" in text


def test_installer_is_whatif_by_default_and_defines_three_tasks():
    text = (SCRIPTS / "install_scheduler.ps1").read_text(encoding="utf-8")
    assert "[switch]$Apply" in text and "$dryRun = -not $Apply" in text
    assert "Register-ScheduledTask" in text and "if (-not $dryRun)" in text
    for command in ("python", "codex", "git", "hugo"):
        assert f"Get-Command {command}" in text
    assert "codex login status" in text
    assert "-Python" in text
    assert "import feedparser, requests, googleapiclient" in text
    for name in ("AI Daily Prepare", "AI Daily Publish", "AI Daily Alert"):
        assert name in text
    for time in ("06:00", "07:00", "12:00"):
        assert time in text
    assert "RestartCount 12" in text
    assert "RestartInterval (New-TimeSpan -Minutes 10)" in text
    assert "-AllowStartIfOnBatteries" in text
    assert "-DontStopIfGoingOnBatteries" in text
    assert "RepetitionInterval" not in text
    assert "Disable-ScheduledTask" in text
