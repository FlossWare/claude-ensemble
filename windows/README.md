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
It creates a machine-level Messenger runtime directory at:

    %PROGRAMDATA%\ClaudeEnsemble\run

The Windows Messenger endpoint is a deterministic named pipe:

    \\.\pipe\ClaudeEnsembleMessenger

The installer also creates a 32-byte authentication key at:

    %PROGRAMDATA%\ClaudeEnsemble\run\messenger.key

and configures the machine environment variables:

    CLAUDE_MESSENGER_SOCKET=\\.\pipe\ClaudeEnsembleMessenger
    CLAUDE_MESSENGER_AUTH_FILE=%PROGRAMDATA%\ClaudeEnsemble\run\messenger.key

The same endpoint and key location are persisted in the Messenger SCM
configuration. The key directory ACL grants access to the selected service
account, SYSTEM, and local Administrators.

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

Linux continues to use Unix-domain stream sockets. Windows uses a native named
pipe through Python's standard multiprocessing connection API. The endpoint is
fixed at \\.\pipe\ClaudeEnsembleMessenger and authenticated with an
installation-generated key.

The Windows CI runs an actual named-pipe bind/connect test, including the
authentication handshake. There is no TCP fallback and no dependency on
Windows Python AF_UNIX support.

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
