#!/usr/bin/env python3
"""
Orchestrator-Based Reasoning Pattern Learner

Uses multi-model consensus to extract and apply reasoning patterns.

DESIGN PRINCIPLES (for iteration):
1. Modular: Each phase is independent function
2. Configurable: All parameters externalized
3. Extensible: Easy to add new pattern types
4. Observable: All operations logged + metrics
5. Versioned: Pattern schema supports evolution
"""

import psycopg2
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
import hashlib

# ============================================================================
# CONFIGURATION (easy to change without code edits)
# ============================================================================

class ReasoningLearnerConfig:
    """Configuration for reasoning learner (modify for iteration)"""

    # PostgreSQL connection
    DB_HOST = 'aio-01'
    DB_PORT = 5433
    DB_USER = 'sfloess'
    DB_NAME = 'learning'

    # Learning parameters (TUNE THESE!)
    MIN_CONSENSUS_RATIO = 0.66  # 4/6 models must agree (can adjust: 0.5 = 3/6, 0.83 = 5/6)
    MIN_CONFIDENCE = 0.7        # Only learn from confident models
    MAX_PATTERN_AGE_DAYS = 90   # Patterns expire (can disable: None)

    # Pattern matching (for retrieval)
    SIMILARITY_THRESHOLD = 0.75  # How similar task must be to use pattern
    MAX_SIMILAR_PATTERNS = 5     # Return top N similar patterns

    # Versioning (for schema evolution)
    PATTERN_SCHEMA_VERSION = 1   # Increment when changing pattern structure

    # Extension hooks (add custom logic here)
    CUSTOM_EXTRACTORS = {}       # task_type -> custom extraction function
    CUSTOM_VALIDATORS = {}       # task_type -> custom validation function


# ============================================================================
# CORE LEARNER CLASS
# ============================================================================

