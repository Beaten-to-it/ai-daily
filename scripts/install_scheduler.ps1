[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'
if ($Apply -and $WhatIf) { throw 'Choose either -Apply or -WhatIf.' }
$dryRun = -not $Apply

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = (Resolve-Path (Join-Path $PSScriptRoot 'run_daily.ps1')).Path
$powershellCommand = Get-Command powershell.exe -ErrorAction SilentlyContinue
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$codexCommand = Get-Command codex -ErrorAction SilentlyContinue
$gitCommand = Get-Command git -ErrorAction SilentlyContinue
$hugoCommand = Get-Command hugo -ErrorAction SilentlyContinue

$powershell = if ($powershellCommand) { $powershellCommand.Source } else { '<missing>' }
$python = if ($pythonCommand) { $pythonCommand.Source } else { '<missing>' }
$codex = if ($codexCommand) { $codexCommand.Source } else { '<missing>' }
$git = if ($gitCommand) { $gitCommand.Source } else { '<missing>' }
$hugo = if ($hugoCommand) { $hugoCommand.Source } else { '<missing>' }
$timeZone = [System.TimeZoneInfo]::Local.Id

$taskPlan = @(
    [pscustomobject]@{ Name = 'AI Daily Prepare'; Time = '06:00'; Mode = 'Prepare'; Retry = 'none' },
    [pscustomobject]@{ Name = 'AI Daily Publish'; Time = '07:00'; Mode = 'Publish'; Retry = '10 minutes for 2 hours' },
    [pscustomobject]@{ Name = 'AI Daily Alert'; Time = '12:00'; Mode = 'Alert'; Retry = 'none' }
)

Write-Host "Mode: $(if ($dryRun) { 'WhatIf' } else { 'Apply' })"
Write-Host "Repository: $repo"
Write-Host "Runner: $runner"
Write-Host "Python: $python"
Write-Host "Codex: $codex"
Write-Host "Git: $git"
Write-Host "Hugo: $hugo"
Write-Host "Time zone: $timeZone"
$taskPlan | Format-Table -AutoSize

$missing = @()
if (-not $powershellCommand) { $missing += 'powershell.exe' }
if (-not $pythonCommand) { $missing += 'python' }
if (-not $codexCommand) { $missing += 'codex' }
if (-not $gitCommand) { $missing += 'git' }
if (-not $hugoCommand) { $missing += 'hugo' }
if ($missing.Count) { throw "Missing required commands: $($missing -join ', ')" }
if ($timeZone -notin @('Korea Standard Time', 'Asia/Seoul')) {
    throw "The scheduler contract requires a KST host; current time zone is $timeZone"
}

& $git -C $repo rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) { throw "Not a Git working tree: $repo" }

# codex login status is read-only and must succeed before unattended tasks are installed.
$previousErrorPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    $loginOutput = & $codex login status 2>&1
    $loginExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorPreference
}
if ($loginExitCode -ne 0) { throw "Codex login is not ready: $loginOutput" }

& $python -c 'import feedparser, requests, googleapiclient'
if ($LASTEXITCODE -ne 0) { throw "Required Python packages are unavailable in $python" }

if (-not $dryRun) {
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $publishSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -RestartCount 12 -RestartInterval (New-TimeSpan -Minutes 10)
    $principal = New-ScheduledTaskPrincipal `
        -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
        -LogonType Interactive -RunLevel Limited

    foreach ($item in $taskPlan) {
        $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Mode $($item.Mode) -Python `"$python`""
        $action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $repo
        $trigger = New-ScheduledTaskTrigger -Daily -At $item.Time
        $taskSettings = if ($item.Mode -eq 'Publish') { $publishSettings } else { $settings }
        Register-ScheduledTask -TaskName $item.Name -Action $action -Trigger $trigger `
            -Settings $taskSettings -Principal $principal -Description 'Codex-native Daily AI publisher' -Force | Out-Null
        Disable-ScheduledTask -TaskName $item.Name | Out-Null
    }
    Write-Host 'Scheduled tasks installed disabled. Enable them only after the activation gate passes.'
}
else {
    Write-Host 'WhatIf only: no scheduled task was registered. Re-run with -Apply to install.'
}
