$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e '.[test]'
Write-Host 'Installed. Run: .\.venv\Scripts\python.exe -m sandgrid --help'
