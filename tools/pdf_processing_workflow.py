#!/usr/bin/env python3
"""
PDF Processing Workflow - Distributed across fleet

Processes PDFs using orchestrator with proper Python execution on each worker
"""

import sys
import os
import subprocess
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.fleet_executor import execute_on_fleet_parallel

PDF_DIR = '/mnt/nas/media/books'
BATCH_SIZE = 100
PROCESS_SCRIPT = str(Path(__file__).parent / 'process_single_pdf.py')

# Fleet configuration
WORKERS = [
    'server-01',
    'server-02',
    'server-03',
    'laptop-01',
    'pi-01',
    'pi-02',
    'desktop-ap',
    'server-ap'
]

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

def chunk_list(lst, n):
    """Split list into n chunks"""
    chunk_size = len(lst) // n + (1 if len(lst) % n else 0)
    return [lst[i:i+chunk_size] for i in range(0, len(lst), chunk_size)]

def process_batch_parallel(pdfs, batch_num, total_batches):
    """Process batch of PDFs using fleet in parallel"""

    print(f"\n{'='*60}")
    print(f"BATCH {batch_num}/{total_batches} - {len(pdfs)} PDFs")
    print(f"{'='*60}\n")

    # Split PDFs across 8 workers
    chunks = chunk_list(pdfs, len(WORKERS))

    # Create tasks for each worker
    tasks = []
    for i, chunk in enumerate(chunks):
        if not chunk:
            continue

        # Build Python script that processes this worker's PDFs
        script = f"""
import sys
import json
sys.path.insert(0, '/opt/claude-orchestrator/tools')
from process_single_pdf import process_pdf

pdfs = {json.dumps(chunk)}
results = []

for pdf_path in pdfs:
    result = process_pdf(pdf_path)
    results.append(result)

    # Progress
    if result.get('success'):
        print(f"✓ {{pdf_path}}", file=sys.stderr)
    else:
        print(f"✗ {{pdf_path}}: {{result.get('error', 'Unknown')}}", file=sys.stderr)

# Return results as JSON
print(json.dumps({{'results': results}}))
"""
        tasks.append(script)

    # Execute on fleet
    start_time = time.time()

    print(f"Distributing {len(pdfs)} PDFs across {len(WORKERS)} workers...")
    print(f"Per worker: ~{len(pdfs) // len(WORKERS)} PDFs\n")

    # Use fleet executor - pass Python script as task
    results = execute_on_fleet_parallel(
        workers=WORKERS,
        model='llama-3.3-70b-versatile',  # Dummy - we're running Python not API
        tasks=tasks,
        max_tokens=50000,
        timeout_ms=600000  # 10 minute timeout per worker
    )

    elapsed = time.time() - start_time

    print(f"\n✅ Batch {batch_num} completed in {elapsed:.1f}s")

    # Parse results from each worker
    all_results = []
    for worker_idx, worker_result in enumerate(results):
        if 'error' in worker_result:
            print(f"  ⚠️  Worker {WORKERS[worker_idx]}: {worker_result['error']}")
            continue

        # Extract JSON from output
        try:
            output = worker_result.get('output', '')
            data = json.loads(output)
            worker_pdfs = data.get('results', [])
            all_results.extend(worker_pdfs)
            print(f"  ✅ Worker {WORKERS[worker_idx]}: {len(worker_pdfs)} PDFs processed")
        except json.JSONDecodeError as e:
            print(f"  ⚠️  Worker {WORKERS[worker_idx]}: JSON parse error - {e}")

    return all_results

def store_results_in_postgres(results):
    """Store extracted claims in PostgreSQL"""

    if not results:
        return

    print(f"\nStoring {len(results)} results in PostgreSQL...")

    import psycopg2

    conn = psycopg2.connect(
        host='aio-01',
        port=5433,
        dbname='learning',
        user='claude'
    )

    cursor = conn.cursor()
    stored = 0

    for result in results:
        if not result.get('success'):
            continue

        pdf_path = result['pdf_path']
        category = result.get('category', 'other')
        claims = result.get('claims', [])

        for claim in claims:
            try:
                cursor.execute("""
                    INSERT INTO learning.pdf_knowledge
                    (pdf_path, category, claim, confidence, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                """, (pdf_path, category, claim, 0.8))
                stored += 1
            except Exception as e:
                print(f"  ⚠️  Failed to store claim: {e}")

    conn.commit()
    cursor.close()
    conn.close()

    print(f"✅ Stored {stored} new claims in PostgreSQL")

def main():
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║       PDF PROCESSING WORKFLOW - DISTRIBUTED FLEET MODE        ║")
    print("╚════════════════════════════════════════════════════════════════╝\n")

    # Find all PDFs
    all_pdfs = find_all_pdfs()

    if not all_pdfs:
        print("No PDFs found!")
        return

    # Split into batches
    batches = []
    for i in range(0, len(all_pdfs), BATCH_SIZE):
        batches.append(all_pdfs[i:i+BATCH_SIZE])

    print(f"\nProcessing strategy:")
    print(f"  Total PDFs: {len(all_pdfs)}")
    print(f"  Batch size: {BATCH_SIZE}")
    print(f"  Total batches: {len(batches)}")
    print(f"  Workers: {len(WORKERS)}")
    print(f"  PDFs per worker: ~{BATCH_SIZE // len(WORKERS)}")
    print(f"  Estimated time: {len(batches) * 10}-{len(batches) * 15} minutes\n")

    # Process each batch
    total_results = []
    total_successful = 0
    total_failed = 0

    for i, batch in enumerate(batches, 1):
        results = process_batch_parallel(batch, i, len(batches))
        total_results.extend(results)

        # Count successes
        successful = sum(1 for r in results if r.get('success'))
        failed = len(results) - successful
        total_successful += successful
        total_failed += failed

        # Store after each batch
        if results:
            store_results_in_postgres(results)

        print(f"\nBatch {i} Summary:")
        print(f"  ✅ Successful: {successful}/{len(results)}")
        print(f"  ❌ Failed: {failed}/{len(results)}")
        print(f"\nCumulative:")
        print(f"  ✅ Total successful: {total_successful}/{len(total_results)}")
        print(f"  ❌ Total failed: {total_failed}/{len(total_results)}")

    print(f"\n{'='*60}")
    print("COMPLETE")
    print(f"{'='*60}")
    print(f"Total PDFs processed: {len(total_results)}")
    print(f"Successful: {total_successful} ({total_successful/len(total_results)*100:.1f}%)")
    print(f"Failed: {total_failed} ({total_failed/len(total_results)*100:.1f}%)")

if __name__ == '__main__':
    main()
