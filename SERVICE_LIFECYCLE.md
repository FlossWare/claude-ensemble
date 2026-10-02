# Service Lifecycle Ownership

## Ownership model

Claude Ensemble services are **systemd user services**. Each daemon owns its
own process lifecycle. There is no top-level Ensemble daemon that starts,
stops, or supervises sibling services.

This is intentional:

- systemd starts and restarts each service.
- A service may depend on another service through systemd dependency
  declarations.
- A service must not spawn a sibling daemon as part of normal startup.
- Clients communicate with services through their documented sockets or
  interfaces.
- Installation enables individual systemd user units; it does not create a
  second process supervisor.

## Current baseline

The verified recovery baseline contains these independently managed services:

| Service | Lifecycle owner |
| --- | --- |
| Memory | systemd user manager |
| Thompson | systemd user manager |
| Learning | systemd user manager |
| Alert | systemd user manager |
| Messenger | systemd user manager |
| Graph | systemd user manager |

Learning declares a systemd dependency on Thompson because Learning can use
Thompson for outcome updates. That dependency does not transfer process
ownership to Learning.

The verified baseline does **not** contain a separate Ensemble application
server. The Graph capability is now represented by its own standalone HTTP
service and systemd unit; it remains independent of every sibling service.

## Startup and shutdown semantics

Starting a service means starting that service's own process:

```text
systemd --user
    |
    +-- claude-memory.service
    +-- claude-thompson.service
    +-- claude-learning.service
    +-- claude-alert.service
    +-- claude-messenger.service
    +-- claude-graph.service
```

Stopping or restarting one service must not implicitly create a second copy
of another service.

Systemd remains responsible for restart policy, process termination, and
service ordering. Service code is responsible for its own socket/resource
cleanup when it receives termination.

## Health and status

Operators can inspect the state of each systemd user service without a separate Ensemble supervisor:

```bash
systemctl --user is-active claude-memory.service
systemctl --user status claude-memory.service
```

Use the same commands with the relevant unit name for Thompson, Learning, Alert,
and Messenger. `is-active` provides a concise active/inactive result; `status`
provides the unit state, recent lifecycle messages, and the process identifier
when available.

For services that expose a socket or other documented interface, service health
also includes availability of that interface. A running systemd unit is not by
itself proof that the application protocol is responding correctly.

Learning has a declared dependency on Thompson. If Thompson is unavailable,
Learning does not take ownership of Thompson or start a replacement process.
Systemd remains responsible for the declared dependency and restart behavior;
Learning must report failures from unavailable Thompson functionality rather
than silently creating another Thompson instance.

## Verification

`test/test_service_lifecycle.py` verifies the baseline service templates
for the ownership contract:

- each service template is a simple systemd service with its own
  `ExecStart`;
- no service template invokes `systemctl` or an orchestration wrapper;
- the only declared inter-service dependency in the baseline is Learning's
  dependency on Thompson;
- all six baseline services are represented, including Graph;
- Graph is loopback-only and has no sibling-process supervision path.

Installer path correctness remains a separate concern for #102.
Termination propagation and platform-specific process-group behavior remain
separate concerns for #94 and #96.
