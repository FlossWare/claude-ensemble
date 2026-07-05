#!/usr/bin/env python3
"""
Batch PDF Processor - Uses orchestrator to process PDFs in parallel

Processes all PDFs from /mnt/nas/media/books using orchestrate_smart.py
distributed across 8 workers.
"""

import sys
import os
import subprocess
import json
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

PDF_DIR = '/mnt/nas/media/books'
BATCH_SIZE = 100
PROCESS_SCRIPT = str(Path(__file__).parent / 'process_single_pdf.py')

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

def process_batch_with_orchestrator(pdfs, batch_num, total_batches):
    """Process a batch of PDFs using orchestrator"""

    print(f"\n{'='*60}")
    print(f"BATCH {batch_num}/{total_batches} - {len(pdfs)} PDFs")
    print(f"{'='*60}\n")

    # Create task that will process PDFs
    task = f"""Process {len(pdfs)} PDFs in parallel - extract knowledge claims.

For each PDF, run this command:
python3 {PROCESS_SCRIPT} "<pdf_path>"

PDFs to process:
{chr(10).join(pdfs[:20])}
{f"... and {len(pdfs) - 20} more" if len(pdfs) > 20 else ""}

Return: JSON array of results from each PDF processed.
Format: [{{"pdf_path": "...", "category": "...", "claims": [...]}}, ...]

Process ALL {len(pdfs)} PDFs and return complete results."""

    # Run orchestrator
    start_time = time.time()

    result = subprocess.run(
        [
            'python3',
            'orchestrate_smart.py',
            '--task', task,
            '--workers', '8',
            '--max-retries', '1'
        ],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent)
    )

    elapsed = time.time() - start_time

    if result.returncode != 0:
        print(f"❌ Batch {batch_num} failed: {result.stderr}")
        return []

    print(f"✅ Batch {batch_num} completed in {elapsed:.1f}s")

    # Parse results from orchestrator output
    # For now, return placeholder - we'll process PDFs directly
    return []

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
                """, (pdf_path, category, claim, 0.8))
                stored += 1
            except Exception as e:
                print(f"  ⚠️  Failed to store claim: {e}")

    conn.commit()
    cursor.close()
    conn.close()

    print(f"✅ Stored {stored} claims in PostgreSQL")

def main():
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║       BATCH PDF PROCESSOR - ORCHESTRATOR PARALLEL MODE        ║")
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
    print(f"  Workers per batch: 8")
    print(f"  Estimated time: {len(batches) * 12}-{len(batches) * 15} minutes\n")

    # Process each batch
    total_results = []

    for i, batch in enumerate(batches, 1):
        results = process_batch_with_orchestrator(batch, i, len(batches))
        total_results.extend(results)

        # Store after each batch
        if results:
            store_results_in_postgres(results)

    print(f"\n{'='*60}")
    print("COMPLETE")
    print(f"{'='*60}")
    print(f"Total PDFs processed: {len(total_results)}")
    print(f"Successful: {sum(1 for r in total_results if r.get('success'))}")
    print(f"Failed: {sum(1 for r in total_results if not r.get('success'))}")

if __name__ == '__main__':
    main()
