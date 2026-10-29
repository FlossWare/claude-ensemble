import json
import threading
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from unittest.mock import patch

import pytest

from runtime.server import BoundedThreadingHTTPServer, Handler
from runtime.knowledge import KnowledgeError, KnowledgeService


SCOPE = {"type": "project", "id": "project-a", "visibility": "private"}
PROFILE = {"name": "default", "version": "0.1", "digest": "0123456789abcdef" * 4}


def create_request(content="source document"):
    return {
        "scope": SCOPE,
        "source_kind": "document",
        "canonical_locator": "https://example.invalid/doc/1",
        "content": content,
        "provenance": {"origin": "test", "evidence_ids": ["evidence-1"]},
        "retention_policy": {"kind": "standard"},
        "index_profile": PROFILE,
    }


@pytest.fixture
def service(tmp_path):
    return KnowledgeService(tmp_path / "knowledge.sqlite3")



def test_create_is_canonical_and_idempotent_across_restart(tmp_path):
    path = tmp_path / "knowledge.sqlite3"
    first_service = KnowledgeService(path)
    status, created = first_service.create(create_request(), "create-key", "req-1")
    assert status == 202
    assert created["source_id"].startswith("knowledge:")
    assert created["revision_sequence"] == 1
    assert created["index_profile"] == PROFILE

    restarted = KnowledgeService(path)
    status, repeated = restarted.create(create_request(), "create-key", "req-2")
    assert status == 202
    assert repeated["source_id"] == created["source_id"]
    assert repeated["operation_id"] == created["operation_id"]
    source_key = created["source_id"].removeprefix("knowledge:")
    assert restarted.read(source_key, SCOPE, "req-3")["content"] == "source document"


def test_idempotency_key_conflict_is_rejected(service):
    service.create(create_request(), "same-key", "req-1")
    with pytest.raises(KnowledgeError) as error:
        service.create(create_request("different content"), "same-key", "req-2")
    assert error.value.status == 409
    assert error.value.code == "idempotency_conflict"


def test_revision_update_requires_current_base_and_preserves_old_revision(service):
    _, created = service.create(create_request(), "create-key", "req-1")
    key = created["source_id"].removeprefix("knowledge:")
    update = {
        "expected_base_revision_sequence": 1,
        "content": "updated source",
        "provenance": {"origin": "update"},
        "index_profile": PROFILE,
    }
    _, updated = service.update(key, update, "update-key", "req-2", SCOPE)
    assert updated["revision_sequence"] == 2
    assert service.read(key, SCOPE, "req-3")["content"] == "updated source"
    with pytest.raises(KnowledgeError) as error:
        service.update(key, update, "stale-update-key", "req-4", SCOPE)
    assert error.value.code == "revision_conflict"
    with pytest.raises(KnowledgeError) as error:
        service.read_for_ingestion(key, SCOPE, 1)
    assert error.value.code == "stale_revision"


def test_revision_verification_distinguishes_current_stale_missing_and_tombstoned(service):
    _, created = service.create(create_request(), "create-key", "req-1")
    key = created["source_id"].removeprefix("knowledge:")
    _, updated = service.update(key, {
        "expected_base_revision_sequence": 1,
        "content": "revision two",
        "provenance": {"origin": "update"},
        "index_profile": PROFILE,
    }, "update-key", "req-2", SCOPE)
    source_id = created["source_id"]
    results = service.verify_revisions([
        {"source_id": source_id, "revision_sequence": 2},
        {"source_id": source_id, "revision_sequence": 1},
        {"source_id": "knowledge:unknown", "revision_sequence": 1},
    ])
    assert [item["status"] for item in results] == ["current", "stale", "not_found"]
    _, deleted = service.delete(key, SCOPE, "source", "delete-key", "req-3")
    assert deleted["revision_sequence"] == 3
    tombstoned = service.verify_revisions([{"source_id": source_id, "revision_sequence": 2}])
    assert tombstoned[0]["status"] == "tombstoned"
    with pytest.raises(KnowledgeError) as error:
        service.read(key, SCOPE, "req-4")
    assert error.value.status == 404


def test_operation_status_and_delete_details_are_available(service):
    _, created = service.create(create_request(), "create-key", "req-1")
    key = created["source_id"].removeprefix("knowledge:")
    _, deleted = service.delete(key, SCOPE, "source", "delete-key", "req-2")
    operation = service.operation(deleted["operation_id"], key, "req-3")
    details = service.deletion_details(deleted["operation_id"])
    assert operation["canonical_status"] == "tombstoned"
    assert details["source_id"] == created["source_id"]
    assert details["index_profile"] == PROFILE



def test_knowledge_create_and_canonical_read_routes_are_reachable(tmp_path):
    service = KnowledgeService(tmp_path / "knowledge-http.sqlite3")
    server = BoundedThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch("runtime.server.get_knowledge_service", return_value=service), \
             patch.object(Handler, "_memory_preflight", return_value={"bundle": {}, "index_base": "", "chunking_base": ""}), \
             patch("runtime.server._MEMORY_INGEST_EXECUTOR.submit"), \
             patch("runtime.server._MEMORY_GRAPH_EXECUTOR.submit"):
            base = f"http://127.0.0.1:{server.server_port}"
            body = json.dumps(create_request()).encode()
            request = Request(base + "/api/v1/knowledge/sources", data=body, method="POST",
                              headers={"Content-Type": "application/json", "Idempotency-Key": "http-create-key"})
            with urlopen(request, timeout=3) as response:
                created = json.loads(response.read())
                assert response.status == 202
            scope_query = urlencode({"scope_type": SCOPE["type"], "scope_id": SCOPE["id"],
                                     "visibility": SCOPE["visibility"]})
            with urlopen(base + "/api/v1/knowledge/sources/" + created["source_id"].split(":", 1)[1] + "?" + scope_query,
                         timeout=3) as response:
                canonical = json.loads(response.read())
                assert response.status == 200
                assert canonical["content"] == "source document"
                assert canonical["source_id"] == created["source_id"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)



def test_graph_projection_journal_is_owner_scoped_and_completion_waits_for_index(tmp_path):
    service = KnowledgeService(tmp_path / "knowledge-graph.sqlite3")
    _, created = service.create(create_request(), "create-key", "req-1")
    operation_id = created["operation_id"]
    pending = service.pending_graph_projections()
    assert len(pending) == 1
    assert pending[0]["operation_kind"] == "project"
    assert pending[0]["payload"]["source_id"] == created["source_id"]
    assert pending[0]["payload"]["owner_projection_sequence"] == 1

    service.update_graph_operation(operation_id, "indexed")
    operation = service.operation(operation_id, None, "req-2")
    assert operation["graph_status"] == "indexed"
    assert operation["status"] == "pending"
    service.update_operation(operation_id, "complete", "indexed")
    operation = service.operation(operation_id, None, "req-3")
    assert operation["status"] == "complete"
    assert service.pending_graph_projections() == []

