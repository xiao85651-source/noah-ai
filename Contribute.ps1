param([ValidateSet('cpu','cuda')][string]$Device = 'cpu')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = $env:NOAH_PYTHON
if (!$python) { $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
if (!(Test-Path -LiteralPath $python)) { throw 'Run Setup.cmd first, or set NOAH_PYTHON to your prepared Python environment.' }
& $python -m training.worker --device $Device
