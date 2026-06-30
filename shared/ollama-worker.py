#!/usr/bin/env python3
"""
Ollama Worker - Executes local model calls via Ollama
NO API KEYS NEEDED - runs on localhost
"""

import json
import sys
import urllib.request
import urllib.error


def call_ollama(model: str, prompt: str, max_tokens: int = 4096):
    """
    Call Ollama local model

    Args:
        model: Model name (e.g., 'phi3.5', 'deepseek-r1:32b')
        prompt: User prompt
        max_tokens: Maximum tokens

    Returns:
        dict with 'response' or 'error'
    """
    # Ollama endpoint
    url = 'http://localhost:11434/api/generate'

    # Build request
    request_data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens
        }
    }

    # Make HTTP request
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(request_data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        with urllib.request.urlopen(req, timeout=120) as response:
            response_data = json.loads(response.read().decode('utf-8'))

            return {
                'response': response_data.get('response', ''),
                'error': '',
                'input_tokens': response_data.get('prompt_eval_count', 0),
                'output_tokens': response_data.get('eval_count', 0)
            }

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        return {
            'error': f"HTTP {e.code}: {error_body}",
            'response': '',
            'input_tokens': 0,
            'output_tokens': 0
        }
    except Exception as e:
        return {
            'error': f"Ollama error: {str(e)}",
            'response': '',
            'input_tokens': 0,
            'output_tokens': 0
        }


def main():
    """Main entry point - reads JSON from stdin, returns JSON to stdout"""
    try:
        # Read parameters from stdin
        params = json.loads(input())

        model = params.get('model', 'phi3.5')
        task = params.get('task', '')
        max_tokens = params.get('max_tokens', 4096)

        # Call Ollama
        result = call_ollama(model, task, max_tokens)

        # Output JSON result
        print(json.dumps(result))

    except Exception as e:
        # Return error as JSON
        error_result = {
            'error': f"Worker error: {str(e)}",
            'response': '',
            'input_tokens': 0,
            'output_tokens': 0
        }
        print(json.dumps(error_result))
        sys.exit(1)


if __name__ == "__main__":
    main()
