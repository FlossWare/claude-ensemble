#!/usr/bin/env python3
"""
Vertex AI Worker - Executes Claude API calls via Google Cloud Vertex AI
Uses Application Default Credentials (gcloud auth)
"""

import json
import sys
import subprocess


def call_vertex_ai(project_id: str, location: str, model: str, prompt: str, max_tokens: int = 4096):
    """
    Call Claude via Vertex AI using gcloud CLI

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

    # Build request JSON
    request = {
        "anthropic_version": "vertex-2023-10-16",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": max_tokens
    }

    # Call via gcloud CLI
    try:
        cmd = [
            'gcloud', 'ai', 'models', 'predict',
            vertex_model,
            f'--project={project_id}',
            f'--region={location}',
            '--json-request=-'
        ]

        result = subprocess.run(
            cmd,
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            return {
                'error': f"gcloud command failed: {result.stderr}",
                'response': '',
                'input_tokens': 0,
                'output_tokens': 0
            }

        # Parse response
        response_data = json.loads(result.stdout)

        # Extract text from Claude response
        if 'content' in response_data and len(response_data['content']) > 0:
            response_text = response_data['content'][0].get('text', '')
        else:
            response_text = str(response_data)

        return {
            'response': response_text,
            'error': '',
            'input_tokens': response_data.get('usage', {}).get('input_tokens', 0),
            'output_tokens': response_data.get('usage', {}).get('output_tokens', 0)
        }

    except subprocess.TimeoutExpired:
        return {
            'error': 'Vertex AI request timed out',
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
