"""Gunicorn configuration — LLM proxy on port 8000."""

bind = "0.0.0.0:8000"
workers = 4
threads = 4
timeout = 180
keepalive = 5
max_requests = 500
max_requests_jitter = 50
accesslog = "/exports/claude-orchestrator/llm-proxy/gunicorn-access.log"
errorlog = "/exports/claude-orchestrator/llm-proxy/gunicorn-error.log"
loglevel = "info"
