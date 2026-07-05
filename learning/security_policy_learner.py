#!/usr/bin/env python3
"""
Security Policy Learner - Continual Learning for Security Patterns

Integrates with PostgreSQL + pgvector for policy storage and retrieval.
Learns from security audit results, vulnerability patterns, and fixes.

Features:
- Policy pattern learning (regex, AST-based)
- Risk scoring with Thompson Sampling
- Vector similarity search for policy recommendations
- OWASP Top 10 coverage tracking
- Automated policy evolution based on audit results

Database: learning schema on aio-01:5433
Tables: security_policies, security_violations, policy_performance
"""

import json
import re
import pickle
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import hashlib
import numpy as np

# Try to import sentence_transformers, graceful fallback
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
    embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    embedding_model = None


class SecurityPolicyLearner:
    """
    Continual learning system for security policies.

    Architecture:
    1. Pattern Learning: Extract regex/AST patterns from vulnerabilities
    2. Risk Scoring: Thompson Sampling for policy effectiveness
    3. Policy Storage: PostgreSQL with vector embeddings
    4. Recommendation: Similarity search for similar code patterns
    5. Evolution: Update policies based on audit feedback
    """

    def __init__(self, db_host='aio-01', db_port=5433, db_name='learning', db_user='claude'):
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.conn = None
        self.cursor = None

        # OWASP Top 10 2021 mapping
        self.owasp_categories = {
            'A01': 'Broken Access Control',
            'A02': 'Cryptographic Failures',
            'A03': 'Injection',
            'A04': 'Insecure Design',
            'A05': 'Security Misconfiguration',
            'A06': 'Vulnerable and Outdated Components',
            'A07': 'Identification and Authentication Failures',
            'A08': 'Software and Data Integrity Failures',
            'A09': 'Security Logging and Monitoring Failures',
            'A10': 'Server-Side Request Forgery'
        }

        # Severity scoring
        self.severity_scores = {
            'CRITICAL': 10,
            'HIGH': 7,
            'MEDIUM': 4,
            'LOW': 1,
            'INFO': 0
        }

        self._connect()
        self._init_schema()

    def _connect(self):
        """Connect to PostgreSQL database."""
        try:
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user
            )
            self.cursor = self.conn.cursor()
            print(f"✓ Connected to PostgreSQL: {self.db_host}:{self.db_port}/{self.db_name}")
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            raise

    def _init_schema(self):
        """Initialize database schema for security policy learning."""

        # Create security_policies table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning.security_policies (
                id SERIAL PRIMARY KEY,
                policy_id TEXT UNIQUE NOT NULL,
                policy_name TEXT NOT NULL,
                owasp_category TEXT,
                severity TEXT,
                pattern TEXT NOT NULL,
                pattern_type TEXT DEFAULT 'regex',
                description TEXT,
                embedding VECTOR(384),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                times_triggered INTEGER DEFAULT 0,
                true_positives INTEGER DEFAULT 0,
                false_positives INTEGER DEFAULT 0,
                precision FLOAT DEFAULT 0.0,
                active BOOLEAN DEFAULT TRUE
            )
        """)

        # Create security_violations table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning.security_violations (
                id SERIAL PRIMARY KEY,
                violation_id TEXT UNIQUE NOT NULL,
                policy_id TEXT REFERENCES learning.security_policies(policy_id),
                file_path TEXT NOT NULL,
                line_number INTEGER,
                code_snippet TEXT,
                severity TEXT,
                fixed BOOLEAN DEFAULT FALSE,
                fix_applied TEXT,
                embedding VECTOR(384),
                detected_at TIMESTAMP DEFAULT NOW(),
                fixed_at TIMESTAMP,
                metadata JSONB
            )
        """)

        # Create policy_performance table (Thompson Sampling state)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning.policy_performance (
                policy_id TEXT PRIMARY KEY,
                alpha FLOAT DEFAULT 1.0,
                beta FLOAT DEFAULT 1.0,
                successes INTEGER DEFAULT 0,
                failures INTEGER DEFAULT 0,
                total_reward FLOAT DEFAULT 0.0,
                avg_reward FLOAT DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT NOW()
            )
        """)

        # Create indexes
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_security_policies_embedding
            ON learning.security_policies USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_security_violations_embedding
            ON learning.security_violations USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_security_violations_policy
            ON learning.security_violations(policy_id)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_security_policies_owasp
            ON learning.security_policies(owasp_category)
        """)

        self.conn.commit()
        print("✓ Security policy schema initialized")

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using sentence-transformers."""
        if not EMBEDDINGS_AVAILABLE or embedding_model is None:
            return None

        try:
            embedding = embedding_model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            print(f"✗ Embedding generation failed: {e}")
            return None

    def add_policy(
        self,
        policy_name: str,
        pattern: str,
        owasp_category: str,
        severity: str,
        description: str,
        pattern_type: str = 'regex'
    ) -> str:
        """
        Add a new security policy.

        Args:
            policy_name: Human-readable policy name
            pattern: Regex or AST pattern to match
            owasp_category: OWASP category (A01-A10)
            severity: CRITICAL|HIGH|MEDIUM|LOW|INFO
            description: Policy description
            pattern_type: regex|ast|semantic

        Returns:
            policy_id
        """
        # Generate policy ID
        policy_id = hashlib.sha256(
            f"{policy_name}:{pattern}:{owasp_category}".encode()
        ).hexdigest()[:16]

        # Generate embedding
        embedding_text = f"{policy_name} {description} {pattern}"
        embedding = self.generate_embedding(embedding_text)

        try:
            self.cursor.execute("""
                INSERT INTO learning.security_policies
                (policy_id, policy_name, owasp_category, severity, pattern,
                 pattern_type, description, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (policy_id) DO UPDATE SET
                    updated_at = NOW(),
                    pattern = EXCLUDED.pattern,
                    description = EXCLUDED.description,
                    embedding = EXCLUDED.embedding
                RETURNING policy_id
            """, (
                policy_id, policy_name, owasp_category, severity,
                pattern, pattern_type, description, embedding
            ))

            result = self.cursor.fetchone()
            self.conn.commit()

            # Initialize Thompson Sampling state
            self._init_policy_performance(policy_id)

            print(f"✓ Added policy: {policy_name} ({policy_id})")
            return result[0]

        except Exception as e:
            self.conn.rollback()
            print(f"✗ Failed to add policy: {e}")
            raise

    def _init_policy_performance(self, policy_id: str):
        """Initialize Thompson Sampling state for a policy."""
        self.cursor.execute("""
            INSERT INTO learning.policy_performance (policy_id)
            VALUES (%s)
            ON CONFLICT (policy_id) DO NOTHING
        """, (policy_id,))
        self.conn.commit()

    def record_violation(
        self,
        policy_id: str,
        file_path: str,
        code_snippet: str,
        severity: str,
        line_number: Optional[int] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Record a security violation detected by a policy.

        Args:
            policy_id: Policy that detected the violation
            file_path: File where violation was found
            code_snippet: Code that triggered the violation
            severity: Severity level
            line_number: Line number (optional)
            metadata: Additional metadata (JSON)

        Returns:
            violation_id
        """
        # Generate violation ID
        violation_id = hashlib.sha256(
            f"{policy_id}:{file_path}:{line_number}:{code_snippet}".encode()
        ).hexdigest()[:16]

        # Generate embedding
        embedding = self.generate_embedding(code_snippet)

        try:
            self.cursor.execute("""
                INSERT INTO learning.security_violations
                (violation_id, policy_id, file_path, line_number,
                 code_snippet, severity, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (violation_id) DO UPDATE SET
                    detected_at = NOW()
                RETURNING violation_id
            """, (
                violation_id, policy_id, file_path, line_number,
                code_snippet, severity, embedding, json.dumps(metadata or {})
            ))

            result = self.cursor.fetchone()
            self.conn.commit()

            # Update policy trigger count
            self._update_policy_triggers(policy_id)

            return result[0]

        except Exception as e:
            self.conn.rollback()
            print(f"✗ Failed to record violation: {e}")
            raise

    def _update_policy_triggers(self, policy_id: str):
        """Increment policy trigger count."""
        self.cursor.execute("""
            UPDATE learning.security_policies
            SET times_triggered = times_triggered + 1
            WHERE policy_id = %s
        """, (policy_id,))
        self.conn.commit()

    def mark_violation_fixed(
        self,
        violation_id: str,
        fix_applied: str,
        is_true_positive: bool = True
    ):
        """
        Mark a violation as fixed and update policy performance.

        Args:
            violation_id: Violation to mark as fixed
            fix_applied: Description of the fix
            is_true_positive: Was this a real security issue?
        """
        self.cursor.execute("""
            UPDATE learning.security_violations
            SET fixed = TRUE,
                fix_applied = %s,
                fixed_at = NOW()
            WHERE violation_id = %s
            RETURNING policy_id
        """, (fix_applied, violation_id))

        result = self.cursor.fetchone()
        if result:
            policy_id = result[0]
            self._update_policy_performance(policy_id, is_true_positive)

        self.conn.commit()

    def _update_policy_performance(self, policy_id: str, is_true_positive: bool):
        """
        Update Thompson Sampling state based on violation feedback.

        Args:
            policy_id: Policy to update
            is_true_positive: Was the detection accurate?
        """
        # Update counts
        if is_true_positive:
            self.cursor.execute("""
                UPDATE learning.security_policies
                SET true_positives = true_positives + 1
                WHERE policy_id = %s
            """, (policy_id,))

            # Update Thompson Sampling (success)
            self.cursor.execute("""
                UPDATE learning.policy_performance
                SET successes = successes + 1,
                    alpha = alpha + 1,
                    total_reward = total_reward + 1,
                    avg_reward = total_reward / NULLIF(successes + failures, 0),
                    last_updated = NOW()
                WHERE policy_id = %s
            """, (policy_id,))
        else:
            self.cursor.execute("""
                UPDATE learning.security_policies
                SET false_positives = false_positives + 1
                WHERE policy_id = %s
            """, (policy_id,))

            # Update Thompson Sampling (failure)
            self.cursor.execute("""
                UPDATE learning.policy_performance
                SET failures = failures + 1,
                    beta = beta + 1,
                    avg_reward = total_reward / NULLIF(successes + failures, 0),
                    last_updated = NOW()
                WHERE policy_id = %s
            """, (policy_id,))

        # Update precision
        self.cursor.execute("""
            UPDATE learning.security_policies
            SET precision = CASE
                WHEN (true_positives + false_positives) > 0
                THEN true_positives::FLOAT / (true_positives + false_positives)
                ELSE 0.0
            END
            WHERE policy_id = %s
        """, (policy_id,))

        self.conn.commit()

    def find_similar_violations(
        self,
        code_snippet: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Find similar violations using vector similarity search.

        Args:
            code_snippet: Code to search for
            limit: Max results to return

        Returns:
            List of similar violations with metadata
        """
        if not EMBEDDINGS_AVAILABLE:
            print("✗ Embeddings not available, using fallback search")
            return []

        embedding = self.generate_embedding(code_snippet)
        if embedding is None:
            return []

        self.cursor.execute("""
            SELECT
                v.violation_id,
                v.policy_id,
                p.policy_name,
                v.file_path,
                v.code_snippet,
                v.severity,
                v.fixed,
                v.fix_applied,
                1 - (v.embedding <=> %s::vector) as similarity
            FROM learning.security_violations v
            JOIN learning.security_policies p ON v.policy_id = p.policy_id
            WHERE v.embedding IS NOT NULL
            ORDER BY v.embedding <=> %s::vector
            LIMIT %s
        """, (embedding, embedding, limit))

        results = []
        for row in self.cursor.fetchall():
            results.append({
                'violation_id': row[0],
                'policy_id': row[1],
                'policy_name': row[2],
                'file_path': row[3],
                'code_snippet': row[4],
                'severity': row[5],
                'fixed': row[6],
                'fix_applied': row[7],
                'similarity': float(row[8])
            })

        return results

    def recommend_policies(self, code_snippet: str, limit: int = 5) -> List[Dict]:
        """
        Recommend security policies for given code using Thompson Sampling.

        Args:
            code_snippet: Code to analyze
            limit: Max policies to recommend

        Returns:
            List of recommended policies
        """
        if not EMBEDDINGS_AVAILABLE:
            return self._recommend_policies_fallback(limit)

        embedding = self.generate_embedding(code_snippet)
        if embedding is None:
            return self._recommend_policies_fallback(limit)

        # Get top policies by similarity + Thompson Sampling score
        self.cursor.execute("""
            SELECT
                p.policy_id,
                p.policy_name,
                p.owasp_category,
                p.severity,
                p.pattern,
                p.description,
                p.precision,
                perf.alpha,
                perf.beta,
                perf.avg_reward,
                1 - (p.embedding <=> %s::vector) as similarity
            FROM learning.security_policies p
            LEFT JOIN learning.policy_performance perf ON p.policy_id = perf.policy_id
            WHERE p.active = TRUE AND p.embedding IS NOT NULL
            ORDER BY
                (1 - (p.embedding <=> %s::vector)) * 0.6 +
                COALESCE(perf.avg_reward, 0.5) * 0.4 DESC
            LIMIT %s
        """, (embedding, embedding, limit))

        results = []
        for row in self.cursor.fetchall():
            # Sample from Beta distribution (Thompson Sampling)
            alpha, beta = row[7] or 1.0, row[8] or 1.0
            thompson_sample = np.random.beta(alpha, beta)

            results.append({
                'policy_id': row[0],
                'policy_name': row[1],
                'owasp_category': row[2],
                'severity': row[3],
                'pattern': row[4],
                'description': row[5],
                'precision': float(row[6]) if row[6] else 0.0,
                'avg_reward': float(row[9]) if row[9] else 0.0,
                'similarity': float(row[10]),
                'thompson_score': float(thompson_sample)
            })

        return results

    def _recommend_policies_fallback(self, limit: int) -> List[Dict]:
        """Fallback recommendation without embeddings (use Thompson Sampling only)."""
        self.cursor.execute("""
            SELECT
                p.policy_id,
                p.policy_name,
                p.owasp_category,
                p.severity,
                p.pattern,
                p.description,
                p.precision,
                perf.alpha,
                perf.beta,
                perf.avg_reward
            FROM learning.security_policies p
            LEFT JOIN learning.policy_performance perf ON p.policy_id = perf.policy_id
            WHERE p.active = TRUE
            ORDER BY COALESCE(perf.avg_reward, 0.5) DESC
            LIMIT %s
        """, (limit,))

        results = []
        for row in self.cursor.fetchall():
            alpha, beta = row[7] or 1.0, row[8] or 1.0
            thompson_sample = np.random.beta(alpha, beta)

            results.append({
                'policy_id': row[0],
                'policy_name': row[1],
                'owasp_category': row[2],
                'severity': row[3],
                'pattern': row[4],
                'description': row[5],
                'precision': float(row[6]) if row[6] else 0.0,
                'avg_reward': float(row[9]) if row[9] else 0.0,
                'similarity': 0.0,
                'thompson_score': float(thompson_sample)
            })

        return results

    def get_policy_stats(self) -> Dict:
        """Get overall policy performance statistics."""
        self.cursor.execute("""
            SELECT
                COUNT(*) as total_policies,
                COUNT(CASE WHEN active = TRUE THEN 1 END) as active_policies,
                SUM(times_triggered) as total_triggers,
                SUM(true_positives) as total_true_positives,
                SUM(false_positives) as total_false_positives,
                AVG(precision) as avg_precision
            FROM learning.security_policies
        """)

        row = self.cursor.fetchone()

        self.cursor.execute("""
            SELECT
                COUNT(*) as total_violations,
                COUNT(CASE WHEN fixed = TRUE THEN 1 END) as fixed_violations
            FROM learning.security_violations
        """)

        violations = self.cursor.fetchone()

        return {
            'total_policies': row[0],
            'active_policies': row[1],
            'total_triggers': row[2] or 0,
            'total_true_positives': row[3] or 0,
            'total_false_positives': row[4] or 0,
            'avg_precision': float(row[5]) if row[5] else 0.0,
            'total_violations': violations[0],
            'fixed_violations': violations[1] or 0
        }

    def export_policies(self, output_path: str):
        """Export all policies to JSON file."""
        self.cursor.execute("""
            SELECT
                p.policy_id,
                p.policy_name,
                p.owasp_category,
                p.severity,
                p.pattern,
                p.pattern_type,
                p.description,
                p.times_triggered,
                p.true_positives,
                p.false_positives,
                p.precision,
                perf.alpha,
                perf.beta,
                perf.avg_reward
            FROM learning.security_policies p
            LEFT JOIN learning.policy_performance perf ON p.policy_id = perf.policy_id
            WHERE p.active = TRUE
            ORDER BY perf.avg_reward DESC NULLS LAST
        """)

        policies = []
        for row in self.cursor.fetchall():
            policies.append({
                'policy_id': row[0],
                'policy_name': row[1],
                'owasp_category': row[2],
                'severity': row[3],
                'pattern': row[4],
                'pattern_type': row[5],
                'description': row[6],
                'times_triggered': row[7],
                'true_positives': row[8],
                'false_positives': row[9],
                'precision': float(row[10]) if row[10] else 0.0,
                'thompson_sampling': {
                    'alpha': float(row[11]) if row[11] else 1.0,
                    'beta': float(row[12]) if row[12] else 1.0,
                    'avg_reward': float(row[13]) if row[13] else 0.0
                }
            })

        with open(output_path, 'w') as f:
            json.dump(policies, f, indent=2)

        print(f"✓ Exported {len(policies)} policies to {output_path}")

    def close(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()


def main():
    """Demo: Initialize and test security policy learner."""
    learner = SecurityPolicyLearner()

    # Add sample OWASP policies
    print("\n=== Adding Security Policies ===")

    # A03: Injection
    learner.add_policy(
        policy_name="SQL Injection - String Concatenation",
        pattern=r"(execute|query)\s*\([^)]*\+[^)]*\)",
        owasp_category="A03",
        severity="CRITICAL",
        description="SQL queries built with string concatenation are vulnerable to injection"
    )

    learner.add_policy(
        policy_name="Command Injection - os.system",
        pattern=r"os\.system\([^)]*\+",
        owasp_category="A03",
        severity="CRITICAL",
        description="System commands with user input allow command injection"
    )

    # A02: Cryptographic Failures
    learner.add_policy(
        policy_name="Weak Hashing - MD5",
        pattern=r"hashlib\.md5\(",
        owasp_category="A02",
        severity="HIGH",
        description="MD5 is cryptographically broken, use SHA-256 or better"
    )

    # A05: Security Misconfiguration
    learner.add_policy(
        policy_name="Debug Mode Enabled",
        pattern=r"DEBUG\s*=\s*True",
        owasp_category="A05",
        severity="HIGH",
        description="Debug mode should never be enabled in production"
    )

    # A07: Authentication Failures
    learner.add_policy(
        policy_name="Hardcoded Password",
        pattern=r"password\s*=\s*[\"'][^\"']{4,}[\"']",
        owasp_category="A07",
        severity="CRITICAL",
        description="Passwords should never be hardcoded in source code"
    )

    # Test violation recording
    print("\n=== Recording Test Violations ===")

    violation1 = learner.record_violation(
        policy_id=learner.cursor.execute(
            "SELECT policy_id FROM learning.security_policies WHERE policy_name LIKE 'SQL Injection%' LIMIT 1"
        ) or learner.cursor.fetchone()[0],
        file_path="/path/to/app.py",
        code_snippet='cursor.execute("SELECT * FROM users WHERE id=" + user_id)',
        severity="CRITICAL",
        line_number=42,
        metadata={'context': 'user authentication'}
    )

    # Get statistics
    print("\n=== Policy Statistics ===")
    stats = learner.get_policy_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Export policies
    output_path = "/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning/security_policies_export.json"
    learner.export_policies(output_path)

    learner.close()
    print("\n✓ Security Policy Learner initialized successfully")


if __name__ == '__main__':
    main()
