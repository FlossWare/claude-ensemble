# Install Claude Ensemble as native Windows services.
# Run from an elevated PowerShell prompt.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

python -m pip install -r "$repoRoot\requirements-windows.txt"

$username = Read-Host "Windows service account (DOMAIN\\user or .\\user)"
if ([string]::IsNullOrWhiteSpace($username)) {
    throw "A service account is required. Claude Ensemble services are user-scoped."
}

python "$repoRoot\windows\claude_ensemble_service.py" install --username $username
if ($LASTEXITCODE -ne 0) {
    throw "Claude Ensemble Windows service installation failed."
}

Write-Host "Claude Ensemble Windows services installed and started."
Write-Host "Use Get-Service ClaudeEnsemble* to inspect them."
