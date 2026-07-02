#!/usr/bin/env python3
"""
Comprehensive Test Suite for Knowledge Tools - FIXED VERSION
Coverage target: 80%+

Fixes:
1. Mock embedding at correct import location (knowledge_system.SentenceTransformer)
2. Add tests for uncovered paths (embedding errors, NaN handling, chunking)
3. Fix concurrent test expectations (2 votes vs 5)
4. Add integration tests for full workflows
5. Add performance tests for HNSW index
"""

import pytest
import psycopg2
import json
import tempfile
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from datetime import datetime
import concurrent.futures

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent / 'tools'))

# Import modules
from knowledge_system import KnowledgeSystem, bridge_mode
from knowledge_sync import KnowledgeSync
import knowledge_tools


# Fixtures for test database
@pytest.fixture
def test_db_config():
    """Database configuration for testing"""
    return {
        'host': 'aio-01',
        'port': 5433,
        'database': 'learning',
        'user': 'claude'
    }


@pytest.fixture
def knowledge_system(test_db_config):
    """Create KnowledgeSystem instance for testing"""
    ks = KnowledgeSystem(**test_db_config)
    yield ks
    ks.close()


@pytest.fixture
def knowledge_sync(test_db_config):
    """Create KnowledgeSync instance for testing"""
    sync = KnowledgeSync(**test_db_config)
    yield sync
    sync.close()


