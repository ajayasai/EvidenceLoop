$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPgCtl = Join-Path $taskRoot '.runtime\pgsql\bin\pg_ctl.exe'
$taskData = Join-Path $taskRoot '.runtime\pgdata'
if (Test-Path -LiteralPath $taskPgCtl) {
    & $taskPgCtl -D $taskData -m fast -w stop
}
