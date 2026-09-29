# Remove Claude Ensemble native Windows services.
# Run from an elevated PowerShell prompt.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$programData = [Environment]::GetFolderPath("CommonApplicationData")
$authKeyPath = Join-Path $programData "ClaudeEnsemble\run\messenger.key"

python "$repoRoot\windows\claude_ensemble_service.py" remove
if ($LASTEXITCODE -ne 0) {
    throw "Claude Ensemble Windows service removal failed."
}

[Environment]::SetEnvironmentVariable("CLAUDE_MESSENGER_SOCKET", $null, "Machine")
[Environment]::SetEnvironmentVariable("CLAUDE_MESSENGER_AUTH_FILE", $null, "Machine")
Remove-Item -Force -ErrorAction SilentlyContinue $authKeyPath

Write-Host "Claude Ensemble Windows services removed."
