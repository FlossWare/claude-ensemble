"""Process-local capability for classifying nested CE REST calls.

This is a worker-capacity marker, not an application authentication mechanism.
The initial CE topology is a single process, so in-process logical services
share this value without introducing a distributed secret-management system.
"""
import secrets

INTERNAL_CALL_TOKEN = secrets.token_urlsafe(32)
