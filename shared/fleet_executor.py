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
import urllib.request
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
PROXY_URL = os.getenv('API_PROXY_URL', 'http://aio-01:8000/v1/chat/completions')

FALLBACK_PROVIDERS = {
    'openai': {
        'url': PROXY_URL,
        'key_env': 'PERSONAL_OPENAI_API_KEY',
        'models': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo']
    },
    'groq': {
        'url': PROXY_URL,
        'key_env': 'PERSONAL_GROQ_API_KEY',
        'models': ['llama-3.3-70b-versatile', 'llama-3.1-70b-versatile', 'mixtral-8x7b-32768']
    },
    'cerebras': {
        'url': PROXY_URL,
        'key_env': 'PERSONAL_CEREBRAS_API_KEY',
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
        'key_env': 'PERSONAL_COHERE_API_KEY',
        'models': ['command-a-plus-05-2026', 'command-a-03-2025', 'command-r7b-12-2024', 'command-r-08-2024', 'command-r-plus-08-2024']
    },
    'deepseek': {
        'url': PROXY_URL,
        'key_env': 'PERSONAL_DEEPSEEK_API_KEY',
        'models': ['deepseek-coder', 'deepseek-chat']
    },
    'openrouter': {
        'url': PROXY_URL,
        'key_env': 'PERSONAL_OPENROUTER_API_KEY',
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
            'poolside/laguna-s-2.1:free',  # Poolside S 2.1
            'poolside/laguna-xs.2:free',  # Poolside XS
            'inclusionai/ling-3.0-flash:free',  # Ling 3.0 Flash
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
    'pollinations': {
        'url': 'https://text.pollinations.ai/openai/chat/completions',
        'key_env': 'NONE',
        'models': ['openai-fast']
    },
    'zerolimitai': {
        'url': 'https://www.zerolimitai.com/api/v1/chat/completions',
        'key_env': 'PERSONAL_ZEROLIMITAI_API_KEY',
        'models': ['auto']
    },
    'edenai': {
        'url': 'https://api.edenai.run/v2/text/chat',
        'key_env': 'PERSONAL_EDENAI_API_KEY',
        'models': [
            'openai/gpt-4o', 'openai/gpt-4o-mini',
            'google/gemini-2.5-flash', 'google/gemini-2.0-flash',
            'anthropic/claude-sonnet',
            'mistralai/mistral-small', 'mistralai/mistral-large',
            'meta/llama-3.3-70b', 'meta/llama-4-scout',
            'deepseek/deepseek-v3', 'deepseek/deepseek-r1',
            'cohere/command-r-plus', 'xai/grok', 'perplexity/sonar',
            'groq/llama-3.3-70b', 'cerebras/llama-3.3-70b',
            'qwen/qwen3-235b', 'cloudflare/llama-3.3-70b'
        ]
    },
    'nvidia-nim': {
        'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
        'key_env': 'NVIDIA_API_KEY',
        'models': [
            'nvidia/nemotron-3-ultra-550b-a55b',
            'nvidia/nemotron-3-super-120b-a12b',
            'nvidia/llama-3.1-nemotron-ultra-253b-v1',
            'nvidia/llama-3.3-nemotron-super-49b-v1.5',
            'nvidia/llama-3.1-nemotron-70b-instruct',
            'nvidia/llama-3.1-nemotron-51b-instruct',
            'nvidia/nemotron-3-nano-30b-a3b',
            'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning',
            'nvidia/nvidia-nemotron-nano-9b-v2',
            'nvidia/cosmos-reason2-8b',
            'mistralai/mistral-large-2-instruct',
            'mistralai/mistral-medium-3.5-128b',
            'mistralai/mistral-nemotron',
            'mistralai/codestral-22b-instruct-v0.1',
            'meta/llama-3.3-70b-instruct',
            'meta/llama-3.1-70b-instruct',
            'meta/llama-3.1-8b-instruct',
            'meta/llama-3.2-90b-vision-instruct',
            'google/gemma-4-31b-it',
            'google/gemma-3-12b-it',
            'deepseek-ai/deepseek-v4-flash',
            'deepseek-ai/deepseek-v4-pro',
            'moonshotai/kimi-k2.6',
            'openai/gpt-oss-120b',
            'openai/gpt-oss-20b',
            'ai21labs/jamba-1.5-large-instruct',
            'ibm/granite-3.0-8b-instruct',
            'writer/palmyra-creative-122b',
            'thinkingmachines/inkling',
            'stepfun-ai/step-3.7-flash',
            'minimaxai/minimax-m3',
            'poolside/laguna-xs-2.1',
        ]
    },
    'ollama': {
        'url': 'http://localhost:11434/api/generate',
        'key_env': 'NONE',
        'models': ['phi3.5', 'deepseek-r1:32b', 'command-r:35b', 'command-r-plus:104b', 'qwen2.5:7b', 'gemma2:2b', 'gemma3:4b']
    }
}

_providers_cache = None
_providers_cache_time = 0
_CACHE_TTL = 300  # 5 minutes

API_URL = os.getenv('ORCHESTRATOR_URL', 'http://aio-01:5000')

KEY_ENV_MAP = {
    'openai': 'PERSONAL_OPENAI_API_KEY',
    'groq': 'PERSONAL_GROQ_API_KEY',
    'cerebras': 'PERSONAL_CEREBRAS_API_KEY',
    'google': 'GOOGLE_API_KEY',
    'google-gemini': 'GOOGLE_API_KEY',
    'anthropic': 'ANTHROPIC_API_KEY',
    'cohere': 'PERSONAL_COHERE_API_KEY',
    'deepseek': 'PERSONAL_DEEPSEEK_API_KEY',
    'openrouter': 'PERSONAL_OPENROUTER_API_KEY',
    'vertex': 'ANTHROPIC_VERTEX_PROJECT_ID',
    'mistral': 'PERSONAL_MISTRAL_API_KEY',
    'cloudflare': 'PERSONAL_CLOUDFLARE_API_KEY',
    'jina': 'PERSONAL_JINA_API_KEY',
    'zerolimitai': 'PERSONAL_ZEROLIMITAI_API_KEY',
    'edenai': 'PERSONAL_EDENAI_API_KEY',
    'github-models': 'GH_TOKEN',
    'nvidia-nim': 'NVIDIA_API_KEY',
    'sambanova': 'PERSONAL_SAMBANOVA_API_KEY',
    'thinking-machines': 'PERSONAL_THINKMACHINES_API_KEY',
    'pollinations': 'NONE',
    'deepinfra': 'NONE',
    'huggingface': 'NONE',
    'ollama': 'NONE',
}

def get_providers() -> Dict[str, Any]:
    """Fetch provider roster from REST API, fall back to hardcoded."""
    global _providers_cache, _providers_cache_time

    if _providers_cache and (time.time() - _providers_cache_time) < _CACHE_TTL:
        return _providers_cache

    try:
        req = urllib.request.Request(f'{API_URL}/models/providers', method='GET')
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        providers = {}
        for p in data.get('providers', []):
            name = p.get('provider', '')
            if not name:
                continue
            providers[name] = {
                'url': p.get('api_endpoint') or PROXY_URL,
                'key_env': KEY_ENV_MAP.get(name, 'NONE'),
                'models': p.get('models', [])
            }

        if providers:
            _providers_cache = providers
            _providers_cache_time = time.time()
            return providers
    except Exception:
        pass

    _providers_cache = FALLBACK_PROVIDERS
    _providers_cache_time = time.time()
    return FALLBACK_PROVIDERS


def map_model_to_provider(model: str) -> str:
    """Map model name to provider"""
    model_lower = model.lower()

    providers = get_providers()
    # Check each provider's models
    for provider, config in providers.items():
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
    provider_config = get_providers().get(provider)

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