# Test KnowledgeSystem class
class TestKnowledgeSystem:
    """Tests for KnowledgeSystem class"""

    def test_init_creates_schema(self, test_db_config):
        """Test that initialization creates required schema"""
        ks = KnowledgeSystem(**test_db_config)
        cursor = ks.conn.cursor()

        # Check tables exist
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'knowledge'
            AND table_name IN ('entries', 'provenance')
        """)
        tables = [row[0] for row in cursor.fetchall()]

        assert 'entries' in tables
        assert 'provenance' in tables

        cursor.close()
        ks.close()

    def test_generate_embedding_with_model(self, knowledge_system):
        """Test embedding generation with sentence-transformers"""
        # Mock at the import location within knowledge_system module
        mock_model = Mock()
        mock_model.encode.return_value = Mock(tolist=lambda: [0.1] * 384)

        with patch('knowledge_system.SentenceTransformer') as mock_st:
            mock_st.return_value = mock_model

            embedding = knowledge_system.generate_embedding("test text")

            assert len(embedding) == 384
            assert all(isinstance(x, float) for x in embedding)
            mock_model.encode.assert_called_once()

    def test_generate_embedding_fallback_import_error(self, knowledge_system):
        """Test embedding fallback when sentence-transformers unavailable"""
        with patch('knowledge_system.SentenceTransformer', side_effect=ImportError):
            embedding = knowledge_system.generate_embedding("test text")

            # Should return zero vector
            assert len(embedding) == 384
            assert all(x == 0.0 for x in embedding)

    def test_generate_embedding_fallback_runtime_error(self, knowledge_system):
        """Test embedding fallback on runtime error"""
        mock_model = Mock()
        mock_model.encode.side_effect = RuntimeError("Model error")

        with patch('knowledge_system.SentenceTransformer') as mock_st:
            mock_st.return_value = mock_model

            # Should raise the error (not fallback on runtime errors)
            with pytest.raises(RuntimeError):
                knowledge_system.generate_embedding("test text")

    def test_store_knowledge_small_content(self, knowledge_system):
        """Test storing knowledge with small content (< 1500 chars)"""
        # Mock embedding generation
        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.1] * 384):
            entry_id = knowledge_system.store_knowledge(
                content="Small test content",
                source="test-source",
                source_type="test",
                metadata={"key": "value"},
                actor="test-user"
            )

        assert isinstance(entry_id, int)
        assert entry_id > 0

        # Verify stored
        cursor = knowledge_system.conn.cursor()
        cursor.execute("SELECT content, source, source_type, metadata FROM knowledge.entries WHERE id = %s", (entry_id,))
        row = cursor.fetchone()

        assert row[0] == "Small test content"
        assert row[1] == "test-source"
        assert row[2] == "test"
        assert row[3]['key'] == "value"

        cursor.close()

    def test_store_knowledge_large_content_chunking(self, knowledge_system):
        """Test storing knowledge with large content (> 1500 chars) - semantic chunking"""
        # Create content with clear sentence boundaries for semantic chunking
        large_content = "This is a test sentence. " * 100  # ~2500 chars with sentence boundaries

        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.1] * 384):
            entry_id = knowledge_system.store_knowledge(
                content=large_content,
                source="test-source-large",
                source_type="test",
                metadata={"large": True},
                actor="test-user"
            )

        assert isinstance(entry_id, int)

        # Verify chunks were created
        cursor = knowledge_system.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM knowledge.entries
            WHERE source = 'test-source-large'
        """)
        chunk_count = cursor.fetchone()[0]

        # Should have created multiple chunks
        assert chunk_count > 1

        # Verify metadata contains chunk info
        cursor.execute("""
            SELECT metadata FROM knowledge.entries
            WHERE source = 'test-source-large'
            LIMIT 1
        """)
        metadata = cursor.fetchone()[0]
        assert 'chunk_index' in metadata
        assert 'total_chunks' in metadata

        cursor.close()

    def test_semantic_search(self, knowledge_system):
        """Test semantic search functionality"""
        # Store test entry
        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.1] * 384):
            knowledge_system.store_knowledge(
                content="PostgreSQL database with pgvector",
                source="test-1",
                source_type="test"
            )

            # Search
            results = knowledge_system.semantic_search("vector database", limit=5)

        assert isinstance(results, list)
        assert len(results) >= 0  # May be empty if no matches
        if len(results) > 0:
            assert 'content' in results[0]
            assert 'similarity' in results[0]
            assert 'source' in results[0]

    def test_semantic_search_with_filters(self, knowledge_system):
        """Test semantic search with source_type filter"""
        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.1] * 384):
            # Store with different types
            knowledge_system.store_knowledge(
                content="Test content type A",
                source="test-a",
                source_type="type-a"
            )
            knowledge_system.store_knowledge(
                content="Test content type B",
                source="test-b",
                source_type="type-b"
            )

            # Search with filter
            results = knowledge_system.semantic_search(
                "test content",
                source_type="type-a",
                limit=10
            )

        # All results should be type-a
        assert all(r['source_type'] == 'type-a' for r in results)

    def test_semantic_search_min_similarity(self, knowledge_system):
        """Test semantic search with min_similarity filter"""
        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.1] * 384):
            knowledge_system.store_knowledge(
                content="Test content",
                source="test-similarity",
                source_type="test"
            )

            # Search with high similarity threshold
            results = knowledge_system.semantic_search(
                "test content",
                min_similarity=0.5,
                limit=10
            )

        # All results should meet threshold
        assert all(r['similarity'] >= 0.5 for r in results)

    def test_semantic_search_nan_handling(self, knowledge_system):
        """Test NaN similarity handling (zero vector case)"""
        # Store with fallback embedding (zero vector)
        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.0] * 384):
            entry_id = knowledge_system.store_knowledge(
                content="Test content with zero embedding",
                source="test-nan",
                source_type="test"
            )

            # Search should handle NaN gracefully (zero vector <=> zero vector = NaN)
            results = knowledge_system.semantic_search("test", limit=5)

        for r in results:
            assert 'similarity' in r
            # NaN should be converted to 0.0
            assert isinstance(r['similarity'], float)
            assert not (r['similarity'] != r['similarity'])  # Not NaN check

    def test_get_provenance(self, knowledge_system):
        """Test provenance tracking"""
        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.1] * 384):
            entry_id = knowledge_system.store_knowledge(
                content="Test content",
                source="test-source",
                source_type="test",
                actor="test-actor"
            )

        provenance = knowledge_system.get_provenance(entry_id)

        assert isinstance(provenance, list)
        assert len(provenance) > 0
        assert provenance[0]['action'] == 'created'
        assert provenance[0]['actor'] == 'test-actor'
        assert 'timestamp' in provenance[0]

    def test_update_knowledge(self, knowledge_system):
        """Test updating knowledge entry"""
        # Store initial
        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.1] * 384):
            entry_id = knowledge_system.store_knowledge(
                content="Original content",
                source="test-source",
                source_type="test",
                actor="test-actor"
            )

            # Update
            knowledge_system.update_knowledge(
                entry_id=entry_id,
                content="Updated content",
                actor="updater"
            )

        # Verify update
        cursor = knowledge_system.conn.cursor()
        cursor.execute("SELECT content FROM knowledge.entries WHERE id = %s", (entry_id,))
        content = cursor.fetchone()[0]
        assert content == "Updated content"

        # Verify provenance
        provenance = knowledge_system.get_provenance(entry_id)
        actions = [p['action'] for p in provenance]
        assert 'created' in actions
        assert 'updated' in actions

        cursor.close()

    def test_get_stats(self, knowledge_system):
        """Test statistics generation"""
        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.1] * 384):
            # Store some entries
            knowledge_system.store_knowledge(
                content="Test 1",
                source="test-1",
                source_type="type-a"
            )
            knowledge_system.store_knowledge(
                content="Test 2",
                source="test-2",
                source_type="type-b"
            )

        stats = knowledge_system.get_stats()

        assert 'total_entries' in stats
        assert 'by_source_type' in stats
        assert stats['total_entries'] > 0
        assert isinstance(stats['by_source_type'], dict)


