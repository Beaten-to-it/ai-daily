[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Prepare','Publish','Alert')]
    [string]$Mode,
    [ValidatePattern('^[0-9]{4}-[0-9]{2}-[0-9]{2}$')]
    [string]$Date,
    [switch]$Shadow,
    [string]$Python
)

$ErrorActionPreference = 'Stop'
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}
$python = if ($Python) {
    (Resolve-Path -LiteralPath $Python -ErrorAction Stop).Path
} else {
    (Get-Command python -ErrorAction Stop).Source
}
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$exitCode = 1

Push-Location $repo
try {
    if ($Mode -eq 'Prepare') {
        if (-not $Date) { $Date = (Get-Date).ToString('yyyy-MM-dd') }
        $arguments = @('-m', 'nbs.orchestrate', '--date', $Date, '--prepare-only')
        if ($Shadow) { $arguments += '--shadow' }
        & $python @arguments
    }
    elseif ($Mode -eq 'Publish') {
        $arguments = @('-m', 'nbs.orchestrate', '--publish-only')
        if ($Date) { $arguments += @('--date', $Date) }
        & $python @arguments
    }
    else {
        if (-not $Date) { $Date = (Get-Date).ToString('yyyy-MM-dd') }
        & $python -m nbs.schedule --date $Date --check-alert
    }
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $exitCode
