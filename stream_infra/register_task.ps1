<#
register_task.ps1 - registers "FSR Volatility Radar Stream" in Task Scheduler.

Runs run_stream.ps1 automatically when you log in, and restarts it
up to 5 times (1 min apart) if the whole process dies unexpectedly.
run_stream.ps1 already handles ffmpeg-level restarts on its own; this
is the outer safety net for the PowerShell process itself.

Run once, as your normal user (no admin needed for an AtLogOn task):
    powershell -File stream_infra\register_task.ps1

Remove it later with:
    Unregister-ScheduledTask -TaskName "FSR Volatility Radar Stream" -Confirm:$false
#>

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ScriptPath = Join-Path $PSScriptRoot "run_stream.ps1"
$TaskName = "FSR Volatility Radar Stream"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $RepoRoot

$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 0) `
    -DontStopOnIdleEnd -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Runs the FSR volatility radar 24/7 stream at logon." `
    -Force | Out-Null

Write-Output "Registered scheduled task: $TaskName"
Write-Output "It will start automatically next time you log in."
Write-Output "To start it right now without logging out: Start-ScheduledTask -TaskName '$TaskName'"
