---
name: always-max-parallelism
description: User ALWAYS wants maximum parallelism - distribute ALL work across ALL available fleet nodes
metadata:
  type: feedback
  created: 2026-06-14
  priority: critical
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# Always Use Maximum Parallelism

**Rule:** ALWAYS distribute work across ALL available fleet nodes with MAXIMUM parallelism.

**Why:** User explicitly stated "i always want max parallelism" during deep learning workflow setup. This is a standing preference for ALL future work.

**How to apply:**

1. **Never use fewer nodes than available** - If 6 nodes exist, use all 6
2. **Distribute EVERY workload type:**
   - Code analysis: Split across ALL nodes
   - PDF analysis: Split across ALL nodes
   - Web analysis: Split across ALL nodes
   - API model calls: Distribute across nodes
   - Ollama models: Run on ALL nodes with Ollama installed
   - Documentation fixes: Parallel across nodes
   - Testing: Parallel test execution
   - Build tasks: Distributed builds

3. **Use parallel() by default** in workflows, not pipeline()
   - pipeline() adds sequential waits between stages
   - parallel() eliminates waits, maximizes throughput
   - Only use pipeline() when stages MUST be sequential

4. **Split data/tasks evenly:**
   - 6 nodes = 6 batches
   - Each node gets 1/6 of the work
   - Different focus per node (patterns, algorithms, APIs, testing, etc.)

5. **Maximize model diversity:**
   - Use DIFFERENT models on each node
   - API models: DeepSeek, Cerebras, OpenRouter, etc.
   - Local models: Different Ollama model per node
   - 40+ total models = maximum coverage

6. **Check available nodes first:**
   ```bash
   for node in laptop-01 server-01 server-02 server-03 aio-01 pi-02; do
     ssh $node 'echo available' 2>/dev/null && echo $node
   done
   ```

7. **Workflow pattern:**
   ```javascript
   const results = await parallel([
     () => agent('Work batch 1/6', {label: 'node1'}),
     () => agent('Work batch 2/6', {label: 'node2'}),
     () => agent('Work batch 3/6', {label: 'node3'}),
     () => agent('Work batch 4/6', {label: 'node4'}),
     () => agent('Work batch 5/6', {label: 'node5'}),
     () => agent('Work batch 6/6', {label: 'node6'})
   ])
   ```

**What this changes:**
- ❌ OLD: "Use 2-3 nodes for this task"
- ✅ NEW: "Use ALL 6 nodes for this task"

- ❌ OLD: "Laptop-01 and server-01 will handle PDFs"
- ✅ NEW: "ALL 6 nodes will analyze PDFs in parallel (6 batches)"

- ❌ OLD: "Pipeline through discovery → analysis → synthesis"
- ✅ NEW: "Parallel discovery on all nodes, parallel analysis on all nodes"

**Exceptions:** NONE - always maximize parallelism unless physically impossible (only 1 task to do, only 1 node accessible)

## Related

- [[feedback_workflow_parallel_vs_pipeline]] - parallel() vs pipeline() semantics
- [[feedback_always_multi_ai]] - Multi-AI consensus (also benefits from parallelism)
- [[reference_distributed_fleet]] - Fleet topology and capabilities
