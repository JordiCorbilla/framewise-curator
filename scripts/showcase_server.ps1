param([switch]$Stop)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$showcaseData = Join-Path $workspace '.local\showcase-data'
if ($Stop) {
    $health = Invoke-RestMethod 'http://127.0.0.1:5173/api/health'
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($health.process_id)"
    if ($health.data_directory -ne $showcaseData -or $process.CommandLine -notmatch 'framewise\.api\.app:app' -or $process.CommandLine -notmatch '--port 5173') {
        throw 'Port 5173 is not the isolated Framewise showcase server; refusing to stop it.'
    }
    Stop-Process -Id $process.ProcessId
    Write-Output 'Isolated showcase server stopped.'
} else {
    $env:FRAMEWISE_DATA_DIR = $showcaseData
    try {
        Start-Process -FilePath (Join-Path $workspace 'backend\.venv\Scripts\python.exe') -ArgumentList '-m','uvicorn','framewise.api.app:app','--app-dir',"`"$workspace\backend`"",'--host','127.0.0.1','--port','5173' -WindowStyle Hidden -RedirectStandardOutput "$showcaseData\server.log" -RedirectStandardError "$showcaseData\server.err.log"
    } finally {
        Remove-Item Env:FRAMEWISE_DATA_DIR
    }
}
