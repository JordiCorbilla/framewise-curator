param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $projectRoot 'backend\.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $runtime)) { throw 'Run .\scripts\setup.ps1 -WithAI first.' }
if (!(Test-Path -LiteralPath "$projectRoot\frontend\dist\index.html")) { throw 'Build frontend: cd frontend; npm run build' }
$running = $false
try { $health = Invoke-RestMethod 'http://127.0.0.1:8765/api/health' -TimeoutSec 2; $running = $health.status -eq 'ok' -and $null -ne $health.data_directory } catch { }
if (!$running) {
    New-Item -ItemType Directory -Force "$projectRoot\.local" | Out-Null
    $process = Start-Process -FilePath $runtime -ArgumentList '-m','uvicorn','framewise.api.app:app','--host','127.0.0.1','--port','8765' -WorkingDirectory "$projectRoot\backend" -WindowStyle Hidden -RedirectStandardOutput "$projectRoot\.local\backend.log" -RedirectStandardError "$projectRoot\.local\backend-error.log" -PassThru
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 500
        if ($process.HasExited) { throw "Backend failed. See $projectRoot\.local\backend-error.log" }
        try { $health = Invoke-RestMethod 'http://127.0.0.1:8765/api/health' -TimeoutSec 2; $running = $health.status -eq 'ok'; if ($running) { break } } catch { }
    }
    if (!$running) { throw 'Backend did not become ready. Inspect .local/backend-error.log' }
    Set-Content -LiteralPath "$projectRoot\.local\backend.pid" -Value $health.process_id
}
Write-Host 'Framewise is ready: http://127.0.0.1:8765'
if (!$NoBrowser) { Start-Process 'http://127.0.0.1:8765' }
