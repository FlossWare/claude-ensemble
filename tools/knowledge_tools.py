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
import knowledge_system
import knowledge_sync

def query_knowledge(query_text, limit=10):
    """Query the knowledge graph (PostgreSQL knowledge.* tables)"""
    return knowledge_system.query(query_text, limit=limit)

def sync_to_neo4j():
    """Sync knowledge from PostgreSQL to Neo4j"""
    return knowledge_sync.sync_all()

def add_knowledge_entity(entity_type, entity_data):
    """Add an entity to the knowledge graph"""
    return knowledge_system.add_entity(entity_type, entity_data)

def add_knowledge_relationship(from_entity, to_entity, rel_type):
    """Add a relationship between entities"""
    return knowledge_system.add_relationship(from_entity, to_entity, rel_type)

if __name__ == '__main__':
    if '--test' in sys.argv:
        print('=== Testing Knowledge Tools ===\n')

        passed = 0
        failed = 0

        try:
            print('Test 1: Import modules...')
            assert knowledge_system is not None
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
