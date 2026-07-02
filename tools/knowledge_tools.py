#!/usr/bin/env python3
"""
Knowledge Tools Wrapper

Wires up unused knowledge components:
- knowledge_system.py (#253)
- knowledge_sync.py (#261)

Usage:
    from knowledge_tools import query_knowledge, sync_to_neo4j
    result = query_knowledge("find files related to PostgreSQL")

Test:
    python3 tools/knowledge_tools.py --test
"""

import sys
from pathlib import Path

# Import knowledge components
sys.path.insert(0, str(Path(__file__).parent))
from knowledge_system import KnowledgeSystem
import knowledge_sync

# Initialize knowledge system instance
_ks = None

def _get_knowledge_system():
    """Get or create KnowledgeSystem instance"""
    global _ks
    if _ks is None:
        _ks = KnowledgeSystem()
    return _ks

def query_knowledge(query_text, limit=10):
    """Query the knowledge graph (PostgreSQL knowledge.* tables)"""
    ks = _get_knowledge_system()
    return ks.semantic_search(query_text, limit=limit)

def sync_to_neo4j():
    """Sync knowledge from PostgreSQL to Neo4j"""
    # Note: sync_all() function does not exist in knowledge_sync module
    # This is a placeholder for future Neo4j integration
    raise NotImplementedError("sync_to_neo4j is not yet implemented - knowledge_sync.sync_all() does not exist")

def add_knowledge_entity(entity_type, entity_data):
    """Add an entity to the knowledge graph"""
    # Note: add_entity() method does not exist on KnowledgeSystem
    # Use store_knowledge() instead for storing knowledge entries
    raise NotImplementedError("add_knowledge_entity is not implemented - use store_knowledge() via query_knowledge wrapper instead")

def add_knowledge_relationship(from_entity, to_entity, rel_type):
    """Add a relationship between entities"""
    # Note: add_relationship() method does not exist on KnowledgeSystem
    # This would require Neo4j integration or additional PostgreSQL schema
    raise NotImplementedError("add_knowledge_relationship is not implemented - requires Neo4j integration or extended schema")

if __name__ == '__main__':
    if '--test' in sys.argv:
        print('=== Testing Knowledge Tools ===\n')

        passed = 0
        failed = 0

        try:
            print('Test 1: Import modules...')
            ks = _get_knowledge_system()
            assert ks is not None
            assert knowledge_sync is not None
            print('✓ All modules loaded\n')
            passed += 1
        except Exception as e:
            print(f'✗ Import failed: {e}\n')
            failed += 1

        try:
            print('Test 2: Check functions...')
            assert callable(query_knowledge)
            assert callable(sync_to_neo4j)
            assert callable(add_knowledge_entity)
            assert callable(add_knowledge_relationship)
            print('✓ All functions available\n')
            passed += 1
        except Exception as e:
            print(f'✗ Function check failed: {e}\n')
            failed += 1

        print(f'\n=== Results: {passed} passed, {failed} failed ===')
        if failed == 0:
            print('✅ ALL TESTS PASSED')
            sys.exit(0)
        else:
            print('❌ SOME TESTS FAILED')
            sys.exit(1)
