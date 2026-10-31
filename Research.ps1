$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$noahPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $noahPython)) { throw 'Run Setup.cmd first.' }
$env:NOAH_PROFILE = 'research-v1'
$env:NOAH_DATA = Join-Path $PSScriptRoot 'data-profiles\research-v1'
$env:PORT = '4323'
Write-Host 'Noah research profile: biopharma, technology and coding. Experimental; not a specialist assistant.'
Write-Host 'Open http://127.0.0.1:4323/#network . Training starts paused; the original seed data is separate.'
& $noahPython -m training.coordinator
