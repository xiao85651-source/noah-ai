$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$noahPython = $env:NOAH_PYTHON
if (!$noahPython) { $noahPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
if (!(Test-Path -LiteralPath $noahPython)) { throw 'Run Setup.cmd first.' }
& $noahPython -m unittest training.test_training training.test_http -v
if ($LASTEXITCODE -ne 0) { throw 'Noah checks failed.' }
Write-Host 'PASS: model, voluntary client protocol, HTTP ingress, training, export, generation and checkpoint recovery.'
