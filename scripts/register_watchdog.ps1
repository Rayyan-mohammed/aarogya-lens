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
$ScriptPath = "E:\aarogya-lens\scripts\watchdog.ps1"
$Command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""

schtasks /create /tn $TaskName /tr $Command /sc minute /mo 10 /f
if ($LASTEXITCODE -eq 0) {
    Write-Host "Registered scheduled task '$TaskName' - runs every 10 minutes."
} else {
    Write-Host "FAILED to register scheduled task (exit code $LASTEXITCODE)"
    exit 1
}
