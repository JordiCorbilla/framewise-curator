param([switch]$WithAI, [switch]$DownloadModels)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location "$projectRoot\backend"
try {
    if ($WithAI -or $DownloadModels) { uv sync --frozen --python 3.11 --extra dev --extra raw --extra ai }
    else { uv sync --frozen --python 3.11 --extra dev --extra raw }
    if ($LASTEXITCODE) { throw 'Python dependency installation failed' }
    if ($DownloadModels) {
        # The switch is explicit user consent to this one-time download.
        & '.\.venv\Scripts\python.exe' '..\scripts\install_models.py' --approve-download
        if ($LASTEXITCODE) { throw 'Model installation failed' }
    }
} finally { Pop-Location }
Push-Location "$projectRoot\frontend"
try {
    npm ci --no-audit --no-fund
    if ($LASTEXITCODE) { throw 'Frontend dependency installation failed' }
    npm run build
    if ($LASTEXITCODE) { throw 'Frontend build failed' }
} finally { Pop-Location }
Write-Host 'Ready. Run .\scripts\start.ps1. ExifTool: winget install --id OliverBetz.ExifTool --exact'
