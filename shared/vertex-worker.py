#!/usr/bin/env python3
"""
Vertex AI Worker - Executes Claude API calls via Google Cloud Vertex AI
Uses REST API with access tokens from gcloud auth
"""

import json
import sys
import subprocess
import urllib.request
import urllib.error


def get_access_token():
    """Get Google Cloud access token using gcloud"""
    try:
        result = subprocess.run(
            ['gcloud', 'auth', 'print-access-token'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except:
        return None


def call_vertex_ai(project_id: str, location: str, model: str, prompt: str, max_tokens: int = 4096):
    """
    Call Claude via Vertex AI REST API

    Args:
        project_id: Google Cloud project ID
        location: Region (e.g., 'us-central1', 'europe-west1')
        model: Claude model version
        prompt: User prompt
        max_tokens: Maximum tokens

    Returns:
        dict with 'response' or 'error'
    """
    # Map model names to Vertex AI versions
    model_map = {
        'claude-3-5-sonnet': 'claude-3-5-sonnet-v2@20241022',
        'claude-3-5-haiku': 'claude-3-5-haiku@20241022',
        'claude-3-opus': 'claude-3-opus@20240229',
        'claude-sonnet': 'claude-3-5-sonnet-v2@20241022',
        'claude-haiku': 'claude-3-5-haiku@20241022',
        'sonnet': 'claude-3-5-sonnet-v2@20241022',
        'haiku': 'claude-3-5-haiku@20241022',
        'opus': 'claude-3-opus@20240229'
    }

    # Normalize model name
    vertex_model = model
    for key, value in model_map.items():
        if key in model.lower():
            vertex_model = value
            break

    # Get access token
    access_token = get_access_token()
    if not access_token:
        return {
            'error': 'Failed to get Google Cloud access token - run: gcloud auth application-default login',
            'response': '',
            'input_tokens': 0,
            'output_tokens': 0
        }

    # Build Vertex AI URL
    url = f'https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/anthropic/models/{vertex_model}:streamRawPredict'

    # Build request
    request_data = {
        "anthropic_version": "vertex-2023-10-16",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": max_tokens
    }

    # Make HTTP request
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(request_data).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
        )

        with urllib.request.urlopen(req, timeout=60) as response:
            response_text = response.read().decode('utf-8')

            # Parse response (may be streaming format)
            lines = response_text.strip().split('\n')
            full_text = ''
            input_tokens = 0
            output_tokens = 0

            for line in lines:
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    if 'content' in data and len(data['content']) > 0:
                        for content_block in data['content']:
                            if content_block.get('type') == 'text':
                                full_text += content_block.get('text', '')
                    if 'usage' in data:
                        input_tokens = data['usage'].get('input_tokens', 0)
                        output_tokens = data['usage'].get('output_tokens', 0)

            return {
                'response': full_text,
                'error': '',
                'input_tokens': input_tokens,
                'output_tokens': output_tokens
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
            'error': f"Vertex AI error: {str(e)}",
            'response': '',
            'input_tokens': 0,
            'output_tokens': 0
        }


def main():
    """Main entry point - reads JSON from stdin, returns JSON to stdout"""
    try:
        # Read parameters from stdin
        params = json.loads(input())

        project_id = params.get('project_id', 'itpc-gcp-uie-eng-claude')
        location = params.get('location', 'us-central1')
        model = params.get('model', 'claude-3-5-sonnet-v2@20241022')
        task = params.get('task', '')
        max_tokens = params.get('max_tokens', 4096)

        # Call Vertex AI
        result = call_vertex_ai(project_id, location, model, task, max_tokens)

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
