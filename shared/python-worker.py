#!/usr/bin/env python3
"""
Python worker - executes on remote machine
Reads JSON params from stdin, makes API call, outputs JSON result
"""
import json
import os
import sys
import urllib.request
import time

def main():
    # Read params from stdin
    try:
        params = json.loads(input())
    except Exception as e:
        print(json.dumps({'error': f'Failed to parse params: {e}'}))
        sys.exit(1)

    task = params.get('task')
    model = params.get('model')
    max_tokens = params.get('max_tokens', 100)
    url = params.get('url')
    key_env = params.get('key_env')
    api_key = params.get('api_key')  # Can be passed directly
    provider = params.get('provider', 'openai')  # Default to OpenAI format

    # Get API key from environment if not provided
    if not api_key:
        api_key = os.environ.get(key_env)

    if not api_key:
        # Try to load from bashrc
        try:
            import re
            import subprocess
            # Validate key_env is a safe env var name (alphanumeric + underscore only)
            if not key_env or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key_env):
                raise ValueError(f'Invalid env var name: {key_env}')
            result = subprocess.run(
                ['bash', '-c', 'source ~/.bashrc && printenv "$1"', '_', key_env],
                capture_output=True,
                text=True,
                timeout=2
            )
            api_key = result.stdout.strip()
        except:
            pass

    if not api_key:
        print(json.dumps({'error': f'Missing {key_env} (not in env, not in bashrc)'}))
        sys.exit(1)

    # Build request based on provider
    start = time.time()

    if provider == 'google':
        # Google Gemini uses Interactions API format
        body = json.dumps({
            'model': model,
            'input': task
        }).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': api_key
        }
        req = urllib.request.Request(url, data=body, headers=headers)
    elif provider == 'cohere':
        # Cohere uses different format
        body = json.dumps({
            'message': task,
            'model': model,
            'max_tokens': max_tokens
        }).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        req = urllib.request.Request(url, data=body, headers=headers)
    else:
        # OpenAI-compatible format (default)
        body = json.dumps({
            'model': model,
            'messages': [{'role': 'user', 'content': task}],
            'max_tokens': max_tokens
        }).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        req = urllib.request.Request(url, data=body, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))

        duration_ms = int((time.time() - start) * 1000)

        # Parse response based on provider
        if provider == 'google':
            # Google Interactions API response format
            output = data.get('output', '')
            input_tokens = data.get('usage', {}).get('input_tokens', 0)
            output_tokens = data.get('usage', {}).get('output_tokens', 0)
        elif provider == 'cohere':
            output = data['text']
            input_tokens = data.get('meta', {}).get('billed_units', {}).get('input_tokens', 0)
            output_tokens = data.get('meta', {}).get('billed_units', {}).get('output_tokens', 0)
        else:
            # OpenAI format
            output = data['choices'][0]['message']['content']
            input_tokens = data.get('usage', {}).get('prompt_tokens', 0)
            output_tokens = data.get('usage', {}).get('completion_tokens', 0)

        print(json.dumps({
            'output': output,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'duration_ms': duration_ms,
            'model': model
        }))

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')[:500]
        print(json.dumps({'error': f'HTTP {e.code}: {error_body}'}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()
