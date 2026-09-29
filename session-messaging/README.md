# Claude Ensemble Session Messaging

claude-messenger is a small local topic-based pub/sub service for session-to-session commands. It is deliberately separate from the memory service: memory stores state, while this service delivers transient events.

## Protocol

Clients send newline-delimited JSON over a Unix domain socket.

Subscribe:

    {"op":"subscribe","topic":"credentials"}

Publish:

    {"op":"publish","topic":"credentials","data":{"action":"reload","path":"~/.FlossWare/secrets.env"}}

The service acknowledges requests. Published events are delivered to every current subscriber and are not persisted.

## Security and lifecycle

- On Linux, the socket defaults to $XDG_RUNTIME_DIR/claude-messenger/claude-messenger.sock.
- On Windows, the socket defaults to %PROGRAMDATA%\\ClaudeEnsemble\\run\\claude-messenger.sock.
- CLAUDE_MESSENGER_SOCKET overrides the endpoint on either platform.
- The Windows installer persists the endpoint as a machine environment variable and in SCM service configuration.
- The Windows installer ACLs the runtime directory for the selected service account, SYSTEM, and local Administrators.
- The service creates the socket with mode 0600 on POSIX systems.
- The systemd template places it under the user runtime directory with 0700 ownership.
- Windows deployments require usable AF_UNIX stream-socket support in the selected Python/Windows environment.
- No TCP listener or external dependency is used.
- Disconnected subscribers are removed.
- Clients can reconnect automatically after a service restart.

## Running

    cd session-messaging
    python3 -m unittest -v

Install the user service (the template uses @ENSEMBLE_ROOT@ as an install-time placeholder):

    mkdir -p ~/.config/systemd/user
    sed "s|@ENSEMBLE_ROOT@|$HOME/Development/FlossWare/claude-ensemble|g" claude-messenger.service.template > ~/.config/systemd/user/claude-messenger.service
    systemctl --user daemon-reload
    systemctl --user enable --now claude-messenger.service

Publish:

    python3 -c 'from messenger_client import MessengerClient; MessengerClient().publish("credentials", {"action": "reload"})'

Listen:

    python3 -c 'from messenger_client import MessengerClient; print(next(MessengerClient().subscribe("credentials")))'

The client module is intentionally dependency-free so it can be used by shell/session initialization without another service framework.
