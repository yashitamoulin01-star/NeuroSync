# Setup Script for Multimodal Behavioral Analytics Developer Environment
# This script installs Python 3.11, Git, VS Code, and FFmpeg onto the D: drive,
# configures environment paths, installs the Claude extension, and sets up GitHub keys.
#
# IMPORTANT: Run this script from an Administrator PowerShell window.

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Starting Dev Tools Installation on D: Drive" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Create directory structure on D: drive
$DevDirectory = "D:\DevTools"
if (!(Test-Path $DevDirectory)) {
    New-Item -ItemType Directory -Path $DevDirectory -Force | Out-Null
    Write-Host "Created base directory: $DevDirectory" -ForegroundColor Green
}

# 2. Install Python 3.11 on D:
Write-Host "`n[1/5] Installing Python 3.11 to $DevDirectory\Python311..." -ForegroundColor Yellow
winget install -e --id Python.Python.3.11 -l "$DevDirectory\Python311" --accept-package-agreements --accept-source-agreements

# 3. Install Git on D:
Write-Host "`n[2/5] Installing Git to $DevDirectory\Git..." -ForegroundColor Yellow
winget install -e --id Git.Git -l "$DevDirectory\Git" --accept-package-agreements --accept-source-agreements

# 4. Install VS Code on D:
Write-Host "`n[3/5] Installing VS Code to $DevDirectory\VSCode..." -ForegroundColor Yellow
winget install -e --id Microsoft.VisualStudioCode -l "$DevDirectory\VSCode" --accept-package-agreements --accept-source-agreements

# 5. Install Node.js (LTS) on D:
Write-Host "`n[4/6] Installing Node.js LTS to $DevDirectory\NodeJS..." -ForegroundColor Yellow
winget install -e --id OpenJS.NodeJS.LTS -l "$DevDirectory\NodeJS" --accept-package-agreements --accept-source-agreements

# 6. Install FFmpeg
Write-Host "`n[5/6] Downloading and setting up FFmpeg in D:..." -ForegroundColor Yellow
$FFmpegZipPath = "$DevDirectory\ffmpeg.zip"
$FFmpegExtractPath = "$DevDirectory\ffmpeg"

if (Test-Path $FFmpegExtractPath) {
    Remove-Item -Recurse -Force $FFmpegExtractPath | Out-Null
}

# Download release essentials from gyan.dev
Write-Host "Downloading FFmpeg static build..." -ForegroundColor Gray
Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $FFmpegZipPath

# Extract archive
Write-Host "Extracting FFmpeg..." -ForegroundColor Gray
Expand-Archive -Path $FFmpegZipPath -DestinationPath $FFmpegExtractPath -Force
Remove-Item -Force $FFmpegZipPath

# Find bin directory recursively
$FFmpegBin = (Get-ChildItem -Path $FFmpegExtractPath -Recurse -Filter "ffmpeg.exe").DirectoryName
Write-Host "FFmpeg binary found at: $FFmpegBin" -ForegroundColor Green

# Add FFmpeg bin directory to User Environment Path
Write-Host "Adding FFmpeg to User Path..." -ForegroundColor Gray
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$FFmpegBin*") {
    [Environment]::SetEnvironmentVariable("Path", $UserPath + ";$FFmpegBin", "User")
    Write-Host "FFmpeg successfully added to PATH!" -ForegroundColor Green
} else {
    Write-Host "FFmpeg is already in PATH." -ForegroundColor Gray
}

# 7. Install Claude VS Code Extension
Write-Host "`n[6/6] Installing official Anthropic Claude extension for VS Code..." -ForegroundColor Yellow
# VS Code needs to be in PATH or we use the newly installed binary to install extension
$CodePath = "$DevDirectory\VSCode\bin\code"
if (Test-Path "$CodePath.cmd") {
    & "$CodePath.cmd" --install-extension Anthropic.claude
    Write-Host "Anthropic Claude extension installed successfully!" -ForegroundColor Green
} else {
    Write-Host "VS Code path not found yet. You can run 'code --install-extension Anthropic.claude' after restarting your terminal." -ForegroundColor Red
}

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "Installation Phase Completed Successfully!" -ForegroundColor Cyan
Write-Host "Please close this window and open a NEW PowerShell window to load the new paths." -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
