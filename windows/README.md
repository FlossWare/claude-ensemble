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

## Installation

Use an elevated PowerShell prompt from a normal Python installation:

    cd <claude-ensemble>
    .\windows\install.ps1

The installer asks for the Windows account under which the services should run.
It creates a shared machine-level Messenger runtime directory at:

    %PROGRAMDATA%\ClaudeEnsemble\run

and configures the machine environment variable:

    CLAUDE_MESSENGER_SOCKET=%PROGRAMDATA%\ClaudeEnsemble\run\claude-messenger.sock

The same explicit endpoint is persisted in the Messenger SCM configuration.
The runtime directory ACL grants access to the selected service account,
SYSTEM, and local Administrators.

The service and interactive clients therefore use the same endpoint without
depending on the service account's profile or Path.home().

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
must provide AF_UNIX stream sockets for the Messenger service. The Windows CI
runs an actual bind/connect test, rather than only checking imports.

If Python cannot create an AF_UNIX stream socket, Messenger startup fails with
the platform's socket error instead of silently falling back to another
transport. The supported Windows deployment therefore requires a Windows/Python
combination with AF_UNIX stream-socket support.

## Security

Run the services under the same non-administrative account used by the
application where possible. Installation itself requires elevation because
Windows SCM service registration and the machine-level socket configuration
are administrative operations.

Do not put a service-account password in source control or a script.
The installer prompts for it.

## Direct execution without services

The native service layer is optional. The Python daemons can still be launched
directly from PowerShell, Command Prompt, Git Bash, or another supported shell.
systemd is not required for direct execution on Windows.
