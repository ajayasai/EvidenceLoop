param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    throw 'Create the project Python environment and install requirements.lock.txt first; see README.md.'
}
& $taskPython scripts/bootstrap_db.py
if ($LASTEXITCODE -ne 0) { throw 'Database setup failed.' }
if (-not (Test-Path -LiteralPath 'apps\web\dist\index.html')) {
    throw 'Build the interface with npm ci and npm run build in apps/web first.'
}
& $taskPython -m uvicorn services.api.app.main:app --host 127.0.0.1 --port $Port --no-access-log
