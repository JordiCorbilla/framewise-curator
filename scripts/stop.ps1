$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot '.local\backend.pid'
if (Test-Path -LiteralPath $pidFile) {
    $serverPid = [int](Get-Content -LiteralPath $pidFile)
    $serverProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $serverPid"
    if ($serverProcess -and $serverProcess.CommandLine -like '*framewise.api.app:app*') { Stop-Process -Id $serverPid }
    elseif ($serverProcess) { throw 'Stored PID belongs to another process; refusing to stop it.' }
    Remove-Item -LiteralPath $pidFile
}
