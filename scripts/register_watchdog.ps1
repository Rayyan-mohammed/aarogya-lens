# Registers the watchdog as a Windows Scheduled Task, running every 10 minutes
# indefinitely, so backend/tunnel/benchmark come back up on their own after a
# sleep/restart instead of needing someone to notice and fix it by hand.
#
# Uses schtasks.exe rather than Register-ScheduledTask — the latter's XML-import
# path needs admin rights on this machine, schtasks doesn't for a plain per-user
# recurring task.
# Run this once:
#   powershell -ExecutionPolicy Bypass -File scripts\register_watchdog.ps1

$TaskName = "BharatHealthWatchdog"
# run_watchdog.vbs starts watchdog.ps1 with no console window, so nothing can close or
# Ctrl+C it mid-run (run_watchdog.bat is for running it by hand). No spaces in these
# paths, so no quoting is needed inside schtasks' /tr.
$Command = "$env:SystemRoot\System32\wscript.exe E:\aarogya-lens\scripts\run_watchdog.vbs"

schtasks /create /tn $TaskName /tr $Command /sc minute /mo 10 /f
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAILED to register scheduled task (exit code $LASTEXITCODE)"
    exit 1
}

# schtasks can't set power options, and its defaults skip runs on battery — which left
# the live site down whenever the laptop was unplugged. Also catch up right after a wake
# instead of waiting for the next 10-minute slot. Editing an existing per-user task this
# way doesn't need admin rights.
$task = Get-ScheduledTask -TaskName $TaskName
$task.Settings.DisallowStartIfOnBatteries = $false
$task.Settings.StopIfGoingOnBatteries = $false
$task.Settings.StartWhenAvailable = $true
$task | Set-ScheduledTask | Out-Null

Write-Host "Registered scheduled task '$TaskName' - runs every 10 minutes, on battery too."