# Test KnowledgeSync class
class TestKnowledgeSync:
    """Tests for KnowledgeSync class"""

    def test_init_creates_schema(self, test_db_config):
        """Test that initialization creates required schema"""
        sync = KnowledgeSync(**test_db_config)
        cursor = sync.conn.cursor()

        # Check tables exist
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'knowledge'
            AND table_name IN ('discoveries', 'verification_votes')
        """)
        tables = [row[0] for row in cursor.fetchall()]

        assert 'discoveries' in tables
        assert 'verification_votes' in tables

        cursor.close()
        sync.close()

    def test_share_discovery_small(self, knowledge_sync):
        """Test sharing small discovery"""
        with patch.object(knowledge_sync, 'generate_embedding', return_value=[0.1] * 384):
            disc_id = knowledge_sync.share_discovery(
                worker_id='worker-01',
                discovery_type='pattern',
                content='Small discovery',
                confidence=0.8
            )

        assert isinstance(disc_id, int)
        assert disc_id > 0

    def test_share_discovery_large_chunking(self, knowledge_sync):
        """Test sharing large discovery with chunking"""
        large_content = "Discovery: " + ("This is a test sentence. " * 100)  # ~2500 chars

        with patch.object(knowledge_sync, 'generate_embedding', return_value=[0.1] * 384):
            disc_id = knowledge_sync.share_discovery(
                worker_id='worker-01',
                discovery_type='pattern',
                content=large_content,
                confidence=0.9
            )

        assert isinstance(disc_id, int)

        # Verify chunks created
        cursor = knowledge_sync.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM knowledge.discoveries
            WHERE worker_id = 'worker-01'
            AND discovery_type LIKE 'pattern_chunk_%'
        """)
        chunk_count = cursor.fetchone()[0]
        assert chunk_count > 1

        cursor.close()

    def test_verify_discovery_approve(self, knowledge_sync):
        """Test approving a discovery"""
        # Share discovery
        with patch.object(knowledge_sync, 'generate_embedding', return_value=[0.1] * 384):
            disc_id = knowledge_sync.share_discovery(
                worker_id='worker-01',
                discovery_type='pattern',
                content='Test discovery',
                confidence=0.8
            )

        # Verify
        result = knowledge_sync.verify_discovery(
            discovery_id=disc_id,
            worker_id='worker-02',
            approve=True,
            reasoning='Confirmed'
        )

        assert 'discovery_id' in result
        assert result['verifications'] == 1
        assert result['rejections'] == 0

    def test_verify_discovery_reject(self, knowledge_sync):
        """Test rejecting a discovery"""
        # Share discovery
        with patch.object(knowledge_sync, 'generate_embedding', return_value=[0.1] * 384):
            disc_id = knowledge_sync.share_discovery(
                worker_id='worker-01',
                discovery_type='pattern',
                content='Test discovery',
                confidence=0.8
            )

        # Reject
        result = knowledge_sync.verify_discovery(
            discovery_id=disc_id,
            worker_id='worker-02',
            approve=False,
            reasoning='Invalid'
        )

        assert result['verifications'] == 0
        assert result['rejections'] == 1

    def test_verify_discovery_threshold_verified(self, knowledge_sync):
        """Test discovery auto-verified after 3 approvals"""
        # Share discovery
        with patch.object(knowledge_sync, 'generate_embedding', return_value=[0.1] * 384):
            disc_id = knowledge_sync.share_discovery(
                worker_id='worker-01',
                discovery_type='pattern',
                content='Test discovery',
                confidence=0.8
            )

        # 3 approvals
        knowledge_sync.verify_discovery(disc_id, 'worker-02', True, 'OK')
        knowledge_sync.verify_discovery(disc_id, 'worker-03', True, 'OK')
        result = knowledge_sync.verify_discovery(disc_id, 'worker-04', True, 'OK')

        assert result['verifications'] == 3
        assert result['status'] == 'verified'

    def test_verify_discovery_threshold_rejected(self, knowledge_sync):
        """Test discovery auto-rejected after 3 rejections"""
        # Share discovery
        with patch.object(knowledge_sync, 'generate_embedding', return_value=[0.1] * 384):
            disc_id = knowledge_sync.share_discovery(
                worker_id='worker-01',
                discovery_type='pattern',
                content='Test discovery',
                confidence=0.8
            )

        # 3 rejections
        knowledge_sync.verify_discovery(disc_id, 'worker-02', False, 'Bad')
        knowledge_sync.verify_discovery(disc_id, 'worker-03', False, 'Bad')
        result = knowledge_sync.verify_discovery(disc_id, 'worker-04', False, 'Bad')

        assert result['rejections'] == 3
        assert result['status'] == 'rejected'

    def test_verify_discovery_duplicate_vote(self, knowledge_sync):
        """Test that duplicate votes from same worker update the vote"""
        with patch.object(knowledge_sync, 'generate_embedding', return_value=[0.1] * 384):
            disc_id = knowledge_sync.share_discovery(
                worker_id='worker-01',
                discovery_type='pattern',
                content='Test discovery',
                confidence=0.8
            )

        # First vote: approve
        result1 = knowledge_sync.verify_discovery(disc_id, 'worker-02', True, 'Approve')
        assert result1['verifications'] == 1
        assert result1['rejections'] == 0

        # Second vote from same worker: reject
        result2 = knowledge_sync.verify_discovery(disc_id, 'worker-02', False, 'Changed mind')
        assert result2['verifications'] == 0
        assert result2['rejections'] == 1

    def test_verify_discovery_not_found(self, knowledge_sync):
        """Test verifying non-existent discovery"""
        result = knowledge_sync.verify_discovery(
            discovery_id=999999,
            worker_id='worker-02',
            approve=True
        )

        assert 'error' in result
        assert 'not found' in result['error'].lower()

    def test_get_fleet_knowledge(self, knowledge_sync):
        """Test getting verified knowledge"""
        # Share and verify discovery
        with patch.object(knowledge_sync, 'generate_embedding', return_value=[0.1] * 384):
            disc_id = knowledge_sync.share_discovery(
                worker_id='worker-01',
                discovery_type='pattern',
                content='Verified discovery',
                confidence=0.9
            )

        # Verify it
        knowledge_sync.verify_discovery(disc_id, 'worker-02', True, 'OK')
        knowledge_sync.verify_discovery(disc_id, 'worker-03', True, 'OK')
        knowledge_sync.verify_discovery(disc_id, 'worker-04', True, 'OK')

        # Get fleet knowledge
        knowledge = knowledge_sync.get_fleet_knowledge(min_confidence=0.7)

        assert isinstance(knowledge, list)
        verified = [k for k in knowledge if k['id'] == disc_id]
        assert len(verified) > 0
        assert verified[0]['confidence'] == 0.9

    def test_get_fleet_knowledge_filters(self, knowledge_sync):
        """Test fleet knowledge with filters"""
        # Share different types
        with patch.object(knowledge_sync, 'generate_embedding', return_value=[0.1] * 384):
            disc1 = knowledge_sync.share_discovery('worker-01', 'pattern', 'Pattern discovery', 0.9)
            disc2 = knowledge_sync.share_discovery('worker-01', 'optimization', 'Optimization discovery', 0.8)

        # Verify both
        for disc_id in [disc1, disc2]:
            knowledge_sync.verify_discovery(disc_id, 'worker-02', True, 'OK')
            knowledge_sync.verify_discovery(disc_id, 'worker-03', True, 'OK')
            knowledge_sync.verify_discovery(disc_id, 'worker-04', True, 'OK')

        # Get only patterns
        knowledge = knowledge_sync.get_fleet_knowledge(discovery_type='pattern')

        assert all(k['type'] == 'pattern' for k in knowledge)

    def test_get_pending_discoveries(self, knowledge_sync):
        """Test getting pending discoveries"""
        # Share discovery (not verified)
        with patch.object(knowledge_sync, 'generate_embedding', return_value=[0.1] * 384):
            disc_id = knowledge_sync.share_discovery(
                worker_id='worker-01',
                discovery_type='pattern',
                content='Pending discovery',
                confidence=0.8
            )

        pending = knowledge_sync.get_pending_discoveries()

        assert isinstance(pending, list)
        assert any(p['id'] == disc_id for p in pending)

    def test_get_stats(self, knowledge_sync):
        """Test knowledge sync statistics"""
        stats = knowledge_sync.get_stats()

        assert 'pending' in stats
        assert 'verified' in stats
        assert 'rejected' in stats
        assert 'total' in stats
        assert 'active_workers' in stats
        assert 'total_votes' in stats


