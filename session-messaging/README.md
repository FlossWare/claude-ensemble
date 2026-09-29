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

- The socket defaults to $XDG_RUNTIME_DIR/claude-messenger.sock.
- The service creates the socket with mode 0600.
- The systemd template places it under the user runtime directory with 0700 ownership.
- No TCP listener or external dependency is used.
- Disconnected subscribers are removed.
- Clients can reconnect automatically after a service restart.

## Running

    cd session-messaging
    python3 -m unittest -v

Install the user service:

    mkdir -p ~/.config/systemd/user
    cp claude-messenger.service.template ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now claude-messenger.service

Publish:

    python3 -c 'from messenger_client import MessengerClient; MessengerClient().publish("credentials", {"action": "reload"})'

Listen:

    python3 -c 'from messenger_client import MessengerClient; print(next(MessengerClient().subscribe("credentials")))'

The client module is intentionally dependency-free so it can be used by shell/session initialization without another service framework.
