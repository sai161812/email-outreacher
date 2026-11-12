param([ValidateSet('start','stop','status')][string]$Action='start', [ValidateRange(1,65535)][int]$Port=5000)
$outreachPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $outreachPython)) {
    Write-Error 'Missing .venv. Install Python 3.12 and follow the locked installation steps in README.md.'
    exit 1
}
& $outreachPython -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3,12) else 1)'
if ($LASTEXITCODE -ne 0) {
    Write-Error 'Python 3.12 is unavailable. Preserve the old .venv, recreate it and install requirements.lock as documented in README.md.'
    exit 1
}
& $outreachPython (Join-Path $PSScriptRoot 'run.py') $Action --port $Port
exit $LASTEXITCODE
