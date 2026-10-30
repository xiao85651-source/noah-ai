$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (!$python -or $python -like '*WindowsApps*') {
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) { $python = $bundled } else { throw 'Install Python 3.12 from python.org first.' }
}
& $python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Could not create a Python virtual environment.' }
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $venvPython -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed.' }
& $venvPython -m pip install 'numpy>=2.0,<3'
if ($LASTEXITCODE -ne 0) { throw 'NumPy installation failed.' }
& $venvPython -m unittest training.test_training -v
if ($LASTEXITCODE -ne 0) { throw 'Training checks did not pass.' }
Write-Host 'Noah is ready. Start.cmd opens the coordinator; Contribute.cmd starts a volunteer client.'
