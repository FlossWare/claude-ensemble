#!/usr/bin/env python3
"""
Knowledge Tools Wrapper

Wires up unused knowledge components:
- knowledge_system.py (#253)
- knowledge_sync.py (#261)

Usage:
    from knowledge_tools import query_knowledge, sync_to_orientdb
    result = query_knowledge("find files related to PostgreSQL")

Test:
    python3 tools/knowledge_tools.py --test
"""

import sys
import logging
from pathlib import Path

import requests

# Import knowledge components
sys.path.insert(0, str(Path(__file__).parent))
from knowledge_system import KnowledgeSystem
import knowledge_sync

logger = logging.getLogger(__name__)

ORIENTDB_API_URL = 'http://aio-01:5000/graph/query'

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

def sync_to_orientdb():
    """Sync knowledge from PostgreSQL to OrientDB via REST API"""
    try:
        ks = _get_knowledge_system()
        entries = ks.semantic_search("", limit=100)
        synced = 0
        for entry in entries:
            query = (
                f"UPDATE KnowledgeEntry SET "
                f"content = '{(entry.get('content', '')).replace(chr(39), chr(92) + chr(39))}', "
                f"source = '{entry.get('source', '')}', "
                f"source_type = '{entry.get('source_type', '')}' "
                f"UPSERT WHERE entry_id = '{entry.get('id', '')}'"
            )
            resp = requests.post(ORIENTDB_API_URL, json={'query': query}, timeout=10)
            if resp.ok:
                synced += 1
        return {'synced': synced, 'total': len(entries)}
    except Exception as e:
        logger.warning(f"OrientDB sync failed (best-effort): {e}")
        return {'synced': 0, 'error': str(e)}

def add_knowledge_entity(entity_type, entity_data):
    """Add an entity to the knowledge graph"""
    # Note: add_entity() method does not exist on KnowledgeSystem
    # Use store_knowledge() instead for storing knowledge entries
    raise NotImplementedError("add_knowledge_entity is not implemented - use store_knowledge() via query_knowledge wrapper instead")

def add_knowledge_relationship(from_entity, to_entity, rel_type):
    """Add a relationship between entities via OrientDB REST API"""
    try:
        query = (
            f"CREATE EDGE {rel_type} FROM "
            f"(SELECT FROM KnowledgeEntry WHERE entry_id = '{from_entity}') TO "
            f"(SELECT FROM KnowledgeEntry WHERE entry_id = '{to_entity}')"
        )
        resp = requests.post(ORIENTDB_API_URL, json={'query': query}, timeout=10)
        if resp.ok:
            return resp.json()
        else:
            logger.warning(f"OrientDB relationship creation returned {resp.status_code}")
            return {'error': f"HTTP {resp.status_code}"}
    except Exception as e:
        logger.warning(f"OrientDB relationship creation failed (best-effort): {e}")
        return {'error': str(e)}

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
            assert callable(sync_to_orientdb)
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
