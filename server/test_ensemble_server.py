#!/usr/bin/env python3
"""End-to-end tests for the canonical Ensemble REST gateway."""
from __future__ import annotations
import json, tempfile, threading, urllib.error, urllib.request
from pathlib import Path

def request(server, method, path, payload=None):
    url=f"http://127.0.0.1:{server.server_port}{path}"
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,method=method)
    req.add_header("Content-Type","application/json")
    try:
        with urllib.request.urlopen(req,timeout=3) as r: return r.status,json.loads(r.read())
    except urllib.error.HTTPError as e: return e.code,json.loads(e.read())

def run():
    import sys, time
    root_repo=Path(__file__).parents[1]
    sys.path.insert(0,str(root_repo))
    sys.path.insert(0,str(root_repo/"graph-service"))
    sys.path.insert(0,str(root_repo/"memory-service"))
    from graph_service import create_server as graph_server
    from memory_service import MemoryService
    from server.ensemble_server import create_server as gateway_server
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        graph=graph_server("127.0.0.1",0,root/"graph.json")
        gt=threading.Thread(target=graph.serve_forever,daemon=True); gt.start()
        memory=MemoryService(root/"memory.sock",root/"memory")
        mt=threading.Thread(target=memory.start,daemon=True); mt.start()
        for _ in range(200):
            if memory.http_port: break
            time.sleep(.01)
        assert memory.http_port
        gateway=gateway_server("127.0.0.1",0,
                               graph_url=f"http://127.0.0.1:{graph.server_port}",
                               memory_url=f"http://127.0.0.1:{memory.http_port}")
        kt=threading.Thread(target=gateway.serve_forever,daemon=True); kt.start()
        try:
            assert request(gateway,"GET","/api/v1/health")[0]==200
            for node in [
                {"id":"model:sonnet","type":"model","properties":{"name":"sonnet"}},
                {"id":"task:code_review","type":"task_type","properties":{"name":"code_review"}},
            ]:
                assert request(gateway,"POST","/api/v1/graph/add-node",node)[0]==200
            assert request(gateway,"POST","/api/v1/graph/add-edge",{
                "source":"model:sonnet","target":"task:code_review","type":"succeeded_on",
                "properties":{"cost":0.12}})[0]==200
            status,body=request(gateway,"POST","/api/v1/decision/analytics/best-models",{"task_type":"code_review"})
            assert status==200 and body["ok"] and body["data"][0]["model"]=="sonnet",body
            status,body=request(gateway,"POST","/api/v1/decision/analytics/best-models",{})
            assert status==400 and not body["ok"]
            status,body=request(gateway,"POST","/api/v1/decision/query/semantic",{})
            assert status==400 and not body["ok"]
        finally:
            gateway.shutdown(); gateway.server_close()
            graph.shutdown(); graph.server_close()
            memory.stop()
            kt.join(2); gt.join(2); mt.join(2)

if __name__=="__main__":
    run(); print("ensemble REST gateway tests passed")
