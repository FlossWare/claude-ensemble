#!/usr/bin/env python3
"""Dependency-free MCP broker for Grok, Perplexity, and Jules."""

import json, os, re, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

def http(url, method="GET", headers=None, body=None, timeout=120):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode()

def json_call(url, method="GET", headers=None, body=None, timeout=120):
    return json.loads(http(url, method, headers, body, timeout))

def parse(text):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise RuntimeError("reviewer returned non-JSON output")
        return json.loads(match.group())

def fail(name, provider, start, exc):
    return {"reviewer": name, "status": "failed", "verdict": "comment",
            "summary": "Reviewer invocation failed.", "findings": [],
            "provider": provider, "model": "",
            "latency_ms": int((time.monotonic() - start) * 1000), "error": str(exc)}

def complete(name, provider, model, start, value):
    findings = value.get("findings", [])
    if not isinstance(findings, list):
        findings = []
    return {"reviewer": name, "status": "complete",
            "verdict": str(value.get("verdict", "comment")),
            "summary": str(value.get("summary", "")), "findings": findings,
            "provider": provider, "model": model,
            "latency_ms": int((time.monotonic() - start) * 1000), "error": ""}

def prompt(p):
    return """Review GitHub PR #{pr} in {repo}. Return ONLY JSON with verdict, summary, and findings.
Do not modify code. Do not include private reasoning. Base={base}; Head={head}; Focus={focus}.
DIFF:
{diff}""".format(pr=p["pr_number"], repo=p["repository"], base=p["base_sha"],
                 head=p["head_sha"],
                 focus=p.get("focus") or "correctness, contracts, security, tests, regressions",
                 diff=p["diff"])

def grok(p):
    start = time.monotonic()
    try:
        key = os.environ["XAI_API_KEY"]
        model = os.environ.get("GROK_MODEL", "grok-4.7")
        headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
        body = {"model": model, "messages": [
            {"role": "system", "content": "Independent code reviewer."},
            {"role": "user", "content": prompt(p)}], "temperature": 0}
        data = json_call("https://api.x.ai/v1/chat/completions", "POST", headers, body)
        return complete("grok", "xai", model, start, parse(data["choices"][0]["message"]["content"]))
    except Exception as exc:
        return fail("grok", "xai", start, exc)

def perplexity(p):
    start = time.monotonic()
    try:
        key = os.environ["PERPLEXITY_API_KEY"]
        model = os.environ.get("PERPLEXITY_MODEL", "sonar-pro")
        headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
        body = {"model": model, "messages": [
            {"role": "system", "content": "Independent code reviewer."},
            {"role": "user", "content": prompt(p)}], "temperature": 0}
        data = json_call(os.environ.get(
            "PERPLEXITY_API_URL", "https://api.perplexity.ai/chat/completions"),
            "POST", headers, body)
        return complete("perplexity", "perplexity", model, start,
                        parse(data["choices"][0]["message"]["content"]))
    except Exception as exc:
        return fail("perplexity", "perplexity", start, exc)

