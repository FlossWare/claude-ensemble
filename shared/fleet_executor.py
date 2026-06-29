#!/usr/bin/env python3
"""
Fleet Executor - Distributed task execution via Python

Works on ALL architectures (x86_64, arm64, armhf) and ALL Python 3.8+
No dependencies - stdlib only

Usage:
    from fleet_executor import execute_on_worker

    result = execute_on_worker(
        worker='server-01',
        model='gpt-4o-mini',
        task='Analyze this code',
        max_tokens=500
    )
"""

import subprocess
import json
import time
import os
import re
from typing import Dict, Any, Optional

# Valid hostname: alphanumeric, dots, hyphens; no leading/trailing dot/hyphen;
# each label 1-63 chars, total max 253 chars (RFC 952 / RFC 1123).
_VALID_HOSTNAME_RE = re.compile(
    r'^(?!-)[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?'
    r'(?:\.(?!-)[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)*$'
)


def _validate_worker_hostname(worker: str) -> None:
    """Validate worker hostname to prevent SSH command injection.

    Raises ValueError if the hostname contains characters outside
    the allowed set (alphanumeric, dots, hyphens) or violates
    RFC 952/1123 structure.
    """
    if not worker or len(worker) > 253:
        raise ValueError(f"Invalid worker hostname (empty or too long): {worker!r}")
    if not _VALID_HOSTNAME_RE.match(worker):
        raise ValueError(
            f"Invalid worker hostname: {worker!r}. "
            "Must contain only alphanumeric characters, dots, and hyphens."
        )

# Provider configuration
PROVIDERS = {
    'openai': {
        'url': 'https://api.openai.com/v1/chat/completions',
        'key_env': 'OPENAI_API_KEY',
        'models': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo']
    },
    'groq': {
        'url': 'https://api.groq.com/openai/v1/chat/completions',
        'key_env': 'GROQ_API_KEY',
        'models': ['llama-3.3-70b-versatile', 'llama-3.1-70b-versatile', 'mixtral-8x7b-32768']
    },
    'cerebras': {
        'url': 'https://api.cerebras.ai/v1/chat/completions',
        'key_env': 'CEREBRAS_API_KEY',
        'models': ['llama-3.3-70b', 'zai-glm-4.7']
    },
    'google': {
        'url': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        'key_env': 'GOOGLE_API_KEY',
        'models': ['gemini-2.0-flash-exp', 'gemini-1.5-flash', 'gemini-1.5-pro']
    },
    'anthropic': {
        'url': 'https://api.anthropic.com/v1/messages',
        'key_env': 'ANTHROPIC_API_KEY',
        'models': ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022']
    }
}

def map_model_to_provider(model: str) -> str:
    """Map model name to provider"""
    model_lower = model.lower()

    # Check each provider's models
    for provider, config in PROVIDERS.items():
        for provider_model in config['models']:
            if provider_model.lower() in model_lower:
                return provider

    # Fallback patterns
    if 'gpt' in model_lower or 'o1' in model_lower:
        return 'openai'
    if 'claude' in model_lower or 'sonnet' in model_lower or 'opus' in model_lower or 'haiku' in model_lower:
        return 'anthropic'
    if 'gemini' in model_lower:
        return 'google'
    if 'llama' in model_lower or 'mixtral' in model_lower:
        return 'groq'
    if 'cerebras' in model_lower:
        return 'cerebras'

    # Default
    return 'openai'

def execute_on_worker(
    worker: str,
    model: str,
    task: str,
    max_tokens: int = 4096,
    timeout_ms: int = 30000,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute API call on remote worker via Python

    Args:
        worker: Worker hostname (e.g., 'server-01', 'aio-01' for local)
        model: Model name (e.g., 'gpt-4o-mini')
        task: Task/prompt to execute
        max_tokens: Maximum tokens in response
        timeout_ms: Timeout in milliseconds
        api_key: Optional API key (will load from env if not provided)

    Returns:
        Dict with output, duration_ms, tokens, execution_host
    """
    start_time = time.time()

    # Map model to provider
    provider = map_model_to_provider(model)
    provider_config = PROVIDERS.get(provider)

    if not provider_config:
        raise ValueError(f"Unknown provider for model: {model}")

    # Get API key if not provided
    if not api_key:
        key_env = provider_config['key_env']
        api_key = os.environ.get(key_env)

        if not api_key:
            # Try loading from bashrc
            try:
                result = subprocess.run(
                    ['bash', '-c', 'source ~/.bashrc && printenv "$1"', '_', key_env],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                api_key = result.stdout.strip()
            except Exception:
                pass

        if not api_key:
            raise ValueError(f"Missing API key: {key_env}")

    # Build parameters
    params = {
        'task': task,
        'model': model,
        'max_tokens': max_tokens,
        'url': provider_config['url'],
        'key_env': provider_config['key_env'],
        'api_key': api_key,
        'provider': provider
    }

    # Execute on worker
    # Use fixed path that works on all workers (under claude user home)
    worker_script = '/home/claude/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/python-worker.py'

    # For local execution (aio-01), use current user's home
    if worker == 'aio-01' or worker == 'localhost':
        worker_script = os.path.expanduser('~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/python-worker.py')

    # Validate worker hostname to prevent SSH command injection
    _validate_worker_hostname(worker)

    if worker == 'aio-01' or worker == 'localhost':
        # Local execution
        result = subprocess.run(
            ['python3', worker_script],
            input=json.dumps(params),
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000 + 10
        )
    else:
        # Remote execution
        result = subprocess.run(
            ['ssh', f'claude@{worker}', 'python3', worker_script],
            input=json.dumps(params),
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000 + 10
        )

    # Parse result (even if returncode != 0, might have JSON error)
    try:
        worker_result = json.loads(result.stdout)
    except json.JSONDecodeError:
        # If can't parse JSON, show actual error
        raise Exception(f"Worker {worker} failed: stdout={result.stdout[:200]}, stderr={result.stderr[:200]}, code={result.returncode}")

    # Don't raise - return error dict for graceful handling (arm64 compatibility)
    # Caller can check 'error' field

    # Calculate total duration
    total_duration_ms = int((time.time() - start_time) * 1000)

    return {
        **worker_result,
        'execution_host': worker,
        'actually_executed_on_worker': True,
        'ssh_overhead_ms': total_duration_ms - worker_result.get('duration_ms', 0),
        'provider': provider
    }


def execute_on_fleet_parallel(
    workers: list,
    model: str,
    tasks: list,
    max_tokens: int = 4096,
    timeout_ms: int = 30000
) -> list:
    """
    Execute tasks in parallel across fleet

    Args:
        workers: List of worker hostnames
        model: Model to use
        tasks: List of tasks (one per worker, or repeated if fewer tasks)
        max_tokens: Max tokens per task
        timeout_ms: Timeout per task

    Returns:
        List of results (one per worker)
    """
    import concurrent.futures

    def execute_task(i):
        worker = workers[i]
        task = tasks[i] if i < len(tasks) else tasks[0]
        try:
            return execute_on_worker(worker, model, task, max_tokens, timeout_ms)
        except Exception as e:
            return {'worker': worker, 'error': str(e)[:200]}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(workers)) as executor:
        results = list(executor.map(execute_task, range(len(workers))))

    return results


if __name__ == '__main__':
    # Test single worker
    print("Testing fleet executor...")

    try:
        result = execute_on_worker(
            worker='aio-01',
            model='gpt-4o-mini',
            task='Say OK',
            max_tokens=5
        )
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
