$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = $env:NOAH_PYTHON
if (!$python) { $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
if (!(Test-Path -LiteralPath $python)) { throw 'Run Setup.cmd first, or set NOAH_PYTHON to a Python environment with requirements.txt installed.' }
Write-Host 'Noah - independently initialized Transformer'
Write-Host 'Open http://127.0.0.1:4317 in your browser. Ctrl+C stops the coordinator.'
& $python -m training.coordinator
