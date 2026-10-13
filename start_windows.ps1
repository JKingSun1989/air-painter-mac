$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:MPLCONFIGDIR = Join-Path $PSScriptRoot '.cache\matplotlib'
$env:XDG_CACHE_HOME = Join-Path $PSScriptRoot '.cache'
$env:PIP_CACHE_DIR = Join-Path $PSScriptRoot '.cache\pip'
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython) -or -not (Test-Path (Join-Path $PSScriptRoot '.venv\.painter-ready'))) {
    & (Join-Path $PSScriptRoot 'setup.ps1')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& $venvPython (Join-Path $PSScriptRoot 'run_app.py') @args
exit $LASTEXITCODE
