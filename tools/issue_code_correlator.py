#!/usr/bin/env python3
"""
Issue+Code Correlator - Link GitHub/GitLab issues to relevant code sections

Uses embeddings to correlate issue descriptions with code files, functions, and
recent changes. Helps identify which parts of the codebase relate to bug reports,
feature requests, or technical debt.

Architecture:
1. Embed issue title+body using sentence-transformers (384-dim)
2. Embed code chunks (files, functions, recent diffs)
3. Cosine similarity search via pgvector
4. Rank correlations by relevance score

Database: PostgreSQL learning@laptop-01
Tables:
- learning.issue_embeddings (issue_id, repo, title, body, embedding, labels, created_at)
- learning.code_embeddings (file_path, chunk_type, chunk_id, code_text, embedding, last_modified)
- learning.issue_code_correlations (issue_id, file_path, chunk_id, similarity_score, correlation_type)

Usage:
    # Ingest issues from GitHub
    python3 issue_code_correlator.py ingest-issues --platform github --limit 50

    # Ingest code chunks from current repo
    python3 issue_code_correlator.py ingest-code --path . --extensions py,js,mjs

    # Find code related to issue #123
    python3 issue_code_correlator.py correlate --issue 123 --top 10

    # Find issues related to file path
    python3 issue_code_correlator.py reverse-correlate --file tools/complexity_estimator.py --top 5

    # Auto-correlate all issues
    python3 issue_code_correlator.py auto-correlate --threshold 0.7
"""

import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import warnings

warnings.filterwarnings('ignore')

try:
    import psycopg2
    from psycopg2.extras import execute_values
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    print(f"Missing dependency: {e}", file=sys.stderr)
    print("Install: pip3 install psycopg2-binary sentence-transformers", file=sys.stderr)
    sys.exit(1)