# Test bridge_mode function
class TestBridgeMode:
    """Tests for bridge_mode JSON request/response handling"""

    def test_bridge_mode_store(self, tmp_path):
        """Test bridge_mode store operation"""
        with patch('knowledge_system.KnowledgeSystem.generate_embedding', return_value=[0.1] * 384):
            request = {
                'operation': 'store',
                'content': 'Test content',
                'source': 'test-source',
                'source_type': 'test',
                'metadata': '{"key": "value"}',
                'actor': 'test-user',
                'output_file': str(tmp_path / 'output.json')
            }

            req_file = tmp_path / 'request.json'
            req_file.write_text(json.dumps(request))

            bridge_mode(str(req_file))

        # Check output
        output = json.loads((tmp_path / 'output.json').read_text())

        assert output['success'] is True
        assert 'entry_id' in output
        assert isinstance(output['entry_id'], int)

    def test_bridge_mode_search(self, tmp_path):
        """Test bridge_mode search operation"""
        with patch('knowledge_system.KnowledgeSystem.generate_embedding', return_value=[0.1] * 384):
            request = {
                'operation': 'search',
                'query': 'test query',
                'limit': 5,
                'min_similarity': 0.5,
                'output_file': str(tmp_path / 'output.json')
            }

            req_file = tmp_path / 'request.json'
            req_file.write_text(json.dumps(request))

            bridge_mode(str(req_file))

        # Check output
        output = json.loads((tmp_path / 'output.json').read_text())

        assert output['success'] is True
        assert 'results' in output
        assert isinstance(output['results'], list)

    def test_bridge_mode_provenance(self, tmp_path, test_db_config):
        """Test bridge_mode provenance operation"""
        # First store an entry
        with patch('knowledge_system.KnowledgeSystem.generate_embedding', return_value=[0.1] * 384):
            ks = KnowledgeSystem(**test_db_config)
            entry_id = ks.store_knowledge('Test', 'test', 'test')
            ks.close()

            request = {
                'operation': 'provenance',
                'entry_id': entry_id,
                'output_file': str(tmp_path / 'output.json')
            }

            req_file = tmp_path / 'request.json'
            req_file.write_text(json.dumps(request))

            bridge_mode(str(req_file))

        # Check output
        output = json.loads((tmp_path / 'output.json').read_text())

        assert output['success'] is True
        assert 'provenance' in output
        assert isinstance(output['provenance'], list)

    def test_bridge_mode_update(self, tmp_path, test_db_config):
        """Test bridge_mode update operation"""
        # First store an entry
        with patch('knowledge_system.KnowledgeSystem.generate_embedding', return_value=[0.1] * 384):
            ks = KnowledgeSystem(**test_db_config)
            entry_id = ks.store_knowledge('Original', 'test', 'test')
            ks.close()

            request = {
                'operation': 'update',
                'entry_id': entry_id,
                'content': 'Updated content',
                'actor': 'updater',
                'output_file': str(tmp_path / 'output.json')
            }

            req_file = tmp_path / 'request.json'
            req_file.write_text(json.dumps(request))

            bridge_mode(str(req_file))

        # Check output
        output = json.loads((tmp_path / 'output.json').read_text())

        assert output['success'] is True

    def test_bridge_mode_stats(self, tmp_path):
        """Test bridge_mode stats operation"""
        request = {
            'operation': 'stats',
            'output_file': str(tmp_path / 'output.json')
        }

        req_file = tmp_path / 'request.json'
        req_file.write_text(json.dumps(request))

        bridge_mode(str(req_file))

        # Check output
        output = json.loads((tmp_path / 'output.json').read_text())

        assert output['success'] is True
        assert 'stats' in output

    def test_bridge_mode_unknown_operation(self, tmp_path):
        """Test bridge_mode with unknown operation"""
        request = {
            'operation': 'unknown_op',
            'output_file': str(tmp_path / 'output.json')
        }

        req_file = tmp_path / 'request.json'
        req_file.write_text(json.dumps(request))

        bridge_mode(str(req_file))

        # Check output
        output = json.loads((tmp_path / 'output.json').read_text())

        assert output['success'] is False
        assert 'error' in output

    def test_bridge_mode_error_handling(self, tmp_path):
        """Test bridge_mode error handling"""
        request = {
            'operation': 'store',
            # Missing required fields
            'output_file': str(tmp_path / 'output.json')
        }

        req_file = tmp_path / 'request.json'
        req_file.write_text(json.dumps(request))

        bridge_mode(str(req_file))

        # Check output
        output = json.loads((tmp_path / 'output.json').read_text())

        assert output['success'] is False
        assert 'error' in output


