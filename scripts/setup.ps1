param([switch]$Dev)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRoot
try {
    $taskVenvPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $taskVenvPython)) {
        $taskPython = Get-Command python -ErrorAction SilentlyContinue
        $taskCondaPython = Join-Path $env:USERPROFILE 'anaconda3\python.exe'
        if ($taskPython) {
            & $taskPython.Source -m venv .venv
        } elseif (Test-Path -LiteralPath $taskCondaPython) {
            & $taskCondaPython -m venv .venv
        } elseif (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3 -m venv .venv
        } else {
            throw 'Install Python 3.11+ first. See docs/GETTING_STARTED.md.'
        }
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }
    $taskRequirements = if ($Dev) { 'requirements-dev.txt' } else { 'requirements.txt' }
    & $taskVenvPython -m pip install -r $taskRequirements
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    Write-Output 'Ready. Run: .\scripts\run.ps1'
} finally { Pop-Location }
