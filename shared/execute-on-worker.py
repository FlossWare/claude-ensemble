#!/usr/bin/env python3
"""
Python-based worker execution - WORKS ON ALL ARCHITECTURES

Uses temp file approach to avoid shell escaping hell.
"""

import subprocess
import json
import re
import time
import tempfile
from typing import Dict, Any

PROVIDER_CONFIG = {
    'groq': {'url': 'https://api.groq.com/openai/v1/chat/completions', 'key_env': 'GROQ_API_KEY'},
    'cerebras': {'url': 'https://api.cerebras.ai/v1/chat/completions', 'key_env': 'CEREBRAS_API_KEY'},
    'google': {'url': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', 'key_env': 'GOOGLE_API_KEY'},
    'cohere': {'url': 'https://api.cohere.com/v2/chat', 'key_env': 'COHERE_API_KEY'},
}

WORKER_SCRIPT = '''import json, os, sys, urllib.request, time
p = json.loads(sys.stdin.read())
k = os.environ.get(p['key_env'])
if not k: print(json.dumps({'error': f"Missing {p['key_env']}"})); sys.exit(1)

start = time.time()
if p['provider'] == 'google':
    url = p['url'].replace('{model}', p['model']) + '?key=' + k
    body = json.dumps({'contents': [{'parts': [{'text': p['task']}]}], 'generationConfig': {'maxOutputTokens': p['max_tokens']}}).encode()
    headers = {'Content-Type': 'application/json'}
else:
    url = p['url']
    body = json.dumps({'model': p['model'], 'messages': [{'role': 'user', 'content': p['task']}], 'max_tokens': p['max_tokens']}).encode()
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + k}

req = urllib.request.Request(url, data=body, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    duration_ms = int((time.time() - start) * 1000)
    if p['provider'] == 'google':
        output = d['candidates'][0]['content']['parts'][0]['text']
        input_tokens = d.get('usageMetadata', {}).get('promptTokenCount', 0)
        output_tokens = d.get('usageMetadata', {}).get('candidatesTokenCount', 0)
    else:
        output = d['choices'][0]['message']['content']
        input_tokens = d.get('usage', {}).get('prompt_tokens', 0)
        output_tokens = d.get('usage', {}).get('completion_tokens', 0)
    print(json.dumps({'output': output, 'input_tokens': input_tokens, 'output_tokens': output_tokens, 'duration_ms': duration_ms}))
except Exception as e:
    print(json.dumps({'error': str(e)})); sys.exit(1)
'''

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


def map_model_to_provider(model: str) -> str:
    model_lower = model.lower()
    if 'cerebras' in model_lower: return 'cerebras'
    if 'gemini' in model_lower: return 'google'
    if 'command' in model_lower: return 'cohere'
    return 'groq'

def execute_on_worker(worker: str, model: str, task: str, max_tokens: int = 4096, timeout_ms: int = 30000) -> Dict[str, Any]:
    _validate_worker_hostname(worker)
    start_time = time.time()
    provider = map_model_to_provider(model)
    config = PROVIDER_CONFIG[provider]

    params = {
        'task': task,
        'model': model,
        'max_tokens': max_tokens,
        'provider': provider,
        'url': config['url'],
        'key_env': config['key_env']
    }

    # Write script to temp file on worker
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(WORKER_SCRIPT)
        local_script = f.name

    try:
        # Copy script to worker
        subprocess.run(['scp', '-q', local_script, f'claude@{worker}:/tmp/worker.py'], check=True, timeout=5)

        # Execute on worker
        result = subprocess.run(
            ['ssh', f'claude@{worker}', 'bash', '-lc', 'python3 /tmp/worker.py; rm -f /tmp/worker.py'],
            input=json.dumps(params),
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000 + 10
        )

        if result.returncode != 0:
            raise Exception(f"Worker failed: {result.stderr[:200]}")

        worker_result = json.loads(result.stdout)
        if 'error' in worker_result:
            raise Exception(worker_result['error'])

        total_duration_ms = int((time.time() - start_time) * 1000)
        return {**worker_result, 'execution_host': worker, 'ssh_overhead_ms': total_duration_ms - worker_result['duration_ms']}

    finally:
        subprocess.run(['rm', '-f', local_script], check=False)

if __name__ == '__main__':
    result = execute_on_worker('server-01', 'llama-3.3-70b-versatile', 'Say OK', 5)
    print(json.dumps(result, indent=2))
