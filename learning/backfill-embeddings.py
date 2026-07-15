#!/usr/bin/env python3
"""
Backfill embeddings for learnings that don't have them
Runs in batches to avoid memory issues
"""
import psycopg2
import sys
import os
from sentence_transformers import SentenceTransformer
import warnings
warnings.filterwarnings('ignore')

# Database connection with env var support
try:
    conn = psycopg2.connect(
        host=os.getenv('PGHOST', 'aio-01'),
        port=int(os.getenv('PGPORT', '5433')),
        database=os.getenv('PGDATABASE', 'learning'),
        user=os.getenv('PGUSER', 'sfloess'),
        password=os.getenv('PGPASSWORD')  # Falls back to .pgpass or peer auth if unset
    )
    cursor = conn.cursor()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    sys.exit(1)

# Load model once
try:
    print('Loading sentence-transformers model...')
    model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
    print('✅ Model loaded')
except Exception as e:
    print(f'❌ Model loading failed: {e}')
    cursor.close()
    conn.close()
    sys.exit(1)

# Process batches until complete
processed = 0
failed = 0
MAX_ITERATIONS = 1000
iteration = 0

try:
    while iteration < MAX_ITERATIONS:
        iteration += 1

        # Find learnings without embeddings
        cursor.execute("""
            SELECT id, description, actionable_insight
            FROM workflow.learnings
            WHERE learning_embedding IS NULL
            ORDER BY id
            LIMIT 100
        """)

        learnings = cursor.fetchall()
        if not learnings:
            print(f'✅ Complete! Processed: {processed}, Failed: {failed}')
            break

        print(f'Batch {iteration}: Found {len(learnings)} learnings without embeddings')

        # Generate and store embeddings
        for i, (learning_id, description, insight) in enumerate(learnings, 1):
            try:
                combined_text = f"{description} {insight}"

                # Generate embedding
                embedding = model.encode(combined_text[:10000])
                embedding_json = '[' + ','.join(map(str, embedding)) + ']'

                # Update database
                cursor.execute("""
                    UPDATE workflow.learnings
                    SET learning_embedding = %s::vector
                    WHERE id = %s
                """, (embedding_json, learning_id))

                processed += 1

                if i % 10 == 0:
                    print(f'  Progress: {processed} processed, {failed} failed')

            except psycopg2.OperationalError as e:
                print(f'❌ Database connection lost: {e}')
                raise  # Exit to outer handler
            except Exception as e:
                print(f'❌ Failed to process learning {learning_id}: {e}')
                failed += 1
                continue

        # Commit batch
        conn.commit()

    if iteration >= MAX_ITERATIONS:
        print(f'⚠️  Hit iteration limit ({MAX_ITERATIONS}). Check for stuck records.')

except KeyboardInterrupt:
    print('\n⚠️  Interrupted by user. Committing partial progress...')
    conn.commit()
except psycopg2.OperationalError as e:
    print(f'❌ Fatal database error: {e}')
    sys.exit(1)
finally:
    cursor.close()
    conn.close()
    print(f'Final stats: {processed} processed, {failed} failed')
