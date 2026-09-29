# Native Windows Services

Claude Ensemble supports native Windows Service Control Manager (SCM) integration.

The application daemons remain unchanged. The Windows layer hosts the existing
Python services and maps the important systemd semantics to SCM:

| Linux/systemd | Windows |
|---|---|
| systemd --user | Windows SCM |
| Restart=always | SCM failure actions + wrapper restart |
| After= / Wants= | SCM service dependencies |
| WantedBy=default.target | Automatic service startup |
| journald | Windows Event Log + per-service logs |
| systemctl start/stop/status | Start-Service / Stop-Service / Get-Service |

## Installation

Use an elevated PowerShell prompt from a normal Python installation:

    cd <claude-ensemble>
    .\windows\install.ps1

The installer asks for the Windows account under which the services should run.
Use the same account that runs Claude Ensemble interactively. This is important
because the services use the account's .claude data and Unix-domain sockets.

pywin32 is used for the actual SCM integration. It provides a native Win32
service host rather than emulating Windows services with a shell process.

## Service names

- ClaudeEnsembleMemory
- ClaudeEnsembleThompson
- ClaudeEnsembleLearning
- ClaudeEnsembleAlert
- ClaudeEnsembleMessenger

Learning depends on Thompson. Alert depends on Learning. Memory and Messenger
are independent.

## Management

    Get-Service ClaudeEnsemble*

    Start-Service ClaudeEnsembleMemory
    Stop-Service ClaudeEnsembleMemory
    Restart-Service ClaudeEnsembleMemory

Or use:

    python windows\claude_ensemble_service.py start
    python windows\claude_ensemble_service.py stop

Remove everything with:

    .\windows\uninstall.ps1

## Logs

Service lifecycle events are written to the Windows Event Log. Child-process
stdout/stderr is additionally captured under:

    %PROGRAMDATA%\ClaudeEnsemble\logs

The application services continue to write their normal Claude Ensemble logs.

## Windows IPC

Claude Ensemble uses Unix-domain stream sockets for local service IPC. Windows
supports AF_UNIX stream sockets on supported modern Windows versions, so the
existing IPC protocol can remain unchanged. Datagram and ancillary-data
features are not used by Claude Ensemble.

## Security

Run the services under the same non-administrative account used by the
application where possible. Installation itself requires elevation because
Windows SCM service registration is machine-level.

Do not put a service-account password in source control or a script.
The installer prompts for it.

## Direct execution without services

The native service layer is optional. The Python daemons can still be launched
directly from PowerShell, Command Prompt, Git Bash, or another supported shell.
systemd is not required for direct execution on Windows.
