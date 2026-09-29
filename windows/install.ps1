# Install Claude Ensemble as native Windows services.
# Run from an elevated PowerShell prompt.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$programData = [Environment]::GetFolderPath("CommonApplicationData")
$runDir = Join-Path $programData "ClaudeEnsemble\run"
$socketPath = Join-Path $runDir "claude-messenger.sock"

python -m pip install -r "$repoRoot\requirements-windows.txt"

$username = Read-Host "Windows service account (DOMAIN\\user or .\\user)"
if ([string]::IsNullOrWhiteSpace($username)) {
    throw "A service account is required. Claude Ensemble services are user-scoped."
}

New-Item -ItemType Directory -Force -Path $runDir | Out-Null
icacls $runDir /inheritance:r | Out-Null
icacls $runDir /grant:r ($username + ":(OI)(CI)(F)") "SYSTEM:(OI)(CI)(F)" "Administrators:(OI)(CI)(F)" | Out-Null

[Environment]::SetEnvironmentVariable("CLAUDE_MESSENGER_SOCKET", $socketPath, "Machine")

python "$repoRoot\windows\claude_ensemble_service.py" install --username $username
if ($LASTEXITCODE -ne 0) {
    throw "Claude Ensemble Windows service installation failed."
}

Write-Host "Claude Ensemble Windows services installed and started."
Write-Host "Messenger socket: $socketPath"
Write-Host "Use Get-Service ClaudeEnsemble* to inspect them."
