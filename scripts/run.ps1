param([ValidateRange(1024,65535)][int]$Port = 8507)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskVenvPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskVenvPython)) {
    throw 'Run .\scripts\setup.ps1 first.'
}
Push-Location -LiteralPath $taskRoot
try {
    & $taskVenvPython -m streamlit run app.py --server.address 127.0.0.1 --server.port $Port
    exit $LASTEXITCODE
} finally { Pop-Location }
