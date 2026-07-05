#!/usr/bin/env python3
"""
Process a single PDF: Extract text and generate knowledge claims

Usage:
    python3 process_single_pdf.py <pdf_path>

Returns JSON:
    {
        "pdf_path": "...",
        "category": "...",
        "claims": [...],
        "page_count": N,
        "success": true/false,
        "error": "..." (if failed)
    }
"""

import sys
import subprocess
import json
import os
import requests

def extract_pdf_text(pdf_path):
    """Extract text from PDF using pdftotext"""
    try:
        result = subprocess.run(
            ['pdftotext', pdf_path, '-'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return None, f"pdftotext failed: {result.stderr}"

        return result.stdout, None
    except subprocess.TimeoutExpired:
        return None, "PDF extraction timeout (>30s)"
    except FileNotFoundError:
        return None, "pdftotext not found - install poppler-utils"
    except Exception as e:
        return None, f"Extraction error: {str(e)}"

def count_pdf_pages(pdf_path):
    """Count pages in PDF"""
    try:
        result = subprocess.run(
            ['pdfinfo', pdf_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        for line in result.stdout.split('\n'):
            if line.startswith('Pages:'):
                return int(line.split(':')[1].strip())
        return 0
    except:
        return 0

def analyze_text_with_api(text, pdf_name):
    """Use API to extract claims and categorize"""

    # Truncate text if too long (keep first 10k chars)
    if len(text) > 10000:
        text = text[:10000] + "\n... [truncated]"

    prompt = f"""Analyze this PDF text and extract knowledge claims.

PDF: {pdf_name}

Text:
{text}

Extract 5-10 key claims that are:
1. Falsifiable (can be proven true/false)
2. Specific (not vague)
3. Important/useful knowledge

Also categorize the PDF into ONE of:
- computer_science
- electronics
- physics
- mathematics
- sci_fi
- methodology
- other

Return ONLY valid JSON:
{{
    "category": "<category>",
    "claims": ["claim 1", "claim 2", ...]
}}
"""

    try:
        # Call local proxy
        response = requests.post(
            'http://aio-01:8000/v1/chat/completions',
            json={
                'model': 'llama-3.3-70b-versatile',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
                'max_tokens': 1000
            },
            timeout=30
        )

        if response.status_code != 200:
            return None, None, f"API error: {response.status_code}"

        result = response.json()
        content = result['choices'][0]['message']['content']

        # Try to parse JSON from response
        # Handle markdown code blocks
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            content = content.split('```')[1].split('```')[0]

        data = json.loads(content.strip())

        category = data.get('category', 'other')
        claims = data.get('claims', [])

        return category, claims, None

    except requests.Timeout:
        return None, None, "API timeout"
    except json.JSONDecodeError as e:
        return None, None, f"JSON parse error: {str(e)}"
    except Exception as e:
        return None, None, f"API error: {str(e)}"

def process_pdf(pdf_path):
    """Main processing function"""

    result = {
        'pdf_path': pdf_path,
        'category': None,
        'claims': [],
        'page_count': 0,
        'success': False,
        'error': None
    }

    # Check file exists
    if not os.path.exists(pdf_path):
        result['error'] = "File not found"
        return result

    # Count pages
    result['page_count'] = count_pdf_pages(pdf_path)

    # Extract text
    text, error = extract_pdf_text(pdf_path)
    if error:
        result['error'] = error
        return result

    if not text or len(text.strip()) < 100:
        result['error'] = "No text extracted or too short"
        return result

    # Analyze with API
    pdf_name = os.path.basename(pdf_path)
    category, claims, error = analyze_text_with_api(text, pdf_name)

    if error:
        result['error'] = error
        return result

    result['category'] = category
    result['claims'] = claims
    result['success'] = True

    return result

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: process_single_pdf.py <pdf_path>'}))
        sys.exit(1)

    pdf_path = sys.argv[1]
    result = process_pdf(pdf_path)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result['success'] else 1)
