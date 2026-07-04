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

# Provider configuration - ALL REQUESTS GO THROUGH LOCAL PROXY
# aio-01:8000 handles routing to actual providers
PROXY_URL = os.getenv('API_PROXY_URL', 'http://aio-01:8002/v1/chat/completions')

PROVIDERS = {
    'openai': {
        'url': PROXY_URL,
        'key_env': 'OPENAI_API_KEY',
        'models': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo']
    },
    'groq': {
        'url': PROXY_URL,
        'key_env': 'GROQ_API_KEY',
        'models': ['llama-3.3-70b-versatile', 'llama-3.1-70b-versatile', 'mixtral-8x7b-32768']
    },
    'cerebras': {
        'url': PROXY_URL,
        'key_env': 'CEREBRAS_API_KEY',
        'models': ['llama-3.3-70b', 'zai-glm-4.7']
    },
    'google': {
        'url': PROXY_URL,
        'key_env': 'GOOGLE_API_KEY',
        'models': ['gemini-3.5-flash', 'gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.5-flash-lite']
    },
    'anthropic': {
        'url': PROXY_URL,
        'key_env': 'ANTHROPIC_API_KEY',
        'models': ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022']
    },
    'cohere': {
        'url': PROXY_URL,
        'key_env': 'COHERE_API_KEY',
        'models': ['command-a-plus-05-2026', 'command-a-03-2025', 'command-r7b-12-2024', 'command-r-08-2024', 'command-r-plus-08-2024']
    },
    'deepseek': {
        'url': PROXY_URL,
        'key_env': 'DEEPSEEK_API_KEY',
        'models': ['deepseek-coder', 'deepseek-chat']
    },
    'openrouter': {
        'url': PROXY_URL,
        'key_env': 'OPENROUTER_API_KEY',
        'models': [
            # All 25 free models from OpenRouter (as of June 2026)
            'nvidia/nemotron-3-ultra-550b-a55b:free',  # 550B ultra large
            'nousresearch/hermes-3-llama-3.1-405b:free',  # 405B huge
            'nvidia/nemotron-3-super-120b-a12b:free',  # 120B working!
            'openai/gpt-oss-120b:free',  # 120B
            'qwen/qwen3-next-80b-a3b-instruct:free',  # 80B
            'meta-llama/llama-3.3-70b-instruct:free',  # 70B
            'google/gemma-4-31b-it:free',  # 31B
            'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free',  # 30B reasoning
            'nvidia/nemotron-3-nano-30b-a3b:free',  # 30B
            'google/gemma-4-26b-a4b-it:free',  # 26B
            'cognitivecomputations/dolphin-mistral-24b-venice-edition:free',  # 24B
            'openai/gpt-oss-20b:free',  # 20B
            'nvidia/nemotron-nano-12b-v2-vl:free',  # 12B vision
            'nvidia/nemotron-nano-9b-v2:free',  # 9B
            'qwen/qwen3-coder:free',  # Coder specialist
            'meta-llama/llama-3.2-3b-instruct:free',  # 3B fast
            'poolside/laguna-m.1:free',  # Poolside M
            'poolside/laguna-xs.2:free',  # Poolside XS
            'liquid/lfm-2.5-1.2b-instruct:free',  # 1.2B instruct (working!)
            'liquid/lfm-2.5-1.2b-thinking:free',  # 1.2B thinking
            'cohere/north-mini-code:free',  # Cohere code
            'nvidia/nemotron-3.5-content-safety:free',  # Safety filter
            'google/lyria-3-pro-preview',  # Audio model
            'google/lyria-3-clip-preview',  # Audio clip
            'openrouter/free'  # Auto-select from available
        ]
    },
    'vertex': {
        'url': 'vertex',  # Special marker - uses Google Cloud SDK
        'key_env': 'ANTHROPIC_VERTEX_PROJECT_ID',
        'models': ['claude-3-5-sonnet-v2@20241022', 'claude-3-5-haiku@20241022', 'claude-3-opus@20240229']
    },
    'ollama': {
        'url': 'http://localhost:11434/api/generate',
        'key_env': 'NONE',  # No API key needed for local Ollama
        'models': ['phi3.5', 'deepseek-r1:32b', 'command-r:35b', 'command-r-plus:104b', 'qwen2.5:7b', 'gemma2:2b', 'gemma3:4b']
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
        # Check if Vertex AI is available (environment variable set)
        if os.environ.get('ANTHROPIC_VERTEX_PROJECT_ID'):
            return 'vertex'
        return 'anthropic'
    if 'gemini' in model_lower:
        return 'google'
    if 'llama' in model_lower or 'mixtral' in model_lower:
        return 'groq'
    if 'cerebras' in model_lower:
        return 'cerebras'
    if 'command' in model_lower:
        return 'cohere'
    if 'deepseek' in model_lower:
        return 'deepseek'
    if 'nex-n2' in model_lower or 'nex-agi' in model_lower:
        return 'openrouter'
    # OpenRouter models have / in them (provider/model format)
    if '/' in model and (':free' in model_lower or 'openrouter/free' in model_lower or
        'nvidia/' in model_lower or 'liquid/' in model_lower or 'poolside/' in model_lower or
        'qwen/' in model_lower or 'nousresearch/' in model_lower or 'cognitivecomputations/' in model_lower):
        return 'openrouter'

    # Default
    return 'openai'

def execute_on_worker(
    worker: str,
    model: str,
    task: str,
    max_tokens: int = 4096,
    timeout_ms: int = 30000,
    api_key: Optional[str] = None,
    max_retries: int = 0,
    backoff_seconds: float = 1.0
) -> Dict[str, Any]:
    """
    Execute API call on remote worker via Python with retry and backoff

    Args:
        worker: Worker hostname (e.g., 'server-01', 'aio-01' for local)
        model: Model name (e.g., 'gpt-4o-mini')
        task: Task/prompt to execute
        max_tokens: Maximum tokens in response
        timeout_ms: Timeout in milliseconds
        api_key: Optional API key (will load from env if not provided)
        max_retries: Number of retries on transient failures (default: 0)
        backoff_seconds: Initial backoff delay, doubles each retry (default: 1.0)

    Returns:
        Dict with output, duration_ms, tokens, execution_host
    """
    start_time = time.time()

    # Transient error codes that warrant retry
    RETRY_CODES = {429, 500, 502, 503, 504}  # Rate limit, server errors

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = _execute_worker_attempt(
                worker, model, task, max_tokens, timeout_ms, api_key
            )

            # Check if result indicates transient failure
            if 'error' in result:
                error_msg = result['error']
                # Extract HTTP code if present
                http_code = None
                if 'HTTP' in error_msg:
                    try:
                        http_code = int(error_msg.split('HTTP')[1].split(':')[0].strip())
                    except:
                        pass

                # Retry on transient errors
                if http_code in RETRY_CODES and attempt < max_retries:
                    delay = backoff_seconds * (2 ** attempt)
                    last_error = f"Attempt {attempt+1}/{max_retries+1} failed: {error_msg}. Retrying in {delay}s..."
                    time.sleep(delay)
                    continue

            # Success or non-retryable error
            if last_error:
                result['retry_history'] = last_error
            return result

        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                delay = backoff_seconds * (2 ** attempt)
                time.sleep(delay)
                continue

            return {
                'error': f"Worker {worker} failed after {max_retries+1} attempts: {last_error}",
                'execution_host': worker,
                'duration_ms': int((time.time() - start_time) * 1000)
            }

    return {
        'error': f"Worker {worker} failed after {max_retries+1} attempts: {last_error}",
        'execution_host': worker,
        'duration_ms': int((time.time() - start_time) * 1000)
    }


def _execute_worker_attempt(
    worker: str,
    model: str,
    task: str,
    max_tokens: int,
    timeout_ms: int,
    api_key: Optional[str]
) -> Dict[str, Any]:
    """
    Single execution attempt on worker (internal helper)
    """
    start_time = time.time()

    # Map model to provider
    provider = map_model_to_provider(model)
    provider_config = PROVIDERS.get(provider)

    if not provider_config:
        raise ValueError(f"Unknown provider for model: {model}")

    # Get API key if not provided (skip for Ollama - local, no key needed)
    if not api_key and provider != 'ollama':
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
            # Proxy handles API keys - use dummy
            api_key = "dummy"

    # Build parameters
    # Format URL with model name if needed (for Google)
    url = provider_config['url']
    if '{model}' in url:
        url = url.replace('{model}', model)

    # Choose worker script based on provider
    if provider == 'vertex':
        worker_script = '/opt/claude-orchestrator/shared/vertex-worker-sdk.py'
        params = {
            'task': task,
            'model': model,
            'max_tokens': max_tokens,
            'project_id': os.environ.get('ANTHROPIC_VERTEX_PROJECT_ID', 'cloudability-it-gemini'),
            'location': os.environ.get('GOOGLE_CLOUD_LOCATION', 'us-east5')
        }
    elif provider == 'ollama':
        worker_script = '/opt/claude-orchestrator/shared/ollama-worker.py'
        params = {
            'task': task,
            'model': model,
            'max_tokens': max_tokens
        }
    else:
        worker_script = '/opt/claude-orchestrator/shared/python-worker.py'
        params = {
            'task': task,
            'model': model,
            'max_tokens': max_tokens,
            'url': url,
            'key_env': provider_config['key_env'],
            'api_key': api_key,
            'provider': provider
        }

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
        # Remote execution - use bash to call wrapper script for proper stdin piping
        wrapper_script = '/opt/claude-orchestrator/shared/ssh-worker-wrapper.sh'
        result = subprocess.run(
            ['bash', wrapper_script, worker, worker_script, json.dumps(params)],
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000 + 10
        )

    # Parse result (even if returncode != 0, might have JSON error)
    try:
        worker_result = json.loads(result.stdout)
    except json.JSONDecodeError:
        # If can't parse JSON, show actual error
        raise Exception(f"Worker {worker} failed: stdout={result.stdout[:2000]}, stderr={result.stderr[:2000]}, code={result.returncode}")

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
    timeout_ms: int = 30000,
    max_retries: int = 2,
    backoff_seconds: float = 1.0
) -> list:
    """
    Execute tasks in parallel across fleet with retry and backoff

    Args:
        workers: List of worker hostnames
        model: Model to use
        tasks: List of tasks (one per worker, or repeated if fewer tasks)
        max_tokens: Max tokens per task
        timeout_ms: Timeout per task
        max_retries: Number of retries on transient failures (default: 2)
        backoff_seconds: Initial backoff delay, doubles each retry (default: 1.0)

    Returns:
        List of results (one per worker)
    """
    import concurrent.futures

    def execute_task(i):
        worker = workers[i]
        task = tasks[i] if i < len(tasks) else tasks[0]
        try:
            return execute_on_worker(
                worker, model, task, max_tokens, timeout_ms,
                max_retries=max_retries, backoff_seconds=backoff_seconds
            )
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
