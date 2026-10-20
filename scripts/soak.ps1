param([ValidateSet(1800,7200,14400,28800,57600)][int]$Seconds=1800)
$ErrorActionPreference="Stop"
Set-Location (Join-Path $PSScriptRoot "..")
& .\.venv\Scripts\uga.exe soak --seconds $Seconds --output ".uga/soak-$Seconds"
exit $LASTEXITCODE
