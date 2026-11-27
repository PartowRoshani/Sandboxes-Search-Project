$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
python -m unittest discover -s genetic_alg/tests -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m genetic_alg.benchmark_100 @args
exit $LASTEXITCODE