class OrchestratorReasoningLearner:
    """
    Learn reasoning patterns from multi-model consensus

    EXTENSION POINTS:
    - add_custom_extractor(): Add task-specific pattern extraction
    - add_custom_validator(): Add custom validation logic
    - pattern_to_prompt(): Override how patterns become prompts
    - _calculate_similarity(): Override similarity metric
    """

    def __init__(self, config: ReasoningLearnerConfig = None):
        self.config = config or ReasoningLearnerConfig()
        self.db = self._get_db()
        self.cursor = self.db.cursor()
        self._init_schema()

    def _get_db(self):
        return psycopg2.connect(
            host=self.config.DB_HOST,
            port=self.config.DB_PORT,
            user=self.config.DB_USER,
            database=self.config.DB_NAME
        )

    def _init_schema(self):
        """Create tables if not exist (versioned for iteration)"""

        # Main patterns table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning.reasoning_patterns (
                id SERIAL PRIMARY KEY,
                pattern_hash VARCHAR(64) UNIQUE,  -- Dedup identical patterns
                task_type VARCHAR(100),
                task_description TEXT,

                -- Pattern content (JSONB for flexibility)
                reasoning_steps JSONB,      -- Array of step descriptions
                example_task TEXT,          -- Concrete example
                example_solution TEXT,      -- Example solution
                metadata JSONB,             -- Extensible metadata

                -- Quality metrics
                consensus_score FLOAT,      -- How many models agreed (0-1)
                avg_confidence FLOAT,       -- Average model confidence
                success_rate FLOAT DEFAULT 1.0,  -- Updated as pattern used
                times_used INT DEFAULT 0,
                times_successful INT DEFAULT 0,

                -- Versioning & lifecycle
                schema_version INT,
                created_at TIMESTAMP DEFAULT NOW(),
                last_used TIMESTAMP,
                expires_at TIMESTAMP,

                -- Search (embedding stored separately for flexibility)
                embedding_id VARCHAR(64)    -- Reference to embedding storage
            )
        """)

        # Pattern embeddings (separate table for easy schema changes)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning.reasoning_embeddings (
                id VARCHAR(64) PRIMARY KEY,
                embedding VECTOR(384),      -- Sentence transformer embedding
                embedding_model VARCHAR(100) DEFAULT 'all-MiniLM-L6-v2',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Pattern usage history (for A/B testing & iteration)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning.pattern_usage (
                id SERIAL PRIMARY KEY,
                pattern_id INT REFERENCES learning.reasoning_patterns(id),
                task_hash VARCHAR(64),
                model_used VARCHAR(100),
                success BOOLEAN,
                execution_time_ms INT,
                quality_score FLOAT,
                feedback JSONB,             -- Extensible feedback data
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Create indexes
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_task_type
            ON learning.reasoning_patterns(task_type)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_success_rate
            ON learning.reasoning_patterns(success_rate DESC)
        """)

        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_embeddings_vector
            ON learning.reasoning_embeddings USING hnsw (embedding vector_cosine_ops)
        """)

        self.db.commit()

    # ========================================================================
    # PHASE 1: LEARN FROM CONSENSUS (extensible)
    # ========================================================================

    def learn_from_consensus(
        self,
        task: str,
        task_type: str,
        worker_results: List[Dict[str, Any]],
        metadata: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Extract reasoning pattern from multi-model consensus

        Args:
            task: The task description
            task_type: Category (debugging, code_generation, etc.)
            worker_results: List of {model, reasoning_steps, solution, confidence}
            metadata: Optional extensible metadata

        Returns:
            Learned pattern dict or None if no consensus

        EXTENSION POINT: Override for custom extraction logic
        """

        # Check if custom extractor registered
        if task_type in self.config.CUSTOM_EXTRACTORS:
            return self.config.CUSTOM_EXTRACTORS[task_type](
                task, worker_results, metadata
            )

        # Default extraction logic
        return self._extract_consensus_pattern(
            task, task_type, worker_results, metadata
        )

    def _extract_consensus_pattern(
        self,
        task: str,
        task_type: str,
        worker_results: List[Dict],
        metadata: Optional[Dict]
    ) -> Optional[Dict]:
        """Default consensus extraction (can override)"""

        # Filter by confidence
        high_confidence = [
            r for r in worker_results
            if r.get('confidence', 0) >= self.config.MIN_CONFIDENCE
        ]

        if len(high_confidence) < 3:
            print(f"⚠️  Too few confident results ({len(high_confidence)})")
            return None

        # Extract reasoning steps from each model
        all_steps = []
        for result in high_confidence:
            steps = result.get('reasoning_steps', [])
            if steps:
                all_steps.append(steps)

        if not all_steps:
            print("⚠️  No reasoning steps provided by models")
            return None

        # Find consensus steps (appear in majority of results)
        consensus_steps = self._find_step_consensus(all_steps)

        # Calculate consensus score
        consensus_score = len(high_confidence) / len(worker_results)

        if consensus_score < self.config.MIN_CONSENSUS_RATIO:
            print(f"⚠️  Consensus too low ({consensus_score:.2%})")
            return None

        # Get best solution (highest confidence)
        best_result = max(high_confidence, key=lambda r: r.get('confidence', 0))

        # Build pattern
        pattern = {
            'task_type': task_type,
            'task_description': task,
            'reasoning_steps': consensus_steps,
            'example_task': task,
            'example_solution': best_result.get('solution', ''),
            'consensus_score': consensus_score,
            'avg_confidence': sum(r.get('confidence', 0) for r in high_confidence) / len(high_confidence),
            'metadata': metadata or {},
            'worker_count': len(worker_results),
            'models_used': [r.get('model', 'unknown') for r in worker_results]
        }

        # Validate pattern (extension point)
        if not self._validate_pattern(pattern):
            return None

        # Store pattern
        pattern_id = self._store_pattern(pattern)
        pattern['id'] = pattern_id

        print(f"✅ Learned pattern #{pattern_id} for {task_type}")
        print(f"   Consensus: {consensus_score:.1%}, Steps: {len(consensus_steps)}")

        return pattern

    def _find_step_consensus(self, all_steps: List[List[str]]) -> List[str]:
        """
        Find common reasoning steps across models

        EXTENSION POINT: Override for custom consensus algorithm
        """

        # Flatten all steps
        step_counts = {}
        for steps in all_steps:
            for step in steps:
                # Normalize step text
                normalized = step.lower().strip()
                step_counts[normalized] = step_counts.get(normalized, 0) + 1

        # Keep steps that appear in majority
        threshold = len(all_steps) * self.config.MIN_CONSENSUS_RATIO
        consensus = [
            step for step, count in step_counts.items()
            if count >= threshold
        ]

        return consensus

    def _validate_pattern(self, pattern: Dict) -> bool:
        """
        Validate pattern before storing

        EXTENSION POINT: Add custom validation per task type
        """

        task_type = pattern['task_type']

        # Check custom validator
        if task_type in self.config.CUSTOM_VALIDATORS:
            return self.config.CUSTOM_VALIDATORS[task_type](pattern)

        # Default validation
        if not pattern['reasoning_steps']:
            return False

        if len(pattern['reasoning_steps']) < 2:
            return False

        return True

    def _store_pattern(self, pattern: Dict) -> int:
        """Store pattern in PostgreSQL"""

        # Generate hash for deduplication
        pattern_hash = self._hash_pattern(pattern)

        # Check if exists
        self.cursor.execute(
            "SELECT id FROM learning.reasoning_patterns WHERE pattern_hash = %s",
            (pattern_hash,)
        )
        existing = self.cursor.fetchone()

        if existing:
            print(f"   Pattern already exists (id={existing[0]})")
            return existing[0]

        # Generate embedding (placeholder - implement with sentence-transformers)
        embedding_id = self._generate_embedding(pattern)

        # Calculate expiry
        expires_at = None
        if self.config.MAX_PATTERN_AGE_DAYS:
            from datetime import timedelta
            expires_at = datetime.now() + timedelta(days=self.config.MAX_PATTERN_AGE_DAYS)

        # Insert pattern
        self.cursor.execute("""
            INSERT INTO learning.reasoning_patterns
            (pattern_hash, task_type, task_description, reasoning_steps,
             example_task, example_solution, metadata, consensus_score,
             avg_confidence, schema_version, embedding_id, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            pattern_hash,
            pattern['task_type'],
            pattern['task_description'],
            json.dumps(pattern['reasoning_steps']),
            pattern['example_task'],
            pattern['example_solution'],
            json.dumps(pattern['metadata']),
            pattern['consensus_score'],
            pattern['avg_confidence'],
            self.config.PATTERN_SCHEMA_VERSION,
            embedding_id,
            expires_at
        ))

        pattern_id = self.cursor.fetchone()[0]
        self.db.commit()

        return pattern_id

    def _hash_pattern(self, pattern: Dict) -> str:
        """Generate hash for pattern deduplication"""

        # Hash based on task type + reasoning steps
        content = f"{pattern['task_type']}:{json.dumps(sorted(pattern['reasoning_steps']))}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _generate_embedding(self, pattern: Dict) -> str:
        """
        Generate embedding for pattern

        EXTENSION POINT: Swap embedding model here
        TODO: Implement with sentence-transformers
        """

        # Placeholder - implement later
        embedding_id = hashlib.sha256(
            json.dumps(pattern['reasoning_steps']).encode()
        ).hexdigest()[:16]

        # For now, store dummy embedding
        # Real implementation: use sentence-transformers

        return embedding_id

    # ========================================================================
    # PHASE 2: RETRIEVE PATTERNS (extensible)
    # ========================================================================

    def get_patterns_for_task(
        self,
        task: str,
        task_type: Optional[str] = None,
        limit: int = None
    ) -> List[Dict]:
        """
        Retrieve relevant patterns for a task

        EXTENSION POINT: Override similarity calculation
        """

        limit = limit or self.config.MAX_SIMILAR_PATTERNS

        # Build query
        query = """
            SELECT id, task_type, task_description, reasoning_steps,
                   example_task, example_solution, consensus_score,
                   avg_confidence, success_rate, times_used
            FROM learning.reasoning_patterns
            WHERE expires_at IS NULL OR expires_at > NOW()
        """
        params = []

        if task_type:
            query += " AND task_type = %s"
            params.append(task_type)

        # Order by success rate + usage
        query += " ORDER BY success_rate DESC, times_used DESC LIMIT %s"
        params.append(limit)

        self.cursor.execute(query, params)

        patterns = []
        for row in self.cursor.fetchall():
            patterns.append({
                'id': row[0],
                'task_type': row[1],
                'task_description': row[2],
                'reasoning_steps': row[3],
                'example_task': row[4],
                'example_solution': row[5],
                'consensus_score': row[6],
                'avg_confidence': row[7],
                'success_rate': row[8],
                'times_used': row[9]
            })

        return patterns

    # ========================================================================
    # PHASE 3: APPLY PATTERNS (extensible)
    # ========================================================================

    def pattern_to_prompt(self, pattern: Dict, task: str) -> str:
        """
        Convert pattern to prompt enhancement

        EXTENSION POINT: Override for custom prompt formatting
        """

        steps_text = "\n".join([
            f"{i+1}. {step}"
            for i, step in enumerate(pattern['reasoning_steps'])
        ])

        prompt = f"""Task: {task}

This task is similar to: {pattern['task_type']}

Use this proven reasoning pattern (success rate: {pattern['success_rate']:.1%}):
{steps_text}

Example task:
{pattern['example_task']}

Example solution:
{pattern['example_solution']}

Now solve the given task following the same reasoning pattern.
"""

        return prompt

    def record_pattern_usage(
        self,
        pattern_id: int,
        task_hash: str,
        model: str,
        success: bool,
        execution_time_ms: int,
        quality_score: float,
        feedback: Optional[Dict] = None
    ):
        """Record pattern usage for learning improvement"""

        # Insert usage record
        self.cursor.execute("""
            INSERT INTO learning.pattern_usage
            (pattern_id, task_hash, model_used, success, execution_time_ms,
             quality_score, feedback)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            pattern_id, task_hash, model, success,
            execution_time_ms, quality_score,
            json.dumps(feedback or {})
        ))

        # Update pattern statistics
        self.cursor.execute("""
            UPDATE learning.reasoning_patterns
            SET times_used = times_used + 1,
                times_successful = times_successful + CASE WHEN %s THEN 1 ELSE 0 END,
                success_rate = (times_successful + CASE WHEN %s THEN 1 ELSE 0 END)::FLOAT / (times_used + 1),
                last_used = NOW()
            WHERE id = %s
        """, (success, success, pattern_id))

        self.db.commit()

    # ========================================================================
    # EXTENSION API
    # ========================================================================

    def add_custom_extractor(self, task_type: str, extractor_fn):
        """Add custom pattern extraction for specific task type"""
        self.config.CUSTOM_EXTRACTORS[task_type] = extractor_fn

    def add_custom_validator(self, task_type: str, validator_fn):
        """Add custom validation for specific task type"""
        self.config.CUSTOM_VALIDATORS[task_type] = validator_fn

    # ========================================================================
    # UTILITIES
    # ========================================================================

    def get_statistics(self) -> Dict:
        """Get learner statistics"""

        self.cursor.execute("""
            SELECT
                COUNT(*) as total_patterns,
                COUNT(DISTINCT task_type) as task_types,
                AVG(consensus_score) as avg_consensus,
                AVG(success_rate) as avg_success,
                SUM(times_used) as total_usage
            FROM learning.reasoning_patterns
            WHERE expires_at IS NULL OR expires_at > NOW()
        """)

        row = self.cursor.fetchone()

        return {
            'total_patterns': row[0],
            'task_types_covered': row[1],
            'avg_consensus_score': float(row[2]) if row[2] else 0,
            'avg_success_rate': float(row[3]) if row[3] else 0,
            'total_usage_count': row[4] or 0
        }

    def close(self):
        self.cursor.close()
        self.db.close()


# ============================================================================
# EXAMPLE CUSTOM EXTRACTORS (for iteration)
# ============================================================================

def debugging_pattern_extractor(task, worker_results, metadata):
    """Custom extractor for debugging tasks"""
    # Example: Extract specific debugging steps
    # Can add domain-specific logic here
    pass

def code_generation_pattern_extractor(task, worker_results, metadata):
    """Custom extractor for code generation"""
    # Example: Extract code structure patterns
    pass


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == '__main__':
    learner = OrchestratorReasoningLearner()

    stats = learner.get_statistics()
    print("Reasoning Learner Statistics:")
    print(f"  Total patterns: {stats['total_patterns']}")
    print(f"  Task types: {stats['task_types_covered']}")
    print(f"  Avg consensus: {stats['avg_consensus_score']:.1%}")
    print(f"  Avg success rate: {stats['avg_success_rate']:.1%}")
    print(f"  Total usage: {stats['total_usage_count']}")

    learner.close()
