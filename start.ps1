# NuanceAI — Start both backend and frontend
# Single entry point: http://localhost:3000

Write-Host ""
Write-Host "  NuanceAI / NeuroSync Platform" -ForegroundColor Cyan
Write-Host "  Starting backend (port 8000) + frontend (port 3000)..." -ForegroundColor Gray
Write-Host ""

# Start FastAPI backend in a new window (activating virtual environment first)
Start-Process cmd -ArgumentList '/k', "cd /d `"$PSScriptRoot`" && .venv\Scripts\activate.bat && python -m uvicorn backend.main:app --reload --port 8000 --host 127.0.0.1"

# Start Next.js frontend in a new window (use cmd to bypass PowerShell npm.ps1 restriction)
Start-Process cmd -ArgumentList '/k', "cd /d `"$PSScriptRoot\frontend`" && npm run dev"

# Wait for Next.js to be ready, then open in default browser
Write-Host "  Waiting 12 seconds for servers to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 12
Start-Process "http://localhost:3000"

Write-Host "  Both servers are starting in separate windows." -ForegroundColor Green
Write-Host ""
Write-Host "  Open this in your browser (wait ~10 seconds):" -ForegroundColor White
Write-Host ""
Write-Host "    http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend API docs: http://localhost:8000/docs" -ForegroundColor Gray
Write-Host ""
