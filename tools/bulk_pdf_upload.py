#!/usr/bin/env python3
"""
Bulk PDF Upload - Uses existing REST API to ingest all PDFs

Uses the /api/v1/ingest/pdf endpoint with parallel uploads
"""

import subprocess
import json
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

PDF_DIR = '/mnt/nas/media/books'
API_URL = 'http://aio-01:8000/api/v1/ingest/pdf'
MAX_WORKERS = 8  # Parallel uploads
BATCH_SIZE = 100  # Process in batches for progress tracking

def find_all_pdfs():
    """Find all PDFs in the library"""
    print("Finding PDFs...")
    result = subprocess.run(
        ['find', PDF_DIR, '-type', 'f', '-name', '*.pdf'],
        capture_output=True,
        text=True
    )

    pdfs = [p for p in result.stdout.strip().split('\n') if p]
    print(f"✅ Found {len(pdfs)} PDFs")
    return pdfs

def get_api_key():
    """Get API key from database"""
    import psycopg2

    try:
        conn = psycopg2.connect(
            host='aio-01',
            port=5433,
            dbname='learning',
            user='sfloess'
        )
        cursor = conn.cursor()

        # Get first active API key
        cursor.execute("""
            SELECT key_prefix || '-' || encode(key_hash, 'hex')
            FROM auth.api_keys
            WHERE is_active = true
            LIMIT 1
        """)

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            return row[0]

        # If no key exists, create one
        print("⚠️  No API key found - the REST API requires authentication")
        print("Run: python3 api/document-ingestion-api.py --create-api-key")
        return None

    except Exception as e:
        print(f"⚠️  Could not get API key: {e}")
        return None

def upload_pdf(pdf_path, api_key):
    """Upload a single PDF to the REST API"""

    result = {
        'pdf_path': pdf_path,
        'success': False,
        'document_id': None,
        'error': None,
        'status': None
    }

    try:
        # Use curl to upload
        cmd = [
            'curl',
            '-X', 'POST',
            '-H', f'X-API-Key: {api_key}',
            '-F', f'file=@{pdf_path}',
            '-F', 'source=bulk_library_import',
            '-F', 'tags=pdf,library,bulk_import',
            '-s',  # Silent
            API_URL
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout per PDF
        )

        if proc.returncode != 0:
            result['error'] = f"Curl failed: {proc.stderr}"
            return result

        # Parse JSON response
        try:
            response = json.loads(proc.stdout)
        except json.JSONDecodeError:
            result['error'] = f"JSON parse error: {proc.stdout[:200]}"
            return result

        result['status'] = response.get('status')
        result['document_id'] = response.get('document_id')

        if result['status'] in ['accepted', 'duplicate']:
            result['success'] = True
        else:
            result['error'] = response.get('message', 'Unknown error')

        return result

    except subprocess.TimeoutExpired:
        result['error'] = "Upload timeout (>120s)"
        return result
    except Exception as e:
        result['error'] = str(e)
        return result

def process_batch(pdfs, batch_num, total_batches, api_key):
    """Process a batch of PDFs in parallel"""

    print(f"\n{'='*60}")
    print(f"BATCH {batch_num}/{total_batches} - {len(pdfs)} PDFs")
    print(f"{'='*60}\n")

    start_time = time.time()
    results = []

    # Upload PDFs in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(upload_pdf, pdf, api_key): pdf for pdf in pdfs}

        for future in as_completed(futures):
            pdf = futures[future]
            try:
                result = future.result()
                results.append(result)

                # Progress feedback
                if result['success']:
                    status = '✓ (DUP)' if result['status'] == 'duplicate' else '✓'
                    print(f"{status} {Path(pdf).name}")
                else:
                    print(f"✗ {Path(pdf).name}: {result['error']}")

            except Exception as e:
                results.append({
                    'pdf_path': pdf,
                    'success': False,
                    'error': str(e)
                })
                print(f"✗ {Path(pdf).name}: {e}")

    elapsed = time.time() - start_time

    successful = sum(1 for r in results if r['success'])
    duplicates = sum(1 for r in results if r.get('status') == 'duplicate')
    failed = len(results) - successful

    print(f"\n✅ Batch {batch_num} completed in {elapsed:.1f}s")
    print(f"  Uploaded: {successful - duplicates}/{len(results)}")
    print(f"  Duplicates: {duplicates}/{len(results)}")
    print(f"  Failed: {failed}/{len(results)}")

    return results

def main():
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║        BULK PDF UPLOAD - REST API PARALLEL MODE              ║")
    print("╚════════════════════════════════════════════════════════════════╝\n")

    # Check if API is running
    import requests
    try:
        r = requests.get('http://aio-01:8000/health', timeout=2)
        if r.status_code != 200:
            print("❌ REST API not running on aio-01:8000")
            print("Start with: python3 api/document-ingestion-api.py")
            return 1
    except Exception as e:
        print(f"❌ Cannot reach REST API: {e}")
        print("Start with: python3 api/document-ingestion-api.py")
        return 1

    print("✅ REST API is running\n")

    # Get API key
    api_key = get_api_key()
    if not api_key:
        return 1

    print(f"✅ API key loaded\n")

    # Find all PDFs
    all_pdfs = find_all_pdfs()

    if not all_pdfs:
        print("No PDFs found!")
        return 1

    # Split into batches
    batches = []
    for i in range(0, len(all_pdfs), BATCH_SIZE):
        batches.append(all_pdfs[i:i+BATCH_SIZE])

    print(f"\nProcessing strategy:")
    print(f"  Total PDFs: {len(all_pdfs)}")
    print(f"  Batch size: {BATCH_SIZE}")
    print(f"  Total batches: {len(batches)}")
    print(f"  Parallel uploads: {MAX_WORKERS}")
    print(f"  Estimated time: {len(batches) * 5}-{len(batches) * 10} minutes\n")

    # Process each batch
    total_results = []
    total_successful = 0
    total_duplicates = 0
    total_failed = 0

    for i, batch in enumerate(batches, 1):
        results = process_batch(batch, i, len(batches), api_key)
        total_results.extend(results)

        successful = sum(1 for r in results if r['success'])
        duplicates = sum(1 for r in results if r.get('status') == 'duplicate')
        failed = len(results) - successful

        total_successful += successful
        total_duplicates += duplicates
        total_failed += failed

        print(f"\nCumulative:")
        print(f"  ✅ Total uploaded: {total_successful - total_duplicates}/{len(total_results)}")
        print(f"  🔁 Total duplicates: {total_duplicates}/{len(total_results)}")
        print(f"  ❌ Total failed: {total_failed}/{len(total_results)}")

    print(f"\n{'='*60}")
    print("COMPLETE")
    print(f"{'='*60}")
    print(f"Total PDFs processed: {len(total_results)}")
    print(f"Uploaded: {total_successful - total_duplicates} ({(total_successful - total_duplicates)/len(total_results)*100:.1f}%)")
    print(f"Duplicates: {total_duplicates} ({total_duplicates/len(total_results)*100:.1f}%)")
    print(f"Failed: {total_failed} ({total_failed/len(total_results)*100:.1f}%)")

    return 0

if __name__ == '__main__':
    sys.exit(main())
