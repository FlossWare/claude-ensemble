#!/usr/bin/env python3
"""
Analogical Reasoning Trainer

Trains a model to:
1. Identify structural patterns across different domains
2. Transfer solutions from source domain to target domain
3. Generate metaphors and analogies
4. Evaluate analogy quality

Uses case-based reasoning + embedding similarity for pattern matching.

Architecture:
- Pattern Extractor: Identifies relational structure
- Similarity Scorer: Measures structural similarity (not surface similarity)
- Transfer Engine: Maps source solution to target domain
- Metaphor Generator: Creates creative analogies

Storage: PostgreSQL + pgvector for fast analogical retrieval
"""

import psycopg2
import numpy as np
import json
import pickle
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import sys

# Add embeddings path
sys.path.insert(0, str(Path.home() / 'Development' / 'redhat' / 'scm' / 'gitlab' / 'cee' / 'sfloess' / 'claude-global-skills' / 'shared'))

try:
    from sentence_transformers import SentenceTransformer
    _embedding_model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')

    def generate_embedding(text):
        """Generate single embedding using sentence-transformers"""
        embeddings = _embedding_model.encode([text], convert_to_numpy=True)
        return embeddings[0]

    EMBEDDINGS_AVAILABLE = True
except ImportError as e:
    EMBEDDINGS_AVAILABLE = False
    print(f"Warning: sentence-transformers not available ({e}), using random embeddings")


def get_db():
    """Connect to PostgreSQL learning database"""
    return psycopg2.connect(
        host='aio-01',
        port=5433,
        user='sfloess',
        database='learning'
    )


class AnalogicalPattern:
    """Represents a structural pattern extracted from a domain"""

    def __init__(self, domain: str, entities: List[str], relations: List[Tuple[str, str, str]],
                 solution: Optional[str] = None, context: str = ""):
        """
        domain: Source domain (e.g., "electrical_circuit", "water_flow", "finance")
        entities: List of entities (e.g., ["battery", "resistor", "wire"])
        relations: List of (entity1, relation, entity2) tuples
        solution: Solution/outcome in this domain
        context: Free-text context description
        """
        self.domain = domain
        self.entities = entities
        self.relations = relations
        self.solution = solution
        self.context = context
        self.embedding = None  # Set later

    def to_dict(self) -> Dict:
        return {
            'domain': self.domain,
            'entities': self.entities,
            'relations': self.relations,
            'solution': self.solution,
            'context': self.context
        }

    def get_structure_text(self) -> str:
        """Get text representation of structure (for embedding)"""
        # Focus on relational structure, not domain-specific terms
        abstract_relations = []
        for e1, rel, e2 in self.relations:
            abstract_relations.append(f"{rel} connects entities")

        return f"Domain structure: {' | '.join(abstract_relations)}. Context: {self.context}"