def jules(p):
    start = time.monotonic()
    try:
        key = os.environ["JULES_API_KEY"]
        owner, repo = p["repository"].split("/", 1)
        sources = json_call("https://jules.googleapis.com/v1alpha/sources",
                            headers={"x-goog-api-key": key})
        source = next(x["name"] for x in sources["sources"]
                      if x.get("githubRepo", {}).get("owner") == owner
                      and x.get("githubRepo", {}).get("repo") == repo)
        body = {"prompt": """Review PR #{0} in {1}. REVIEW ONLY: do not edit, commit, or create a PR.
Compare {2} with {3}. Return ONLY JSON with verdict, summary, and findings.
Do not include private reasoning.""".format(
            p["pr_number"], p["repository"], p["base_sha"], p["head_sha"]),
            "title": "Review PR #{}".format(p["pr_number"]),
            "sourceContext": {"source": source,
                              "githubRepoContext": {"startingBranch": p.get("head_ref", "main")}},
            "requirePlanApproval": False}
        session = json_call("https://jules.googleapis.com/v1alpha/sessions", "POST",
                            {"x-goog-api-key": key, "Content-Type": "application/json"}, body)
        session_id = session.get("id") or session["name"].split("/")[-1]
        deadline = time.monotonic() + int(os.environ.get("JULES_TIMEOUT_SECONDS", "900"))
        messages = []
        while time.monotonic() < deadline:
            encoded = urllib.parse.quote(session_id, safe="")
            state = json_call("https://jules.googleapis.com/v1alpha/sessions/" + encoded,
                              headers={"x-goog-api-key": key})
            activities = json_call(
                "https://jules.googleapis.com/v1alpha/sessions/" + encoded + "/activities?pageSize=100",
                headers={"x-goog-api-key": key})
            for activity in activities.get("activities", []):
                message = activity.get("agentMessaged", {}).get("agentMessage")
                if message and message not in messages:
                    messages.append(message)
            if state.get("state") == "COMPLETED":
                break
            if state.get("state") == "FAILED":
                raise RuntimeError("Jules session failed")
            time.sleep(float(os.environ.get("JULES_POLL_SECONDS", "3")))
        else:
            raise RuntimeError("Jules review timed out")
        return complete("jules", "google-jules", "jules", start, parse(messages[-1]))
    except Exception as exc:
        return fail("jules", "google-jules", start, exc)

def package(repository, pr_number, focus=""):
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "claude-ensemble-reviewer-mcp"}
    if token:
        headers["Authorization"] = "Bearer " + token
    url = "https://api.github.com/repos/{}/pulls/{}".format(repository, pr_number)
    metadata = json_call(url, headers=headers)
    diff_headers = dict(headers)
    diff_headers["Accept"] = "application/vnd.github.v3.diff"
    diff = http(url, headers=diff_headers)
    if len(diff.encode()) > 1500000:
        raise RuntimeError("PR diff exceeds 1.5MB")
    return {"repository": repository, "pr_number": pr_number,
            "base_sha": metadata["base"]["sha"], "head_sha": metadata["head"]["sha"],
            "base_ref": metadata["base"]["ref"], "head_ref": metadata["head"]["ref"],
            "focus": focus, "diff": diff}

def review_all(p):
    funcs = {"grok": grok, "perplexity": perplexity, "jules": jules}
    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(func, p): name for name, func in funcs.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as exc:
                results[name] = fail(name, name, time.monotonic(), exc)
    return [results[name] for name in ("grok", "perplexity", "jules")]

SCHEMA = {"type": "object", "properties": {
    "repository": {"type": "string"},
    "pr_number": {"type": "integer", "minimum": 1},
    "focus": {"type": "string"}}, "required": ["repository", "pr_number"]}

TOOLS = [{"name": "review_grok", "description": "Review a GitHub pull request with Grok.", "inputSchema": SCHEMA},
         {"name": "review_perplexity", "description": "Review a GitHub pull request with Perplexity.", "inputSchema": SCHEMA},
         {"name": "review_jules", "description": "Review a GitHub pull request with Jules.", "inputSchema": SCHEMA},
         {"name": "review_all", "description": "Run Grok, Perplexity, and Jules independently.", "inputSchema": SCHEMA}]

def handle(request):
    method, request_id = request.get("method"), request.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": request_id,
                "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                           "serverInfo": {"name": "claude-ensemble-reviewer", "version": "0.1"}}}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        try:
            args = request.get("params", {}).get("arguments", {})
            package_data = package(args["repository"], int(args["pr_number"]), args.get("focus", ""))
            name = request["params"]["name"]
            if name == "review_all":
                result = {"reviews": review_all(package_data)}
            elif name == "review_grok":
                result = grok(package_data)
            elif name == "review_perplexity":
                result = perplexity(package_data)
            elif name == "review_jules":
                result = jules(package_data)
            else:
                raise ValueError("unknown tool")
            return {"jsonrpc": "2.0", "id": request_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]}}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": request_id,
                    "error": {"code": -32000, "message": str(exc)}}
    if request_id is None:
        return None
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": -32601, "message": "method not found"}}

if __name__ == "__main__":
    import sys
    for line in sys.stdin:
        if line.strip():
            print(json.dumps(handle(json.loads(line))), flush=True)
