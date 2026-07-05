#!/usr/bin/env python3
"""
Process PDFs using direct SSH to workers (no API calls)

Distributes 849 PDFs across 8 workers for parallel text extraction
"""

import subprocess
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

PDF_DIR = '/mnt/nas/media/books'
WORKERS = ['server-01', 'server-02', 'server-03', 'laptop-01', 'pi-01', 'pi-02', 'desktop-ap', 'server-ap']
BATCH_SIZE = 100

def find_all_pdfs():
    """Find all PDFs recursively"""
    print("Finding PDFs in /mnt/nas/media/books...")
    result = subprocess.run(
        ['find', PDF_DIR, '-type', 'f', '-name', '*.pdf'],
        capture_output=True,
        text=True
    )
    pdfs = [p for p in result.stdout.strip().split('\n') if p]
    print(f"✅ Found {len(pdfs)} PDFs")
    return pdfs

def chunk_list(lst, n):
    """Split list into n equal chunks"""
    chunk_size = (len(lst) + n - 1) // n
    return [lst[i:i+chunk_size] for i in range(0, len(lst), chunk_size)]

def process_on_worker(worker, pdfs):
    """Process PDFs on a single worker via SSH"""

    # Create Python script to run on worker
    script = '''
import subprocess
import json
import sys

pdfs = ''' + json.dumps(pdfs) + '''
results = []

for pdf_path in pdfs:
    try:
        result = subprocess.run(
            ['pdftotext', pdf_path, '-'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            results.append({'pdf': pdf_path, 'success': False, 'error': 'pdftotext failed'})
            continue

        text = result.stdout
        if len(text.strip()) < 100:
            results.append({'pdf': pdf_path, 'success': False, 'error': 'No text extracted'})
            continue

        results.append({
            'pdf': pdf_path,
            'success': True,
            'text_length': len(text),
            'preview': text[:200]
        })

    except Exception as e:
        results.append({'pdf': pdf_path, 'success': False, 'error': str(e)})

print(json.dumps({'results': results}))
'''

    # Execute on worker via SSH
    try:
        result = subprocess.run(
            ['ssh', f'claude@{worker}', 'python3', '-c', script],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            return {
                'worker': worker,
                'error': f"SSH failed: {result.stderr[:200]}",
                'results': []
            }

        # Parse JSON output
        data = json.loads(result.stdout)
        return {
            'worker': worker,
            'results': data.get('results', [])
        }

    except subprocess.TimeoutExpired:
        return {
            'worker': worker,
            'error': 'Timeout (>5 minutes)',
            'results': []
        }
    except json.JSONDecodeError as e:
        return {
            'worker': worker,
            'error': f'JSON parse error: {e}',
            'results': []
        }
    except Exception as e:
        return {
            'worker': worker,
            'error': str(e),
            'results': []
        }

def process_batch_parallel(pdfs, batch_num, total_batches):
    """Process batch using direct SSH to 8 workers in parallel"""

    print(f"\n{'='*70}")
    print(f"BATCH {batch_num}/{total_batches} - Processing {len(pdfs)} PDFs")
    print(f"{'='*70}")

    # Split PDFs across 8 workers
    chunks = chunk_list(pdfs, len(WORKERS))

    print(f"\nDistribution:")
    for i, chunk in enumerate(chunks):
        if chunk:
            print(f"  {WORKERS[i]}: {len(chunk)} PDFs")

    # Execute on workers in parallel
    print(f"\nExecuting via direct SSH to {len(WORKERS)} workers...\n")
    start_time = time.time()

    all_results = []
    successful = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=len(WORKERS)) as executor:
        futures = {executor.submit(process_on_worker, WORKERS[i], chunk): WORKERS[i]
                  for i, chunk in enumerate(chunks) if chunk}

        for future in as_completed(futures):
            worker = futures[future]
            try:
                worker_result = future.result()

                if 'error' in worker_result:
                    print(f"  ❌ {worker}: {worker_result['error']}")
                    # Count PDFs as failed
                    worker_idx = WORKERS.index(worker)
                    failed += len(chunks[worker_idx])
                    continue

                pdfs_processed = worker_result['results']
                worker_success = sum(1 for r in pdfs_processed if r.get('success'))
                worker_failed = len(pdfs_processed) - worker_success

                successful += worker_success
                failed += worker_failed
                all_results.extend(pdfs_processed)

                print(f"  ✅ {worker}: {worker_success}/{len(pdfs_processed)} successful")

            except Exception as e:
                print(f"  ❌ {worker}: Exception: {e}")
                worker_idx = WORKERS.index(worker)
                failed += len(chunks[worker_idx])

    elapsed = time.time() - start_time

    print(f"\n✅ Batch {batch_num} completed in {elapsed:.1f}s")
    print(f"   Successful: {successful}/{len(pdfs)}")
    print(f"   Failed: {failed}/{len(pdfs)}")

    return all_results

