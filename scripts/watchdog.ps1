# Watchdog: keeps the backend, tunnel, and benchmark alive without manual intervention.
# Registered as a Windows Scheduled Task (see scripts/register_watchdog.ps1) so it runs
# on its own schedule regardless of whether anyone is actively working in this repo.

$Root = "E:\aarogya-lens"
$LogFile = "$Root\scripts\watchdog.log"
$CloudflaredExe = "C:\Program Files (x86)\cloudflared\cloudflared.exe"

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $LogFile -Value $line
}

# First thing, unconditionally — so if anything below throws, there's still proof
# the task actually fired under Task Scheduler and a way to see where it died.
Log "watchdog fired"

try {

Set-Location $Root

# ── 1. Backend (FastAPI on :8000) ──────────────────────────────────────────
$backendUp = $false
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 5 -UseBasicParsing
    $backendUp = $resp.StatusCode -eq 200
} catch { $backendUp = $false }

if (-not $backendUp) {
    Log "backend down, restarting"
    Start-Process -FilePath "$Root\.venv\Scripts\python.exe" `
        -ArgumentList "-m", "uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000" `
        -WorkingDirectory $Root -WindowStyle Hidden
    Start-Sleep -Seconds 8
} else {
    Log "backend ok"
}

# ── 2. Cloudflare tunnel ────────────────────────────────────────────────────
$tunnelProc = Get-Process -Name cloudflared -ErrorAction SilentlyContinue
$tunnelUp = $false
if ($tunnelProc) {
    # A running process isn't proof the tunnel is actually reachable — quick
    # tunnels can wedge. Verify against the URL we last recorded, if any.
    $urlFile = "$Root\scripts\.tunnel_url"
    if (Test-Path $urlFile) {
        $lastUrl = (Get-Content $urlFile -Raw).Trim()
        try {
            $resp = Invoke-WebRequest -Uri "$lastUrl/health" -TimeoutSec 8 -UseBasicParsing
            $tunnelUp = $resp.StatusCode -eq 200
        } catch { $tunnelUp = $false }
    }
}

if (-not $tunnelUp) {
    Log "tunnel down, restarting"
    if ($tunnelProc) { Stop-Process -Id $tunnelProc.Id -Force -ErrorAction SilentlyContinue }

    $tunnelLog = "$Root\scripts\.tunnel_stdout"
    Remove-Item $tunnelLog -ErrorAction SilentlyContinue
    # --protocol http2 (TCP) instead of the default quic (UDP) — this network has
    # blocked outbound UDP to Cloudflare's edge before, which leaves quic retrying
    # forever with no error, just silence. http2 routes around that.
    Start-Process -FilePath $CloudflaredExe -ArgumentList "tunnel", "--protocol", "http2", "--url", "http://localhost:8000" `
        -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardError $tunnelLog

    # cloudflared prints the URL to stderr within a few seconds of starting
    $newUrl = $null
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 2
        if (Test-Path $tunnelLog) {
            $match = Select-String -Path $tunnelLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($match) { $newUrl = $match.Matches[0].Value; break }
        }
    }

    if ($newUrl) {
        Log "new tunnel url: $newUrl"
        Set-Content -Path "$Root\scripts\.tunnel_url" -Value $newUrl -NoNewline

        # Update the original frontend (no build step) and redeploy straight to gh-pages.
        $indexPath = "$Root\frontend\index.html"
        (Get-Content $indexPath -Raw) -replace "const API_BASE = '[^']*';", "const API_BASE = '$newUrl';" |
            Set-Content -Path $indexPath -NoNewline

        # Keep the Next.js env file current too, even though rebuilding it here is
        # skipped deliberately — that build is memory-heavy and unreliable to run
        # unattended on this machine; it gets rebuilt manually when convenient.
        Set-Content -Path "$Root\frontend-nextjs\.env.local" -Value "NEXT_PUBLIC_API_BASE=$newUrl" -NoNewline

        git add frontend/index.html frontend-nextjs/.env.local 2>&1 | Out-Null
        git commit -m "watchdog: tunnel url rotated to $newUrl" 2>&1 | Out-Null
        git push 2>&1 | Out-Null

        $tmpWorktree = "$env:TEMP\watchdog-gh-pages"
        Remove-Item -Recurse -Force $tmpWorktree -ErrorAction SilentlyContinue
        git worktree add $tmpWorktree gh-pages 2>&1 | Out-Null
        Copy-Item $indexPath "$tmpWorktree\index.html" -Force
        Push-Location $tmpWorktree
        git add index.html 2>&1 | Out-Null
        git commit -m "watchdog: tunnel url rotated to $newUrl" 2>&1 | Out-Null
        git push origin gh-pages 2>&1 | Out-Null
        Pop-Location
        git worktree remove $tmpWorktree --force 2>&1 | Out-Null

        Log "frontend redeployed with new url"
    } else {
        Log "ERROR: could not capture new tunnel url from cloudflared output"
    }
} else {
    Log "tunnel ok"
}

# ── 3. Benchmark eval runner ────────────────────────────────────────────────
$evalRunning = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "eval_runner" }

# eval_runner.py deletes the checkpoint file only on genuine full completion, so its
# presence is the reliable "still has work to do" signal — not eval_results.json,
# which can be a stale leftover from an earlier (possibly discarded/contaminated) run.
$checkpointPath = "$Root\backend\evaluation\eval_checkpoint.json"

if (-not $evalRunning -and (Test-Path $checkpointPath)) {
    Log "benchmark not running and checkpoint shows unfinished work, restarting (will resume)"
    Start-Process -FilePath "$Root\.venv\Scripts\python.exe" `
        -ArgumentList "-u", "-m", "backend.evaluation.eval_runner", "--model", "groq" `
        -WorkingDirectory $Root -WindowStyle Hidden `
        -RedirectStandardOutput "$Root\scripts\.eval_stdout"
} elseif ($evalRunning) {
    Log "benchmark ok"
} else {
    Log "benchmark finished (no checkpoint left) - nothing to do"
}

Log "watchdog done"

} catch {
    Log "FATAL: $_"
}
