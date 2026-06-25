# NuanceAI — Enhanced Launcher
# Starts Backend (port 8000) + Frontend (port 3000) with health checks

$HOST_ROOT = $PSScriptRoot

# ── Colours ───────────────────────────────────────────────────────────────────
function Banner {
    Clear-Host
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║       NuanceAI  ·  NeuroSync Platform    ║" -ForegroundColor Cyan
    Write-Host "  ║   Behavioral Intelligence Interview AI   ║" -ForegroundColor DarkCyan
    Write-Host "  ╚══════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function WaitForPort($port, $label, $maxSeconds = 30) {
    Write-Host "  ⏳  Waiting for $label (port $port)..." -ForegroundColor Yellow -NoNewline
    $waited = 0
    while ($waited -lt $maxSeconds) {
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $tcp.Connect("127.0.0.1", $port)
            $tcp.Close()
            Write-Host "  ✓  $label is UP" -ForegroundColor Green
            return $true
        } catch {}
        Start-Sleep -Milliseconds 1000
        $waited++
        Write-Host "." -NoNewline -ForegroundColor DarkGray
    }
    Write-Host ""
    Write-Host "  ✗  $label did not start within ${maxSeconds}s" -ForegroundColor Red
    return $false
}

# ── Kill any stale processes on our ports ─────────────────────────────────────
function KillPort($port) {
    $pids = netstat -ano 2>$null | Select-String ":$port\s" | ForEach-Object {
        ($_ -split '\s+')[-1]
    } | Sort-Object -Unique
    foreach ($p in $pids) {
        if ($p -match '^\d+$' -and $p -ne '0') {
            try { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } catch {}
        }
    }
}

Banner

Write-Host "  Clearing stale processes on ports 3000 and 8000..." -ForegroundColor DarkGray
KillPort 8000
KillPort 3000
Start-Sleep -Seconds 1

# ── Start Backend ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  [1/2]  Starting FastAPI Backend..." -ForegroundColor White
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "& { Set-Location '$HOST_ROOT'; Write-Host '  [Backend] Starting...' -ForegroundColor Cyan; .\.venv\Scripts\Activate.ps1; python -m uvicorn backend.main:app --port 8000 --host 127.0.0.1; Read-Host 'Press Enter to close' }" `
    -WindowStyle Normal

# ── Start Frontend ────────────────────────────────────────────────────────────
Write-Host "  [2/2]  Starting Next.js Frontend..." -ForegroundColor White
Start-Process cmd -ArgumentList "/k",
    "title NuanceAI Frontend && cd /d `"$HOST_ROOT\frontend`" && npm run dev"

# ── Wait for both ports ────────────────────────────────────────────────────────
Write-Host ""
$backendUp  = WaitForPort 8000 "Backend API"  40
$frontendUp = WaitForPort 3000 "Frontend App" 60

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ══════════════════════════════════════════" -ForegroundColor DarkCyan
if ($backendUp -and $frontendUp) {
    Write-Host "  ✅  Both servers are running!" -ForegroundColor Green
} elseif ($frontendUp) {
    Write-Host "  ⚠️   Frontend is up, backend needs a moment." -ForegroundColor Yellow
} else {
    Write-Host "  ⚠️   Servers still starting — check the console windows." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  🌐  App  →  http://localhost:3000" -ForegroundColor Cyan
Write-Host "  🔌  API  →  http://localhost:8000/docs" -ForegroundColor DarkCyan
Write-Host "  📊  Demo →  http://localhost:3000/session/demo/results" -ForegroundColor DarkCyan
Write-Host "  ══════════════════════════════════════════" -ForegroundColor DarkCyan
Write-Host ""

# Open browser automatically
if ($frontendUp) {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:3000"
}

Write-Host "  Press any key to close this launcher..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