class AnalogicalReasoning:
    """Main analogical reasoning engine"""

    def __init__(self, embedding_dim: int = 384):
        self.embedding_dim = embedding_dim
        self.patterns: Dict[str, AnalogicalPattern] = {}
        self.pattern_embeddings = {}

    def add_pattern(self, pattern_id: str, pattern: AnalogicalPattern):
        """Add a known pattern to the knowledge base"""
        self.patterns[pattern_id] = pattern

        # Generate embedding from structure
        structure_text = pattern.get_structure_text()
        if EMBEDDINGS_AVAILABLE:
            pattern.embedding = generate_embedding(structure_text)
        else:
            # Random embedding for testing
            pattern.embedding = np.random.randn(self.embedding_dim)

        self.pattern_embeddings[pattern_id] = pattern.embedding

    def find_analogous_patterns(self, target_pattern: AnalogicalPattern, k: int = 5) -> List[Tuple[str, float]]:
        """Find patterns analogous to target (structural similarity)"""
        if not self.patterns:
            return []

        # Generate target embedding
        structure_text = target_pattern.get_structure_text()
        if EMBEDDINGS_AVAILABLE:
            target_embedding = generate_embedding(structure_text)
        else:
            target_embedding = np.random.randn(self.embedding_dim)

        # Compute cosine similarity
        similarities = []
        for pattern_id, pattern_emb in self.pattern_embeddings.items():
            # Skip same domain (we want cross-domain analogies)
            if self.patterns[pattern_id].domain == target_pattern.domain:
                continue

            sim = self._cosine_similarity(target_embedding, pattern_emb)
            similarities.append((pattern_id, sim))

        # Return top-k most similar
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:k]

    def transfer_solution(self, source_pattern_id: str, target_pattern: AnalogicalPattern) -> Dict:
        """Transfer solution from source pattern to target pattern"""
        if source_pattern_id not in self.patterns:
            return {'success': False, 'error': 'Source pattern not found'}

        source = self.patterns[source_pattern_id]

        # Create mapping between entities
        entity_mapping = self._create_entity_mapping(source, target_pattern)

        # Transfer solution by substituting entities
        if source.solution:
            transferred_solution = self._substitute_entities(source.solution, entity_mapping)
        else:
            transferred_solution = "No solution available in source pattern"

        return {
            'success': True,
            'source_domain': source.domain,
            'target_domain': target_pattern.domain,
            'entity_mapping': entity_mapping,
            'original_solution': source.solution,
            'transferred_solution': transferred_solution,
            'confidence': self._calculate_transfer_confidence(source, target_pattern)
        }

    def generate_metaphor(self, concept: str, target_domain: str) -> str:
        """Generate a metaphor mapping concept to target domain"""
        # Find pattern related to concept
        concept_pattern = AnalogicalPattern(
            domain='abstract',
            entities=[concept],
            relations=[],
            context=concept
        )

        analogies = self.find_analogous_patterns(concept_pattern, k=3)

        if not analogies:
            return f"{concept} (no metaphor found)"

        # Get best analogy
        best_id, best_score = analogies[0]
        best_pattern = self.patterns[best_id]

        # Generate metaphor
        metaphor = f"{concept} is like {best_pattern.domain}: {best_pattern.context}"

        return metaphor

    def evaluate_analogy(self, source_id: str, target_id: str) -> Dict:
        """Evaluate quality of analogy between two patterns"""
        if source_id not in self.patterns or target_id not in self.patterns:
            return {'valid': False, 'error': 'Pattern not found'}

        source = self.patterns[source_id]
        target = self.patterns[target_id]

        # Structural similarity
        structural_sim = self._cosine_similarity(
            self.pattern_embeddings[source_id],
            self.pattern_embeddings[target_id]
        )

        # Relation overlap
        relation_overlap = self._compute_relation_overlap(source, target)

        # Entity count similarity
        entity_ratio = min(len(source.entities), len(target.entities)) / max(len(source.entities), len(target.entities))

        # Overall quality score
        quality = 0.5 * structural_sim + 0.3 * relation_overlap + 0.2 * entity_ratio

        return {
            'valid': True,
            'quality_score': quality,
            'structural_similarity': structural_sim,
            'relation_overlap': relation_overlap,
            'entity_ratio': entity_ratio,
            'interpretation': self._interpret_quality(quality)
        }

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors"""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def _create_entity_mapping(self, source: AnalogicalPattern, target: AnalogicalPattern) -> Dict[str, str]:
        """Create mapping between source and target entities"""
        # Simple heuristic: map by position
        mapping = {}
        for i, (src_ent, tgt_ent) in enumerate(zip(source.entities, target.entities)):
            mapping[src_ent] = tgt_ent
        return mapping

    def _substitute_entities(self, solution: str, mapping: Dict[str, str]) -> str:
        """Substitute entities in solution text"""
        result = solution
        for src, tgt in mapping.items():
            result = result.replace(src, tgt)
        return result

    def _calculate_transfer_confidence(self, source: AnalogicalPattern, target: AnalogicalPattern) -> float:
        """Calculate confidence in solution transfer"""
        # Higher confidence if more structural similarity
        if not self.pattern_embeddings:
            return 0.5

        src_id = [k for k, v in self.patterns.items() if v == source][0]
        src_emb = self.pattern_embeddings[src_id]

        tgt_structure = target.get_structure_text()
        if EMBEDDINGS_AVAILABLE:
            tgt_emb = generate_embedding(tgt_structure)
        else:
            tgt_emb = np.random.randn(self.embedding_dim)

        return self._cosine_similarity(src_emb, tgt_emb)

    def _compute_relation_overlap(self, source: AnalogicalPattern, target: AnalogicalPattern) -> float:
        """Compute overlap in relation types"""
        src_rels = set([r[1] for r in source.relations])  # Extract relation types
        tgt_rels = set([r[1] for r in target.relations])

        if not src_rels or not tgt_rels:
            return 0.0

        overlap = len(src_rels & tgt_rels)
        total = len(src_rels | tgt_rels)

        return overlap / total if total > 0 else 0.0

    def _interpret_quality(self, quality: float) -> str:
        """Interpret quality score"""
        if quality > 0.8:
            return "Excellent analogy - strong structural mapping"
        elif quality > 0.6:
            return "Good analogy - clear structural similarities"
        elif quality > 0.4:
            return "Moderate analogy - some similarities"
        else:
            return "Weak analogy - limited structural overlap"

    def save(self, filepath: str):
        """Save model to disk"""
        state = {
            'embedding_dim': self.embedding_dim,
            'patterns': {k: v.to_dict() for k, v in self.patterns.items()},
            'pattern_embeddings': {k: v.tolist() for k, v in self.pattern_embeddings.items()}
        }

        with open(filepath, 'wb') as f:
            pickle.dump(state, f)

    @classmethod
    def load(cls, filepath: str):
        """Load model from disk"""
        with open(filepath, 'rb') as f:
            state = pickle.load(f)

        model = cls(embedding_dim=state['embedding_dim'])

        # Restore patterns
        for pattern_id, pattern_dict in state['patterns'].items():
            pattern = AnalogicalPattern(
                domain=pattern_dict['domain'],
                entities=pattern_dict['entities'],
                relations=pattern_dict['relations'],
                solution=pattern_dict.get('solution'),
                context=pattern_dict.get('context', '')
            )
            model.patterns[pattern_id] = pattern

        # Restore embeddings
        model.pattern_embeddings = {k: np.array(v) for k, v in state['pattern_embeddings'].items()}

        return model


def create_training_examples() -> List[Tuple[str, AnalogicalPattern]]:
    """Create example patterns for training"""
    examples = []

    # Example 1: Electrical circuit
    examples.append(('circuit_1', AnalogicalPattern(
        domain='electrical_circuit',
        entities=['battery', 'resistor', 'wire'],
        relations=[
            ('battery', 'powers', 'wire'),
            ('wire', 'connects', 'resistor'),
            ('resistor', 'limits', 'current')
        ],
        solution='Increase voltage to increase current flow',
        context='Ohms law: voltage drives current through resistance'
    )))

    # Example 2: Water flow (analogous to circuit)
    examples.append(('water_1', AnalogicalPattern(
        domain='water_flow',
        entities=['pump', 'valve', 'pipe'],
        relations=[
            ('pump', 'powers', 'pipe'),
            ('pipe', 'connects', 'valve'),
            ('valve', 'limits', 'flow')
        ],
        solution='Increase pressure to increase water flow',
        context='Pressure drives flow through restrictions'
    )))

    # Example 3: Finance flow
    examples.append(('finance_1', AnalogicalPattern(
        domain='finance',
        entities=['investment', 'fees', 'account'],
        relations=[
            ('investment', 'powers', 'account'),
            ('account', 'connects', 'fees'),
            ('fees', 'limits', 'returns')
        ],
        solution='Increase capital to increase returns',
        context='Capital drives returns through fees'
    )))

    # Example 4: Heat transfer
    examples.append(('heat_1', AnalogicalPattern(
        domain='heat_transfer',
        entities=['furnace', 'insulation', 'room'],
        relations=[
            ('furnace', 'powers', 'room'),
            ('room', 'connects', 'insulation'),
            ('insulation', 'limits', 'heat_loss')
        ],
        solution='Increase temperature to increase heat flow',
        context='Temperature drives heat through resistance'
    )))

    # Example 5: Team management (abstract)
    examples.append(('management_1', AnalogicalPattern(
        domain='team_management',
        entities=['leader', 'bureaucracy', 'team'],
        relations=[
            ('leader', 'powers', 'team'),
            ('team', 'connects', 'bureaucracy'),
            ('bureaucracy', 'limits', 'productivity')
        ],
        solution='Increase motivation to increase output',
        context='Leadership drives productivity through organizational friction'
    )))

    # Example 6: Software architecture
    examples.append(('software_1', AnalogicalPattern(
        domain='software',
        entities=['server', 'middleware', 'client'],
        relations=[
            ('server', 'powers', 'client'),
            ('client', 'connects', 'middleware'),
            ('middleware', 'limits', 'throughput')
        ],
        solution='Increase resources to increase throughput',
        context='Server capacity drives throughput through middleware overhead'
    )))

    return examples


def train_analogical_reasoning():
    """Train analogical reasoning model from examples"""
    print("=== Analogical Reasoning Trainer ===\n")

    # Create model
    model = AnalogicalReasoning(embedding_dim=384)

    # Load training examples
    examples = create_training_examples()
    print(f"Training examples: {len(examples)}")

    # Add patterns
    for pattern_id, pattern in examples:
        model.add_pattern(pattern_id, pattern)
        print(f"  Added: {pattern_id} ({pattern.domain})")

    print("\n=== Testing Analogical Retrieval ===")

    # Test 1: Find analogies for a new electrical problem
    test_pattern = AnalogicalPattern(
        domain='electrical_circuit',
        entities=['generator', 'capacitor', 'load'],
        relations=[
            ('generator', 'powers', 'load'),
            ('load', 'connects', 'capacitor'),
            ('capacitor', 'limits', 'voltage_spike')
        ],
        context='How to smooth voltage fluctuations'
    )

    analogies = model.find_analogous_patterns(test_pattern, k=3)
    print("\nTest 1: Find analogies for voltage smoothing problem")
    for pattern_id, score in analogies:
        pattern = model.patterns[pattern_id]
        print(f"  {pattern_id} ({pattern.domain}): {score:.3f}")

    # Test 2: Transfer solution
    if analogies:
        best_id = analogies[0][0]
        transfer = model.transfer_solution(best_id, test_pattern)
        print(f"\nTest 2: Transfer solution from {transfer['source_domain']}")
        print(f"  Original: {transfer['original_solution']}")
        print(f"  Transferred: {transfer['transferred_solution']}")
        print(f"  Confidence: {transfer['confidence']:.3f}")

    # Test 3: Generate metaphor
    metaphor = model.generate_metaphor('leadership', 'water_flow')
    print(f"\nTest 3: Generate metaphor")
    print(f"  {metaphor}")

    # Test 4: Evaluate analogy quality
    if len(model.patterns) >= 2:
        ids = list(model.patterns.keys())
        eval_result = model.evaluate_analogy(ids[0], ids[1])
        print(f"\nTest 4: Evaluate analogy quality ({ids[0]} <-> {ids[1]})")
        print(f"  Quality: {eval_result['quality_score']:.3f}")
        print(f"  Interpretation: {eval_result['interpretation']}")

    # Save model
    model_path = '/home/sfloess/.claude/learning/analogical_reasoning.pkl'
    model.save(model_path)
    print(f"\n✅ Model saved: {model_path}")

    # Save stats
    stats = {
        'num_patterns': len(model.patterns),
        'domains': list(set([p.domain for p in model.patterns.values()])),
        'embedding_dim': model.embedding_dim,
        'trained_at': datetime.now().isoformat()
    }

    stats_path = '/home/sfloess/.claude/learning/analogical_reasoning_stats.json'
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"✅ Stats saved: {stats_path}")

    # Store in PostgreSQL
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning.analogical_patterns (
            pattern_id VARCHAR PRIMARY KEY,
            domain VARCHAR,
            entities JSONB,
            relations JSONB,
            solution TEXT,
            context TEXT,
            embedding vector(1024),
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Insert patterns
    for pattern_id, pattern in model.patterns.items():
        embedding_list = model.pattern_embeddings[pattern_id].tolist()

        cursor.execute("""
            INSERT INTO learning.analogical_patterns
            (pattern_id, domain, entities, relations, solution, context, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (pattern_id) DO UPDATE SET
                solution = EXCLUDED.solution,
                context = EXCLUDED.context
        """, (
            pattern_id,
            pattern.domain,
            json.dumps(pattern.entities),
            json.dumps(pattern.relations),
            pattern.solution,
            pattern.context,
            embedding_list
        ))

    db.commit()
    cursor.close()
    db.close()

    print("✅ Patterns stored in PostgreSQL")

    return model, stats


if __name__ == '__main__':
    model, stats = train_analogical_reasoning()

    print(f"\n=== Training Complete ===")
    print(f"Patterns trained: {stats['num_patterns']}")
    print(f"Domains covered: {', '.join(stats['domains'])}")
    print(f"\nTo use in code:")
    print(f"  from analogical_reasoning_trainer import AnalogicalReasoning")
    print(f"  model = AnalogicalReasoning.load('/home/sfloess/.claude/learning/analogical_reasoning.pkl')")
    print(f"  analogies = model.find_analogous_patterns(target_pattern)")