def store_in_postgres(results):
    """Store extracted PDF data in PostgreSQL"""

    if not results:
        return 0

    print(f"\nStoring {len(results)} results in PostgreSQL...")

    import psycopg2

    try:
        conn = psycopg2.connect(
            host='aio-01',
            port=5433,
            dbname='learning',
            user='claude'
        )
        cursor = conn.cursor()

        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning.pdf_metadata (
                id SERIAL PRIMARY KEY,
                pdf_path TEXT UNIQUE NOT NULL,
                text_length INT,
                text_preview TEXT,
                processed_at TIMESTAMP DEFAULT NOW()
            )
        """)

        stored = 0
        for result in results:
            if not result.get('success'):
                continue

            pdf_path = result['pdf']
            text_preview = result.get('preview', '')
            text_length = result.get('text_length', 0)

            try:
                cursor.execute("""
                    INSERT INTO learning.pdf_metadata
                    (pdf_path, text_length, text_preview, processed_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (pdf_path) DO UPDATE SET
                        text_length = EXCLUDED.text_length,
                        text_preview = EXCLUDED.text_preview,
                        processed_at = NOW()
                """, (pdf_path, text_length, text_preview))
                stored += 1
            except Exception as e:
                print(f"  ⚠️  Failed to store {Path(pdf_path).name}: {e}")

        conn.commit()
        cursor.close()
        conn.close()

        print(f"✅ Stored {stored} PDFs in PostgreSQL")
        return stored

    except Exception as e:
        print(f"⚠️  PostgreSQL error: {e}")
        return 0

def main():
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║     PDF PROCESSING - DIRECT SSH PARALLEL MODE (8 WORKERS)       ║")
    print("╚══════════════════════════════════════════════════════════════════╝\n")

    # Find all PDFs
    all_pdfs = find_all_pdfs()

    if not all_pdfs:
        print("❌ No PDFs found!")
        return 1

    # Split into batches
    batches = []
    for i in range(0, len(all_pdfs), BATCH_SIZE):
        batches.append(all_pdfs[i:i+BATCH_SIZE])

    print(f"\nProcessing Plan:")
    print(f"  Total PDFs: {len(all_pdfs)}")
    print(f"  Batch size: {BATCH_SIZE} PDFs")
    print(f"  Total batches: {len(batches)}")
    print(f"  Workers: {len(WORKERS)}")
    print(f"  PDFs per worker per batch: ~{BATCH_SIZE // len(WORKERS)}")
    print(f"  Estimated time: {len(batches) * 2}-{len(batches) * 4} minutes")
    print(f"  Total: ~{(len(batches) * 3) // 60}h {(len(batches) * 3) % 60}m\n")

    # Process each batch
    total_successful = 0
    total_failed = 0

    for i, batch in enumerate(batches, 1):
        results = process_batch_parallel(batch, i, len(batches))

        # Count successes
        batch_success = sum(1 for r in results if r.get('success'))
        batch_failed = len(results) - batch_success

        total_successful += batch_success
        total_failed += batch_failed

        # Store batch results
        store_in_postgres(results)

        if total_successful + total_failed > 0:
            print(f"\nCumulative Progress:")
            print(f"  ✅ Total successful: {total_successful}/{total_successful + total_failed}")
            print(f"  ❌ Total failed: {total_failed}/{total_successful + total_failed}")
            print(f"  📊 Success rate: {total_successful/(total_successful + total_failed)*100:.1f}%")

    print(f"\n{'='*70}")
    print("COMPLETE - ALL 849 PDFs PROCESSED")
    print(f"{'='*70}")
    print(f"Total processed: {total_successful + total_failed}")
    if total_successful + total_failed > 0:
        print(f"Successful: {total_successful} ({total_successful/(total_successful + total_failed)*100:.1f}%)")
        print(f"Failed: {total_failed} ({total_failed/(total_successful + total_failed)*100:.1f}%)")

    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