class IssueCodeCorrelator:
    """Correlate GitHub/GitLab issues with codebase using embeddings"""

    def __init__(self, db_host='laptop-01', db_name='learning', db_user='sfloess'):
        self.conn = psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user
        )
        self.model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
        self._init_tables()

    def _init_tables(self):
        """Create tables if not exist"""
        with self.conn.cursor() as cur:
            # Issue embeddings table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS learning.issue_embeddings (
                    issue_id INTEGER,
                    repo TEXT,
                    platform TEXT CHECK(platform IN ('github', 'gitlab')),
                    title TEXT NOT NULL,
                    body TEXT,
                    embedding vector(768),
                    labels JSONB DEFAULT '[]'::jsonb,
                    state TEXT CHECK(state IN ('open', 'closed')),
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (repo, platform, issue_id)
                )
            """)

            # Code embeddings table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS learning.code_embeddings (
                    id SERIAL PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    chunk_type TEXT CHECK(chunk_type IN ('file', 'function', 'class', 'diff')),
                    chunk_id TEXT,  -- function name, class name, commit hash, etc.
                    code_text TEXT NOT NULL,
                    embedding vector(768),
                    language TEXT,
                    lines_start INTEGER,
                    lines_end INTEGER,
                    last_modified TIMESTAMP DEFAULT NOW(),
                    UNIQUE(file_path, chunk_type, chunk_id)
                )
            """)

            # Correlation results table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS learning.issue_code_correlations (
                    issue_id INTEGER,
                    repo TEXT,
                    platform TEXT,
                    file_path TEXT,
                    chunk_id TEXT,
                    similarity_score REAL,
                    correlation_type TEXT CHECK(correlation_type IN ('direct', 'contextual', 'historical')),
                    created_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (repo, platform, issue_id, file_path, chunk_id)
                )
            """)

            # Create HNSW indexes for fast similarity search
            cur.execute("""
                CREATE INDEX IF NOT EXISTS issue_embedding_idx
                ON learning.issue_embeddings
                USING hnsw (embedding vector_cosine_ops)
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS code_embedding_idx
                ON learning.code_embeddings
                USING hnsw (embedding vector_cosine_ops)
            """)

            self.conn.commit()

    def ingest_issues(self, platform: str, limit: int = 100, state: str = 'open') -> int:
        """
        Fetch issues from GitHub/GitLab and store embeddings

        Args:
            platform: 'github' or 'gitlab'
            limit: Max issues to fetch
            state: 'open', 'closed', or 'all'

        Returns:
            Number of issues ingested
        """
        # Detect repo
        repo = self._get_repo_name()

        # Fetch issues via CLI
        if platform == 'github':
            cmd = f'gh issue list --state {state} --limit {limit} --json number,title,body,labels,createdAt,state'
        else:  # gitlab
            cmd = f'glab issue list --state {state} --per-page {limit} --json number,title,body,labels,createdAt,state'

        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
            issues = json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"Failed to fetch issues: {e}", file=sys.stderr)
            return 0
        except json.JSONDecodeError as e:
            print(f"Failed to parse issues JSON: {e}", file=sys.stderr)
            return 0

        ingested = 0
        with self.conn.cursor() as cur:
            for issue in issues:
                try:
                    # Combine title + body for embedding
                    text = f"{issue['title']}\n\n{issue.get('body', '')}"
                    embedding = self.model.encode(text, convert_to_numpy=True).tolist()

                    # Extract labels
                    labels = [
                        l['name'] if isinstance(l, dict) else l
                        for l in issue.get('labels', [])
                    ]

                    # Insert/update issue embedding
                    cur.execute("""
                        INSERT INTO learning.issue_embeddings
                        (issue_id, repo, platform, title, body, embedding, labels, state, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (repo, platform, issue_id)
                        DO UPDATE SET
                            title = EXCLUDED.title,
                            body = EXCLUDED.body,
                            embedding = EXCLUDED.embedding,
                            labels = EXCLUDED.labels,
                            state = EXCLUDED.state,
                            updated_at = NOW()
                    """, (
                        issue['number'],
                        repo,
                        platform,
                        issue['title'],
                        issue.get('body', ''),
                        embedding,
                        json.dumps(labels),
                        issue.get('state', 'open'),
                        issue.get('createdAt')
                    ))

                    ingested += 1
                except Exception as e:
                    print(f"Failed to ingest issue #{issue['number']}: {e}", file=sys.stderr)
                    continue

            self.conn.commit()

        return ingested

    def ingest_code(self, path: str = '.', extensions: List[str] = None, chunk_type: str = 'file') -> int:
        """
        Embed code files from repository

        Args:
            path: Repository path
            extensions: File extensions to include (e.g., ['py', 'js', 'mjs'])
            chunk_type: 'file' (whole file) or 'function' (per-function chunking)

        Returns:
            Number of code chunks ingested
        """
        if extensions is None:
            extensions = ['py', 'js', 'mjs', 'ts', 'tsx', 'java', 'cpp', 'c', 'h']

        repo_path = Path(path).resolve()
        ingested = 0

        # Find all matching files
        patterns = [f"**/*.{ext}" for ext in extensions]
        files = []
        for pattern in patterns:
            files.extend(repo_path.glob(pattern))

        # Filter out common exclusions
        exclude_patterns = [
            'node_modules', '.git', '__pycache__', 'dist', 'build',
            '.claude', 'venv', 'env', '.pytest_cache', 'coverage'
        ]
        files = [
            f for f in files
            if not any(excl in f.parts for excl in exclude_patterns)
        ]

        with self.conn.cursor() as cur:
            for file_path in files:
                try:
                    # Read file content
                    code_text = file_path.read_text(encoding='utf-8', errors='ignore')

                    # Skip empty or very large files
                    if not code_text.strip() or len(code_text) > 100000:
                        continue

                    # Generate embedding
                    embedding = self.model.encode(code_text[:10000], convert_to_numpy=True).tolist()

                    # Relative path from repo root
                    rel_path = str(file_path.relative_to(repo_path))

                    # Get file extension as language hint
                    language = file_path.suffix.lstrip('.')

                    # Get last modified time
                    last_modified = subprocess.run(
                        f"git log -1 --format=%cI -- {file_path}",
                        shell=True, capture_output=True, text=True, cwd=repo_path
                    ).stdout.strip() or None

                    # Insert/update code embedding
                    cur.execute("""
                        INSERT INTO learning.code_embeddings
                        (file_path, chunk_type, chunk_id, code_text, embedding, language, last_modified)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (file_path, chunk_type, chunk_id)
                        DO UPDATE SET
                            code_text = EXCLUDED.code_text,
                            embedding = EXCLUDED.embedding,
                            last_modified = EXCLUDED.last_modified
                    """, (
                        rel_path,
                        chunk_type,
                        rel_path,  # chunk_id = file_path for whole-file chunks
                        code_text[:50000],  # Store first 50k chars
                        embedding,
                        language,
                        last_modified
                    ))

                    ingested += 1

                    if ingested % 10 == 0:
                        print(f"Ingested {ingested} files...", file=sys.stderr)
                        self.conn.commit()

                except Exception as e:
                    print(f"Failed to ingest {file_path}: {e}", file=sys.stderr)
                    continue

            self.conn.commit()

        return ingested

    def correlate_issue(self, issue_id: int, top_k: int = 10, threshold: float = 0.6) -> List[Dict]:
        """
        Find code sections most relevant to an issue

        Args:
            issue_id: Issue number
            top_k: Return top K results
            threshold: Minimum similarity score (0-1)

        Returns:
            List of dicts with file_path, chunk_id, similarity_score, code_preview
        """
        repo = self._get_repo_name()
        platform = self._detect_platform()

        with self.conn.cursor() as cur:
            # Get issue embedding
            cur.execute("""
                SELECT embedding FROM learning.issue_embeddings
                WHERE repo = %s AND platform = %s AND issue_id = %s
            """, (repo, platform, issue_id))

            row = cur.fetchone()
            if not row:
                print(f"Issue #{issue_id} not found in database", file=sys.stderr)
                return []

            issue_embedding = row[0]

            # Find similar code chunks
            cur.execute("""
                SELECT
                    file_path,
                    chunk_id,
                    1 - (embedding <=> %s::vector) as similarity,
                    LEFT(code_text, 500) as code_preview,
                    language
                FROM learning.code_embeddings
                WHERE 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (issue_embedding, issue_embedding, threshold, issue_embedding, top_k))

            results = []
            for row in cur.fetchall():
                results.append({
                    'file_path': row[0],
                    'chunk_id': row[1],
                    'similarity_score': float(row[2]),
                    'code_preview': row[3],
                    'language': row[4]
                })

            # Store correlations
            for result in results:
                cur.execute("""
                    INSERT INTO learning.issue_code_correlations
                    (issue_id, repo, platform, file_path, chunk_id, similarity_score, correlation_type)
                    VALUES (%s, %s, %s, %s, %s, %s, 'direct')
                    ON CONFLICT (repo, platform, issue_id, file_path, chunk_id)
                    DO UPDATE SET
                        similarity_score = EXCLUDED.similarity_score,
                        created_at = NOW()
                """, (
                    issue_id, repo, platform,
                    result['file_path'],
                    result['chunk_id'],
                    result['similarity_score']
                ))

            self.conn.commit()

        return results

    def reverse_correlate(self, file_path: str, top_k: int = 5, threshold: float = 0.6) -> List[Dict]:
        """
        Find issues most relevant to a code file

        Args:
            file_path: Relative path to file
            top_k: Return top K results
            threshold: Minimum similarity score

        Returns:
            List of dicts with issue_id, title, similarity_score, labels
        """
        repo = self._get_repo_name()
        platform = self._detect_platform()

        with self.conn.cursor() as cur:
            # Get code embedding
            cur.execute("""
                SELECT embedding FROM learning.code_embeddings
                WHERE file_path = %s
                ORDER BY last_modified DESC
                LIMIT 1
            """, (file_path,))

            row = cur.fetchone()
            if not row:
                print(f"File '{file_path}' not found in database", file=sys.stderr)
                return []

            code_embedding = row[0]

            # Find similar issues
            cur.execute("""
                SELECT
                    issue_id,
                    title,
                    body,
                    1 - (embedding <=> %s::vector) as similarity,
                    labels,
                    state
                FROM learning.issue_embeddings
                WHERE repo = %s AND platform = %s
                  AND 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (code_embedding, repo, platform, code_embedding, threshold, code_embedding, top_k))

            results = []
            for row in cur.fetchall():
                results.append({
                    'issue_id': row[0],
                    'title': row[1],
                    'body_preview': row[2][:200] if row[2] else '',
                    'similarity_score': float(row[3]),
                    'labels': json.loads(row[4]) if row[4] else [],
                    'state': row[5]
                })

        return results

    def auto_correlate_all(self, threshold: float = 0.7, top_k: int = 5) -> Dict[str, int]:
        """
        Auto-correlate all issues with codebase

        Args:
            threshold: Minimum similarity score
            top_k: Top K correlations per issue

        Returns:
            Stats dict with issues_processed, correlations_found
        """
        repo = self._get_repo_name()
        platform = self._detect_platform()

        with self.conn.cursor() as cur:
            # Get all open issues
            cur.execute("""
                SELECT issue_id FROM learning.issue_embeddings
                WHERE repo = %s AND platform = %s AND state = 'open'
            """, (repo, platform))

            issue_ids = [row[0] for row in cur.fetchall()]

        stats = {'issues_processed': 0, 'correlations_found': 0}

        for issue_id in issue_ids:
            results = self.correlate_issue(issue_id, top_k=top_k, threshold=threshold)
            stats['issues_processed'] += 1
            stats['correlations_found'] += len(results)

            if stats['issues_processed'] % 10 == 0:
                print(f"Processed {stats['issues_processed']}/{len(issue_ids)} issues...", file=sys.stderr)

        return stats

    def _get_repo_name(self) -> str:
        """Get repository name from git remote"""
        result = subprocess.run(
            'git remote get-url origin',
            shell=True, capture_output=True, text=True
        )

        if result.returncode != 0:
            return 'local-repo'

        url = result.stdout.strip()
        # Extract repo name from URL (handles github.com/user/repo.git or gitlab.com/user/repo)
        parts = url.rstrip('.git').split('/')
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        return 'local-repo'

    def _detect_platform(self) -> str:
        """Detect if repo is GitHub or GitLab"""
        result = subprocess.run(
            'git remote -v | head -1',
            shell=True, capture_output=True, text=True
        )

        remote = result.stdout.lower()
        if 'github.com' in remote:
            return 'github'
        elif 'gitlab' in remote:
            return 'gitlab'
        return 'github'  # default

    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Issue+Code Correlator')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Ingest issues
    ingest_issues_parser = subparsers.add_parser('ingest-issues', help='Fetch and embed issues')
    ingest_issues_parser.add_argument('--platform', choices=['github', 'gitlab'], default='github')
    ingest_issues_parser.add_argument('--limit', type=int, default=100)
    ingest_issues_parser.add_argument('--state', choices=['open', 'closed', 'all'], default='open')

    # Ingest code
    ingest_code_parser = subparsers.add_parser('ingest-code', help='Embed code files')
    ingest_code_parser.add_argument('--path', default='.')
    ingest_code_parser.add_argument('--extensions', default='py,js,mjs,ts,java')

    # Correlate issue
    correlate_parser = subparsers.add_parser('correlate', help='Find code for issue')
    correlate_parser.add_argument('--issue', type=int, required=True)
    correlate_parser.add_argument('--top', type=int, default=10)
    correlate_parser.add_argument('--threshold', type=float, default=0.6)

    # Reverse correlate
    reverse_parser = subparsers.add_parser('reverse-correlate', help='Find issues for file')
    reverse_parser.add_argument('--file', required=True)
    reverse_parser.add_argument('--top', type=int, default=5)
    reverse_parser.add_argument('--threshold', type=float, default=0.6)

    # Auto-correlate
    auto_parser = subparsers.add_parser('auto-correlate', help='Correlate all issues')
    auto_parser.add_argument('--threshold', type=float, default=0.7)
    auto_parser.add_argument('--top', type=int, default=5)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    correlator = IssueCodeCorrelator()

    try:
        if args.command == 'ingest-issues':
            count = correlator.ingest_issues(
                platform=args.platform,
                limit=args.limit,
                state=args.state
            )
            print(f"✓ Ingested {count} issues")

        elif args.command == 'ingest-code':
            extensions = args.extensions.split(',')
            count = correlator.ingest_code(
                path=args.path,
                extensions=extensions
            )
            print(f"✓ Ingested {count} code files")

        elif args.command == 'correlate':
            results = correlator.correlate_issue(
                issue_id=args.issue,
                top_k=args.top,
                threshold=args.threshold
            )

            print(f"\n🔗 Top {len(results)} correlations for issue #{args.issue}:\n")
            for i, r in enumerate(results, 1):
                print(f"{i}. {r['file_path']} ({r['language']})")
                print(f"   Similarity: {r['similarity_score']:.3f}")
                print(f"   Preview: {r['code_preview'][:100]}...\n")

        elif args.command == 'reverse-correlate':
            results = correlator.reverse_correlate(
                file_path=args.file,
                top_k=args.top,
                threshold=args.threshold
            )

            print(f"\n🔗 Top {len(results)} issues for {args.file}:\n")
            for i, r in enumerate(results, 1):
                print(f"{i}. Issue #{r['issue_id']}: {r['title']}")
                print(f"   Similarity: {r['similarity_score']:.3f}")
                print(f"   Labels: {', '.join(r['labels'])}")
                print(f"   State: {r['state']}\n")

        elif args.command == 'auto-correlate':
            stats = correlator.auto_correlate_all(
                threshold=args.threshold,
                top_k=args.top
            )
            print(f"\n✓ Processed {stats['issues_processed']} issues")
            print(f"✓ Found {stats['correlations_found']} correlations")

    finally:
        correlator.close()


if __name__ == '__main__':
    main()
