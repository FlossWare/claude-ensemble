"""Decision Support advisor built on observed learning data."""
from __future__ import annotations
from typing import Any
from .learning_analytics import LearningAnalytics

class ArbitrationAdvisor:
    def __init__(self, analytics: LearningAnalytics|None=None):
        self.analytics=analytics or LearningAnalytics()

    def recommend_models(self, task_type: str, scope: str="medium", budget: float|None=None, count: int=3)->dict[str,Any]:
        result=self.analytics.best_models_for(task_type,scope,count+2)
        if not result.get("ok") or not result.get("data"):
            return {"ok":False,"error":f"No historical data for {task_type}","data":None}
        rows=[dict(x) for x in result["data"] if budget is None or x["avg_cost"]<=budget]
        if not rows: return {"ok":False,"error":f"No models available within {budget} budget","data":None}
        for i,row in enumerate(rows[:count]):
            row["reason"]="highest observed success rate" if i==0 else "observed alternative"
        rows=rows[:count]
        return {"ok":True,"error":None,"data":{"task_type":task_type,"scope":scope,"budget":budget,"recommended":rows,"sample_count":sum(x["sample_count"] for x in rows)},"sample_count":sum(x["sample_count"] for x in rows)}

    def recommend_phases(self, task_type: str, scope: str, budget: float|None=None)->dict[str,Any]:
        recommendation="3" if scope=="large" else "2"
        costs=self.analytics.scope_cost_analysis()
        scope_data=costs.get("data",{}).get(scope,{})
        if budget is not None and scope_data.get("avg_cost",0)>budget: recommendation="2"
        failures=self.analytics.failure_analysis(task_type)
        if failures.get("data",{}).get("failure_count",0)>5: recommendation="3"
        return {"ok":True,"error":None,"data":{"task_type":task_type,"scope":scope,"recommendation":recommendation,"empirical_failure_count":failures.get("data",{}).get("failure_count",0),"estimated_costs":scope_data},"sample_count":failures.get("sample_count",0)}

    def estimate_cost(self, models:list[str], task_type:str, phases:int=2)->dict[str,Any]:
        result=self.analytics.best_models_for(task_type,limit=20)
        costs={x["model"]:x["avg_cost"] for x in result.get("data",[])}
        worker=sum(costs.get(m,0.15) for m in models)/len(models) if models else 0.15
        total=worker+0.08
        return {"ok":True,"error":None,"data":{"task_type":task_type,"phases":phases,"workers":models,"worker_cost_per_phase":worker,"arbiter_cost_per_phase":0.08,"total_per_phase":total,"total_all_phases":total*phases,"sample_count":result.get("sample_count",0)},"sample_count":result.get("sample_count",0)}

    def full_recommendation(self, task_type:str, scope:str="medium", budget:float|None=None)->dict[str,Any]:
        models=self.recommend_models(task_type,scope,budget)
        phases=self.recommend_phases(task_type,scope,budget)
        if not models.get("ok") or not phases.get("ok"):
            return {"ok":False,"error":"Could not generate recommendations","data":{"models_error":models.get("error"),"phases_error":phases.get("error")}}
        chosen=[x["model"] for x in models["data"]["recommended"]]
        cost=self.estimate_cost(chosen,task_type,int(phases["data"]["recommendation"]))
        return {"ok":True,"error":None,"data":{"task_type":task_type,"scope":scope,"budget":budget,"recommendation":{"models":chosen,"phases":int(phases["data"]["recommendation"]),"estimated_cost":cost["data"]["total_all_phases"]},"details":{"models":models,"phases":phases,"cost":cost}},"sample_count":models.get("sample_count",0)}

