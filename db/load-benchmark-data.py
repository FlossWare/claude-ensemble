#!/usr/bin/env python3
"""
Load benchmark dataset into PostgreSQL evaluation schema
Usage: python3 db/load-benchmark-data.py [--host localhost] [--port 5432] [--database learning] [--user sfloess]
"""

import json
import argparse
import sys
from pathlib import Path

def load_benchmark_data(host='localhost', port=5432, database='learning', user='sfloess'):
    """Load benchmark dataset from JSON into PostgreSQL"""
    try:
        import psycopg2
        from psycopg2.extras import Json
    except ImportError:
        print("✗ psycopg2 not installed. Install with: pip install psycopg2-binary")
        return False
    
    # Locate benchmark file
    benchmark_file = Path(__file__).parent.parent / 'evaluation' / 'benchmark-dataset.json'
    
    if not benchmark_file.exists():
        print(f"✗ Benchmark file not found: {benchmark_file}")
        return False
    
    print(f"Loading benchmark data from {benchmark_file}")
    
    # Load JSON
    with open(benchmark_file) as f:
        data = json.load(f)
    
    questions = data.get('questions', [])
    print(f"✓ Loaded {len(questions)} benchmark questions")
    
    # Connect to database
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user
        )
        cursor = conn.cursor()
        print(f"✓ Connected to {user}@{host}:{port}/{database}")
    except psycopg2.OperationalError as e:
        print(f"✗ Database connection failed: {e}")
        return False
    
    # Insert benchmark questions
    inserted = 0
    try:
        for q in questions:
            cursor.execute("""
                INSERT INTO evaluation.benchmarks
                (task_type, question, ground_truth, difficulty, category)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                q['task_type'],
                q['question'],
                Json(q['ground_truth']),
                q['difficulty'],
                q.get('category', q['task_type'])
            ))
            inserted += 1
        
        conn.commit()
        print(f"✓ Inserted {inserted} benchmark questions")
    except Exception as e:
        print(f"✗ Insert failed: {e}")
        conn.rollback()
        cursor.close()
        conn.close()
        return False
    
    # Verify insertion
    try:
        cursor.execute("SELECT COUNT(*) FROM evaluation.benchmarks")
        count = cursor.fetchone()[0]
        print(f"✓ Verified: {count} total questions in database")
        
        # Show distribution
        cursor.execute("""
            SELECT task_type, COUNT(*) as count, difficulty, COUNT(*) FILTER (WHERE difficulty = 'easy') as easy,
                   COUNT(*) FILTER (WHERE difficulty = 'medium') as medium,
                   COUNT(*) FILTER (WHERE difficulty = 'hard') as hard
            FROM evaluation.benchmarks
            GROUP BY task_type, difficulty
            ORDER BY task_type
        """)
        
        print("\nTask type distribution:")
        task_counts = {}
        for row in cursor.fetchall():
            task_type = row[0]
            if task_type not in task_counts:
                task_counts[task_type] = 0
            task_counts[task_type] += row[1]
        
        for task_type in sorted(task_counts.keys()):
            print(f"  {task_type}: {task_counts[task_type]}")
        
        # Show difficulty distribution
        cursor.execute("""
            SELECT difficulty, COUNT(*) FROM evaluation.benchmarks
            GROUP BY difficulty
            ORDER BY difficulty
        """)
        
        print("\nDifficulty distribution:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}")
    
    except Exception as e:
        print(f"✗ Verification failed: {e}")
        cursor.close()
        conn.close()
        return False
    
    cursor.close()
    conn.close()
    print("\n✓ Benchmark data loaded successfully!")
    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Load benchmark dataset into PostgreSQL')
    parser.add_argument('--host', default='localhost', help='Database host')
    parser.add_argument('--port', type=int, default=5432, help='Database port')
    parser.add_argument('--database', default='learning', help='Database name')
    parser.add_argument('--user', default='sfloess', help='Database user')
    
    args = parser.parse_args()
    
    success = load_benchmark_data(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user
    )
    
    sys.exit(0 if success else 1)
