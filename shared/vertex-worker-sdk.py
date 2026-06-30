#!/opt/vertex-venv/bin/python3
"""
Vertex AI Worker using Anthropic SDK
Requires: pip install anthropic[vertex]
"""

import json
import sys
import os

try:
    from anthropic import AnthropicVertex
except ImportError:
    # Fallback error message
    print(json.dumps({
        'error': 'anthropic[vertex] package not installed. Run: pip install anthropic[vertex]',
        'response': '',
        'input_tokens': 0,
        'output_tokens': 0
    }))
    sys.exit(1)


def call_vertex_ai(project_id: str, region: str, model: str, prompt: str, max_tokens: int = 4096):
    """
    Call Claude via Vertex AI using Anthropic SDK

    Args:
        project_id: Google Cloud project ID
        region: Region (e.g., 'us-east5', 'europe-west1')
        model: Claude model version
        prompt: User prompt
        max_tokens: Maximum tokens

    Returns:
        dict with 'response' or 'error'
    """
    try:
        # Initialize Vertex AI client
        client = AnthropicVertex(project_id=project_id, region=region)

        # Map common model names
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

        vertex_model = model
        for key, value in model_map.items():
            if key in model.lower():
                vertex_model = value
                break

        # Call API
        message = client.messages.create(
            model=vertex_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Extract response
        response_text = ''
        for block in message.content:
            if hasattr(block, 'text'):
                response_text += block.text

        return {
            'response': response_text,
            'error': '',
            'input_tokens': message.usage.input_tokens,
            'output_tokens': message.usage.output_tokens
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
        region = params.get('region', 'us-east5')  # Default Vertex region for Claude
        model = params.get('model', 'claude-3-5-sonnet-v2@20241022')
        task = params.get('task', '')
        max_tokens = params.get('max_tokens', 4096)

        # Call Vertex AI
        result = call_vertex_ai(project_id, region, model, task, max_tokens)

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