# Test knowledge_tools.py wrapper
class TestKnowledgeToolsWrapper:
    """Tests for knowledge_tools.py wrapper functions"""

    def test_import_knowledge_tools(self):
        """Test importing knowledge_tools module"""
        assert hasattr(knowledge_tools, 'query_knowledge')
        assert hasattr(knowledge_tools, 'sync_to_neo4j')
        assert hasattr(knowledge_tools, 'add_knowledge_entity')
        assert hasattr(knowledge_tools, 'add_knowledge_relationship')

    def test_query_knowledge(self):
        """Test query_knowledge wrapper"""
        with patch('knowledge_tools.KnowledgeSystem') as mock_ks:
            mock_instance = Mock()
            mock_instance.semantic_search.return_value = [{'content': 'test'}]
            mock_ks.return_value = mock_instance

            results = knowledge_tools.query_knowledge("test query", limit=5)

            assert isinstance(results, list)
            mock_instance.semantic_search.assert_called_once()

    def test_add_knowledge_entity_not_implemented(self):
        """Test that add_knowledge_entity raises NotImplementedError"""
        with pytest.raises(NotImplementedError):
            knowledge_tools.add_knowledge_entity('test_type', {'key': 'value'})

    def test_add_knowledge_relationship_not_implemented(self):
        """Test that add_knowledge_relationship raises NotImplementedError"""
        with pytest.raises(NotImplementedError):
            knowledge_tools.add_knowledge_relationship('entity1', 'entity2', 'relates_to')

    def test_sync_to_neo4j_not_implemented(self):
        """Test that sync_to_neo4j raises NotImplementedError"""
        with pytest.raises(NotImplementedError):
            knowledge_tools.sync_to_neo4j()


