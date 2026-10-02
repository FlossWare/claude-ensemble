#!/usr/bin/env python3
"""End-to-end tests for the canonical Ensemble REST gateway."""
from __future__ import annotations
import json, os, tempfile, threading, urllib.error, urllib.request
from pathlib import Path

def request(server, method, path, payload=None, headers=None):

    url=f"http://127.0.0.1:{server.server_port}{path}"
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,method=method)
    req.add_header("Content-Type","application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
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
    from server.ensemble_server import create_server as gateway_server, _forward
    from learning.arbitration_advisor import ArbitrationAdvisor
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
        unavailable=gateway_server("127.0.0.1",0,graph_url="",memory_url="")
        ut=threading.Thread(target=unavailable.serve_forever,daemon=True); ut.start()
        try:
            status,body=request(unavailable,"GET","/api/v1/graph/health")
            assert status==503 and not body["ok"]
        finally:
            unavailable.shutdown(); unavailable.server_close(); ut.join(2)

        advisor=ArbitrationAdvisor()
        advisor.recommend_models=lambda *args, **kwargs: {
            "ok":True,"error":None,"error_code":None,
            "data":{"recommended":[{"model":"sonnet"}],"sample_count":1},
            "sample_count":1,
        }
        advisor.recommend_phases=lambda *args, **kwargs: {
            "ok":True,"error":None,"error_code":None,
            "data":{"recommendation":"2","failure_count":0},
            "sample_count":1,
        }
        advisor.estimate_cost=lambda *args, **kwargs: {
            "ok":False,"error":"No observed cost data","error_code":"no_data","data":None,
        }
        result=advisor.full_recommendation("code_review")
        assert not result["ok"] and result["error_code"]=="no_data"
        assert result["data"]["details"]["cost"]["error_code"]=="no_data"

        class CostAnalytics:
            def best_models_for(self, task_type, *args, **kwargs):
                return {
                    "ok":True,
                    "data":[
                        {"model":"cheap","avg_cost":0.10},
                        {"model":"expensive","avg_cost":0.20},
                    ],
                    "sample_count":2,
                }

        cost_advisor=ArbitrationAdvisor(CostAnalytics())
        previous=os.environ.get("ENSEMBLE_ARBITER_COST")
        os.environ["ENSEMBLE_ARBITER_COST"]="0.08"
        try:
            result=cost_advisor.estimate_cost(["cheap","expensive"],"code_review",phases=3)
        finally:
            if previous is None:
                os.environ.pop("ENSEMBLE_ARBITER_COST",None)
            else:
                os.environ["ENSEMBLE_ARBITER_COST"]=previous
        assert result["ok"]
        assert abs(result["data"]["worker_cost_per_phase"]-0.30)<1e-6
        assert abs(result["data"]["total_per_phase"]-0.38)<1e-6
        assert abs(result["data"]["total_all_phases"]-1.14)<1e-6

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

            # Memory is independently reachable through the same public boundary.
            assert request(gateway,"POST","/api/v1/memory/write",
                           {"name":"rest-test","content":"gateway memory round trip"})[0]==200
            status,body=request(gateway,"POST","/api/v1/memory/read",{"name":"rest-test"})
            assert status==200 and body["ok"] and body["content"]=="gateway memory round trip",body

            status,body=request(gateway,"POST","/api/v1/decision/analytics/best-models",{"task_type":"code_review"})
            assert status==200 and body["ok"] and body["data"][0]["model"]=="sonnet",body
            status,body=request(gateway,"POST","/api/v1/decision/query/patterns",{"model":"sonnet"})
            assert status==200 and body["ok"] and body["sample_count"]==1,body
            status,body=request(gateway,"POST","/api/v1/decision/analytics/best-models",{})
            assert status==400 and not body["ok"] and body["error_code"]=="invalid_request"
            status,body=request(gateway,"POST","/api/v1/decision/query/semantic",{})
            assert status==400 and not body["ok"] and body["error_code"]=="invalid_request"

            # A declared oversized body is rejected before any read/allocation.
            status,body=request(gateway,"POST","/api/v1/graph/add-node",{"id":"oversized"},
                                 {"Content-Length":str(16*1024*1024+1)})
            assert status==400 and not body["ok"]

            # Gateway instances retain their own upstream routing.
            graph2=graph_server("127.0.0.1",0,root/"graph2.json")
            gt2=threading.Thread(target=graph2.serve_forever,daemon=True); gt2.start()
            gateway2=gateway_server("127.0.0.1",0,
                                    graph_url=f"http://127.0.0.1:{graph2.server_port}",
                                    memory_url=f"http://127.0.0.1:{memory.http_port}")
            kt2=threading.Thread(target=gateway2.serve_forever,daemon=True); kt2.start()
            try:
                assert request(gateway2,"POST","/api/v1/graph/add-node",
                               {"id":"model:other","type":"model","properties":{}})[0]==200
                assert request(gateway,"POST","/api/v1/graph/add-node",
                               {"id":"model:first","type":"model","properties":{}})[0]==200
                status,_=request(gateway2,"GET","/api/v1/graph/node/model:first")
                assert status==404
                status,_=request(gateway2,"GET","/api/v1/graph/node/model:other")
                assert status==200
            finally:
                gateway2.shutdown(); gateway2.server_close()
                graph2.shutdown(); graph2.server_close()
                kt2.join(2); gt2.join(2)
        finally:
            gateway.shutdown(); gateway.server_close()
            graph.shutdown(); graph.server_close()
            memory.stop()
            kt.join(2); gt.join(2); mt.join(2)

if __name__=="__main__":
    run(); print("ensemble REST gateway tests passed")
