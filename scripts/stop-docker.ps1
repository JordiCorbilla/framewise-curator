$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $projectRoot '.local\docker-settings.json'
if (!(Test-Path -LiteralPath $statePath)) { Write-Host 'No Docker workspace has been started with this launcher.'; exit 0 }
$saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
$env:FRAMEWISE_PHOTOS_PATH = $saved.photos
$env:FRAMEWISE_WORKSPACE_ID = $saved.workspace
$env:FRAMEWISE_PORT = [string]$saved.port
Push-Location $projectRoot
try {
    docker compose stop
    if ($LASTEXITCODE) { throw 'Docker could not stop Framewise.' }
    Write-Host 'Framewise stopped. Collections, selections and models remain in the Docker volume.'
} finally { Pop-Location }