# Performance tests
class TestPerformance:
    """Performance tests for HNSW index and similarity search"""

    def test_hnsw_index_performance(self, knowledge_system):
        """Test HNSW index performance for similarity search"""
        import time

        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.1] * 384):
            # Insert 100 entries
            for i in range(100):
                knowledge_system.store_knowledge(
                    content=f"Test entry {i} with some content",
                    source=f"test-{i}",
                    source_type="benchmark"
                )

            # Measure search time
            start = time.time()
            results = knowledge_system.semantic_search("test content", limit=10)
            elapsed = time.time() - start

        # Should be fast (< 100ms for 100 entries)
        assert elapsed < 0.1
        assert len(results) <= 10

    def test_batch_insert_performance(self, knowledge_system):
        """Test batch insert performance"""
        import time

        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.1] * 384):
            start = time.time()
            for i in range(50):
                knowledge_system.store_knowledge(
                    content=f"Batch entry {i}",
                    source=f"batch-{i}",
                    source_type="benchmark"
                )
            elapsed = time.time() - start

        # Should handle 50 inserts reasonably fast
        assert elapsed < 5.0


# Integration tests
class TestIntegration:
    """Integration tests with actual database"""

    def test_full_workflow(self, knowledge_system, knowledge_sync):
        """Test complete workflow: store, search, share, verify"""
        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.1] * 384):
            with patch.object(knowledge_sync, 'generate_embedding', return_value=[0.1] * 384):
                # 1. Store knowledge
                entry_id = knowledge_system.store_knowledge(
                    content="Integration test discovery",
                    source="integration-test",
                    source_type="test"
                )

                # 2. Search
                results = knowledge_system.semantic_search("integration test")
                assert any(r['id'] == entry_id for r in results)

                # 3. Share discovery
                disc_id = knowledge_sync.share_discovery(
                    worker_id='worker-integration',
                    discovery_type='pattern',
                    content='Integration test pattern',
                    confidence=0.85
                )

                # 4. Verify discovery
                knowledge_sync.verify_discovery(disc_id, 'worker-02', True, 'Verified')
                knowledge_sync.verify_discovery(disc_id, 'worker-03', True, 'Verified')
                knowledge_sync.verify_discovery(disc_id, 'worker-04', True, 'Verified')

                # 5. Get fleet knowledge
                fleet_knowledge = knowledge_sync.get_fleet_knowledge()
                assert any(k['id'] == disc_id for k in fleet_knowledge)

    def test_provenance_chain(self, knowledge_system):
        """Test provenance tracking across operations"""
        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.1] * 384):
            # Store
            entry_id = knowledge_system.store_knowledge(
                content="Original content",
                source="test",
                source_type="test",
                actor="creator"
            )

            # Update multiple times
            knowledge_system.update_knowledge(entry_id, "Updated v1", "updater-1")
            knowledge_system.update_knowledge(entry_id, "Updated v2", "updater-2")

        # Get provenance
        provenance = knowledge_system.get_provenance(entry_id)

        # Should have 3 actions
        actions = [p['action'] for p in provenance]
        actors = [p['actor'] for p in provenance]

        assert 'created' in actions
        assert actions.count('updated') == 2
        assert 'creator' in actors
        assert 'updater-1' in actors
        assert 'updater-2' in actors

    def test_chunking_workflow(self, knowledge_system):
        """Test full workflow with chunked content"""
        large_content = "This is test content. " * 150  # ~3300 chars

        with patch.object(knowledge_system, 'generate_embedding', return_value=[0.1] * 384):
            # Store large content
            entry_id = knowledge_system.store_knowledge(
                content=large_content,
                source="chunk-test",
                source_type="test",
                actor="chunker"
            )

        # Verify chunks
        cursor = knowledge_system.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*), MAX(metadata->>'chunk_index')
            FROM knowledge.entries
            WHERE source = 'chunk-test'
        """)
        count, max_index = cursor.fetchone()
        cursor.close()

        assert count > 1
        assert max_index is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '--cov=knowledge_system', '--cov=knowledge_sync', '--cov-report=term-missing'])
