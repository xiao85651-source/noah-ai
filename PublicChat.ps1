$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$noahPython = $env:NOAH_PYTHON
if (!$noahPython) { $noahPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
if (!(Test-Path -LiteralPath $noahPython)) { throw 'Run Setup.cmd first.' }
if (!$env:NOAH_FOLLOW_RELEASES) { $env:NOAH_FOLLOW_RELEASES = '1' }
& $noahPython -m training.gateway
