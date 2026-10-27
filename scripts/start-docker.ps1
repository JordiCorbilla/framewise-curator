param([string]$Photos, [ValidateRange(1024,65535)][int]$Port = 8765, [switch]$NoBrowser, [switch]$Build)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (!(Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install Docker Desktop first: https://www.docker.com/products/docker-desktop/ . Then start Docker and reopen this launcher.' }
$dockerOS = docker info --format '{{.OSType}}'
if ($LASTEXITCODE -or $dockerOS -ne 'linux') { throw 'Start Docker Desktop with Linux containers, then try again.' }
$statePath = Join-Path $projectRoot '.local\docker-settings.json'
if (!$Photos -and (Test-Path -LiteralPath $statePath)) {
    $saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $Photos = $saved.photos
    if (!$PSBoundParameters.ContainsKey('Port') -and $saved.port) { $Port = [int]$saved.port }
}
if (!$Photos -or !(Test-Path -LiteralPath $Photos -PathType Container)) {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = 'Choose the folder containing your photo collections. Framewise mounts it read-only.'
    $dialog.ShowNewFolderButton = $false
    $dialog.RootFolder = [System.Environment+SpecialFolder]::MyComputer
    if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { Write-Host 'No folder selected. Nothing started.'; exit 0 }
    $Photos = $dialog.SelectedPath
    $dialog.Dispose()
}
$Photos = (Resolve-Path -LiteralPath $Photos).ProviderPath
$hash = [System.Security.Cryptography.SHA256]::Create()
try { $workspaceId = ([BitConverter]::ToString($hash.ComputeHash([Text.Encoding]::UTF8.GetBytes($Photos.ToLowerInvariant())))).Replace('-','').Substring(0,12).ToLowerInvariant() } finally { $hash.Dispose() }
$env:FRAMEWISE_PHOTOS_PATH = $Photos
$env:FRAMEWISE_WORKSPACE_ID = $workspaceId
$env:FRAMEWISE_PORT = [string]$Port
Push-Location $projectRoot
try {
    # Fail visibly if another app already owns the URL. Do not stop unrelated services.
    $current = docker compose ps --status running --quiet framewise
    if (!$current) {
        $listener = [System.Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$Port)
        try { $listener.Start() } catch { throw "Port $Port is in use. Stop your other Framewise server or run scripts/start-docker.ps1 -Port 8766." } finally { $listener.Stop() }
    }
    $bundleImage = Join-Path $projectRoot 'framewise-image.tar'
    $existing = docker image ls framewise:0.2.0 --quiet
    $bundleManifestPath = Join-Path $projectRoot 'bundle-manifest.json'
    $reloadBundle = !$existing
    if ((Test-Path -LiteralPath $bundleManifestPath) -and (Test-Path -LiteralPath $bundleImage)) {
        $bundleManifest = Get-Content -LiteralPath $bundleManifestPath -Raw | ConvertFrom-Json
        $currentImageId = docker image inspect framewise:0.2.0 --format '{{.Id}}' 2>$null
        if ($bundleManifest.image_id -and $currentImageId -ne $bundleManifest.image_id) { $reloadBundle = $true }
    }
    if ($reloadBundle -and (Test-Path -LiteralPath $bundleImage)) {
        Write-Host 'Loading the bundled Framewise image. This only happens once…'
        if ($bundleManifest -and $bundleManifest.files.'framewise-image.tar') {
            $actual = (Get-FileHash -LiteralPath $bundleImage -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actual -ne $bundleManifest.files.'framewise-image.tar') { throw 'Bundled image checksum mismatch. Download/extract the ZIP again.' }
        }
        docker image load --input $bundleImage
        if ($LASTEXITCODE) { throw 'Bundled image could not be loaded.' }
    }
    if ($Build -or (!(docker image ls framewise:0.2.0 --quiet))) {
        Write-Host 'Building Framewise. No Python or Node installation is needed on your computer.'
        docker compose build
        if ($LASTEXITCODE) { throw 'Docker image build failed. Check your connection and the messages above.' }
    }
    docker compose up -d --no-build --wait --wait-timeout 180
    if ($LASTEXITCODE) { throw 'Framewise did not become healthy. Inspect: docker compose logs --tail 80' }
    New-Item -ItemType Directory -Force (Split-Path -Parent $statePath) | Out-Null
    @{photos=$Photos;workspace=$workspaceId;port=$Port} | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
    Write-Host "Framewise is ready: http://127.0.0.1:$Port"
    Write-Host 'Use Scan > Choose folder. Optional AI weights can be installed once from Settings.'
    if (!$NoBrowser) { Start-Process "http://127.0.0.1:$Port" }
} finally { Pop-Location }
