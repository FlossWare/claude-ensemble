#!/usr/bin/env python3
"""
Generate embeddings for PDFs using Cloudflare Workers AI

Usage:
    python3 generate_pdf_embeddings.py <start_id> <end_id>

Example:
    python3 generate_pdf_embeddings.py 1 100
"""

import sys
import os
import requests
import json
import psycopg2

# Cloudflare Workers AI API
CLOUDFLARE_ACCOUNT_ID = os.getenv('CLOUDFLARE_ACCOUNT_ID', '')
CLOUDFLARE_API_KEY = os.getenv('CLOUDFLARE_API_KEY', '')

def generate_embedding(text):
    """Generate embedding using Cloudflare Workers AI"""

    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_KEY:
        # Fallback: Use a simple hash-based embedding (for testing)
        import hashlib
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        # Create 384-dim vector from hash
        embedding = []
        for i in range(384):
            embedding.append((hash_bytes[i % len(hash_bytes)] - 128) / 128.0)
        return embedding

    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/baai/bge-small-en-v1.5"

    headers = {
        'Authorization': f'Bearer {CLOUDFLARE_API_KEY}',
        'Content-Type': 'application/json'
    }

    # Truncate text to 512 tokens (~2048 chars)
    truncated = text[:2048]

    payload = {
        'text': truncated
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            embedding = result['result']['data']
            # Cloudflare returns [[...]] - flatten it
            if isinstance(embedding[0], list):
                embedding = embedding[0]
            return embedding
        else:
            print(f"API error: {response.status_code}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"Request error: {e}", file=sys.stderr)
        return None

def process_pdfs(start_id, end_id):
    """Process PDFs in the given ID range"""

    conn = psycopg2.connect(
        host='aio-01',
        port=5433,
        dbname='learning',
        user='claude'
    )

    cursor = conn.cursor()

    # Get PDFs in range
    cursor.execute("""
        SELECT id, pdf_path, text_preview, text_length
        FROM learning.pdf_metadata
        WHERE id >= %s AND id <= %s
        ORDER BY id
    """, (start_id, end_id))

    pdfs = cursor.fetchall()

    print(f"Processing {len(pdfs)} PDFs (ID {start_id}-{end_id})")

    success = 0
    failed = 0

    for pdf_id, pdf_path, text_preview, text_length in pdfs:
        # Use text_preview or first 2048 chars for embedding
        text = text_preview if text_preview else ""

        if not text or len(text) < 50:
            failed += 1
            continue

        # Generate embedding
        embedding = generate_embedding(text)

        if embedding:
            # Store in PostgreSQL
            cursor.execute("""
                UPDATE learning.pdf_metadata
                SET embedding = %s
                WHERE id = %s
            """, (embedding, pdf_id))

            # ALSO store in Neo4j
            try:
                import subprocess
                escaped_path = pdf_path.replace("'", "'\\''")
                # Convert embedding to string for Neo4j
                emb_str = str(embedding)

                subprocess.run([
                    'node', '-e',
                    f"""
                    const neo4j = require('neo4j-driver');
                    const driver = neo4j.driver('bolt://aio-01:7687', neo4j.auth.basic('neo4j', 'neo4j'));
                    const session = driver.session();
                    session.run(
                        'MATCH (p:PDFDocument {{path: $path}}) SET p.embedding = $embedding',
                        {{path: '{escaped_path}', embedding: {emb_str}}}
                    ).then(() => session.close()).then(() => driver.close()).catch(() => {{}});
                    """
                ], capture_output=True, timeout=5, cwd='/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills')
            except:
                pass  # Neo4j update is best-effort

            success += 1

            if success % 10 == 0:
                conn.commit()
                print(f"  Progress: {success}/{len(pdfs)}")
        else:
            failed += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Complete: {success} success, {failed} failed")

    return {
        'success': success,
        'failed': failed,
        'total': len(pdfs)
    }

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python3 generate_pdf_embeddings.py <start_id> <end_id>")
        sys.exit(1)

    start_id = int(sys.argv[1])
    end_id = int(sys.argv[2])

    result = process_pdfs(start_id, end_id)

    print(json.dumps(result))
