# Remove Claude Ensemble native Windows services.
# Run from an elevated PowerShell prompt.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

python "$repoRoot\windows\claude_ensemble_service.py" remove
if ($LASTEXITCODE -ne 0) {
    throw "Claude Ensemble Windows service removal failed."
}

Write-Host "Claude Ensemble Windows services removed."
