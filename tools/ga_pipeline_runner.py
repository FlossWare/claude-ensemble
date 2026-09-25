#!/usr/bin/env python3
"""Pipeline runner for GA meta-optimization.

Configures and executes the 9-technique pipeline per a PipelineChromosome.
Each technique is called via REST API on aio-01:5000.
"""
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('pipeline_runner')

API_BASE = os.environ.get('API_BASE', 'http://localhost:5000')


@dataclass
class PipelineResult:
    answer: str = ""
    latency_ms: float = 0.0
    cost_estimate: float = 0.0
    techniques_used: List[str] = field(default_factory=list)
    error: Optional[str] = None
    raw_responses: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


def _api(method: str, path: str, json_data=None, timeout: int = 60) -> Optional[Dict]:
    try:
        url = f'{API_BASE}{path}'
        if method == 'GET':
            resp = requests.get(url, timeout=timeout)
        else:
            resp = requests.post(url, json=json_data or {}, timeout=timeout)
        if resp.ok:
            return resp.json()
        logger.warning(f'{method} {path} returned {resp.status_code}: {resp.text[:200]}')
    except Exception as e:
        logger.warning(f'{method} {path} failed: {e}')
    return None


def _get_api_key(name: str = 'PERSONAL_OPENROUTER_API_KEY') -> Optional[str]:
    data = _api('GET', f'/secrets/{name}')
    if data:
        return data.get('value')
    return os.environ.get(name)


def run_cascade(query: str, chromosome) -> Optional[Dict]:
    """Execute LLM cascade: route through tiers based on confidence."""
    return _api('POST', '/cascade/query', {
        'query': query,
        'threshold': chromosome.cascade_threshold,
        'max_tier': chromosome.cascade_max_tier,
        'max_tokens': chromosome.cascade_max_tokens,
        'timeout': chromosome.cascade_timeout,
    }, timeout=chromosome.cascade_timeout + 10)


def run_crag(query: str, chromosome) -> Optional[Dict]:
    """Execute Corrective RAG: retrieve, grade, refine."""
    return _api('POST', '/rag/corrective-search', {
        'query': query,
        'limit': chromosome.crag_limit,
        'mode': chromosome.crag_mode,
        'max_fallback_rounds': chromosome.crag_max_fallback_rounds,
    }, timeout=30)


def run_graph_rag(query: str, chromosome) -> Optional[Dict]:
    """Execute Graph RAG: entity extraction + graph traversal."""
    return _api('POST', '/graph-rag/query', {
        'query': query,
        'max_hops': chromosome.graph_max_hops,
        'expand_entities': chromosome.graph_expansion,
        'excerpt_length': chromosome.graph_excerpt_len,
    }, timeout=30)


def run_moa(query: str, chromosome, context: str = "") -> Optional[Dict]:
    """Execute Mixture of Agents: multi-model proposal + aggregation."""
    full_query = f"{query}\n\nContext:\n{context}" if context else query
    return _api('POST', '/moa/query', {
        'query': full_query,
        'num_proposers': chromosome.moa_num_proposers,
        'num_aggregators': chromosome.moa_num_aggregators,
        'num_layers': chromosome.moa_num_layers,
        'temperature': chromosome.moa_temperature,
        'max_tokens': chromosome.moa_max_tokens,
    }, timeout=120)


def select_thompson(query: str, chromosome) -> Optional[Dict]:
    """Select model via non-stationary Thompson Sampling."""
    return _api('POST', '/learning/bandits/select', {
        'task_type': 'benchmark',
        'decay_factor': chromosome.ts_decay_factor,
        'window_size': chromosome.ts_window_size,
    }, timeout=10)


def update_thompson(strategy: str, reward: float, chromosome) -> None:
    """Update Thompson Sampling bandit with observed reward."""
    _api('POST', '/learning/bandits/update', {
        'strategy': strategy,
        'reward': reward,
        'outcome': 'SUCCESS' if reward > 0.5 else 'FAILED',
    }, timeout=5)


def select_linucb(query: str, chromosome) -> Optional[Dict]:
    """Select model via LinUCB contextual bandits."""
    return _api('POST', '/learning/strategies/select-nonstationary', {
        'query': query,
        'alpha': chromosome.linucb_alpha,
        'regularization': chromosome.linucb_regularisation,
    }, timeout=10)


def run_contextual_retrieval(query: str, chromosome) -> Optional[Dict]:
    """Start contextual retrieval enrichment."""
    return _api('POST', '/pipeline/contextual-retrieval/start', {
        'query': query,
    }, timeout=30)


def run_evoprompt(query: str, chromosome) -> Optional[Dict]:
    """Run EvoPrompt: LLM-guided prompt evolution."""
    return _api('POST', '/evolution/start', {
        'prompt': query,
        'population_size': 5,
        'generations': 3,
    }, timeout=60)


def run_map_elites(chromosome) -> Optional[Dict]:
    """Start MAP-Elites quality-diversity search."""
    return _api('POST', '/evolution/map-elites/start', {
        'population_size': 10,
        'generations': 5,
    }, timeout=60)


def run_pipeline(query: str, chromosome) -> PipelineResult:
    """Execute the full pipeline configured by a chromosome.

    Pipeline flow:
    1. Route: select model via bandits/cascade
    2. Retrieve: augment with knowledge via CRAG/GraphRAG
    3. Generate: produce answer via cascade/MoA
    4. Learn: update bandits with outcome
    """
    result = PipelineResult()
    start = time.time()
    context_parts = []
    selected_model = None
    selected_strategy = None

    try:
        # --- Step 1: Model Selection / Routing ---
        if chromosome.routing_strategy == 'bandit_first':
            if chromosome.use_contextual_bandits:
                linucb = select_linucb(query, chromosome)
                if linucb:
                    selected_model = linucb.get('selected_model') or linucb.get('strategy')
                    selected_strategy = selected_model
                    result.techniques_used.append('contextual_bandits')
                    result.raw_responses['linucb'] = linucb

            if not selected_model and chromosome.use_thompson:
                ts = select_thompson(query, chromosome)
                if ts:
                    selected_model = ts.get('selected_model') or ts.get('strategy')
                    selected_strategy = selected_model
                    result.techniques_used.append('thompson')
                    result.raw_responses['thompson'] = ts

        elif chromosome.routing_strategy == 'cascade_first':
            if chromosome.use_cascade:
                cascade = run_cascade(query, chromosome)
                if cascade and not cascade.get('error'):
                    answer = cascade.get('answer') or cascade.get('response', '')
                    confidence = cascade.get('confidence', 0)
                    result.techniques_used.append('cascade')
                    result.raw_responses['cascade'] = cascade
                    result.cost_estimate += cascade.get('cost', 0)

                    if confidence >= chromosome.cascade_threshold and answer:
                        result.answer = answer
                        result.latency_ms = (time.time() - start) * 1000
                        return result

        elif chromosome.routing_strategy == 'complexity_route':
            is_complex = len(query) > 200 or query.count('\n') > 3 or '```' in query
            if is_complex and chromosome.use_moa:
                pass  # fall through to MoA in generation step
            elif chromosome.use_cascade:
                cascade = run_cascade(query, chromosome)
                if cascade and not cascade.get('error'):
                    answer = cascade.get('answer') or cascade.get('response', '')
                    confidence = cascade.get('confidence', 0)
                    result.techniques_used.append('cascade')
                    result.raw_responses['cascade'] = cascade
                    result.cost_estimate += cascade.get('cost', 0)

                    if confidence >= chromosome.cascade_threshold and answer:
                        result.answer = answer
                        result.latency_ms = (time.time() - start) * 1000
                        return result

        # --- Step 2: Knowledge Retrieval ---
        if chromosome.use_crag:
            crag = run_crag(query, chromosome)
            if crag and not crag.get('error'):
                results_list = crag.get('results', [])
                if isinstance(results_list, list):
                    for doc in results_list[:chromosome.crag_limit]:
                        if isinstance(doc, dict):
                            context_parts.append(doc.get('content', doc.get('text', str(doc)))[:2000])
                        elif isinstance(doc, str):
                            context_parts.append(doc[:2000])
                result.techniques_used.append('crag')
                result.raw_responses['crag'] = crag

        if chromosome.use_graph_rag:
            graph = run_graph_rag(query, chromosome)
            if graph and not graph.get('error'):
                combined = graph.get('combined_results') or graph.get('results', '')
                if combined:
                    if isinstance(combined, list):
                        context_parts.extend(str(c)[:2000] for c in combined[:5])
                    else:
                        context_parts.append(str(combined)[:3000])
                result.techniques_used.append('graph_rag')
                result.raw_responses['graph_rag'] = graph

        if chromosome.use_contextual_retrieval:
            cr = run_contextual_retrieval(query, chromosome)
            if cr and not cr.get('error'):
                enriched = cr.get('enriched_chunks') or cr.get('results', [])
                if isinstance(enriched, list):
                    for chunk in enriched[:5]:
                        if isinstance(chunk, dict):
                            context_parts.append(chunk.get('enriched_content', chunk.get('content', ''))[:2000])
                result.techniques_used.append('contextual_retrieval')
                result.raw_responses['contextual_retrieval'] = cr

        context = '\n---\n'.join(context_parts) if context_parts else ''

        # --- Step 3: Answer Generation ---
        if chromosome.use_moa:
            moa = run_moa(query, chromosome, context)
            if moa and not moa.get('error'):
                result.answer = moa.get('answer') or moa.get('response', '')
                result.techniques_used.append('moa')
                result.raw_responses['moa'] = moa
                result.cost_estimate += moa.get('cost', 0)

        if not result.answer and chromosome.use_cascade:
            augmented_query = f"{query}\n\nRelevant context:\n{context}" if context else query
            cascade = run_cascade(augmented_query, chromosome)
            if cascade and not cascade.get('error'):
                result.answer = cascade.get('answer') or cascade.get('response', '')
                result.techniques_used.append('cascade')
                result.raw_responses['cascade_final'] = cascade
                result.cost_estimate += cascade.get('cost', 0)

        if not result.answer:
            api_key = _get_api_key()
            if api_key:
                augmented_query = f"{query}\n\nContext:\n{context}" if context else query
                model = selected_model or 'meta-llama/llama-3.3-70b-instruct:free'
                try:
                    resp = requests.post(
                        'https://openrouter.ai/api/v1/chat/completions',
                        headers={
                            'Authorization': f'Bearer {api_key}',
                            'Content-Type': 'application/json',
                        },
                        json={
                            'model': model,
                            'messages': [{'role': 'user', 'content': augmented_query[:8000]}],
                            'max_tokens': 2048,
                            'temperature': 0.3,
                        },
                        timeout=60,
                    )
                    if resp.ok:
                        data = resp.json()
                        result.answer = data['choices'][0]['message']['content']
                        result.techniques_used.append('direct_model')
                        usage = data.get('usage', {})
                        result.cost_estimate += usage.get('total_cost', 0)
                except Exception as e:
                    result.error = f'Direct model fallback failed: {e}'

        # --- Step 4: Bandit Learning ---
        if selected_strategy and result.answer:
            reward = 0.7 if len(result.answer) > 50 else 0.3
            if chromosome.use_thompson:
                update_thompson(selected_strategy, reward, chromosome)
            result.techniques_used.append('bandit_update')

        # --- Step 5: EvoPrompt (if enabled, for prompt refinement) ---
        if chromosome.use_evoprompt and not result.answer:
            evo = run_evoprompt(query, chromosome)
            if evo and not evo.get('error'):
                best_prompt = evo.get('best_prompt') or evo.get('evolved_prompt', query)
                result.raw_responses['evoprompt'] = evo
                result.techniques_used.append('evoprompt')

    except Exception as e:
        result.error = str(e)
        logger.error(f'Pipeline error: {e}')

    result.latency_ms = (time.time() - start) * 1000
    return result


def configure_and_run(query: str, chromosome) -> Dict:
    """Run pipeline and return results as dict (for benchmark integration)."""
    pr = run_pipeline(query, chromosome)
    return {
        'answer': pr.answer,
        'latency_ms': pr.latency_ms,
        'cost_estimate': pr.cost_estimate,
        'techniques_used': pr.techniques_used,
        'error': pr.error,
    }


if __name__ == '__main__':
    from ga_pipeline_optimizer import PipelineChromosome

    default = PipelineChromosome.balanced()
    print(f'Running pipeline with balanced config...')
    print(f'Active techniques: {[t for t, v in default.active_techniques().items() if v]}')

    result = run_pipeline("What is Thompson Sampling and why use it for model selection?", default)
    print(f'\nAnswer: {result.answer[:200]}...' if result.answer else f'\nError: {result.error}')
    print(f'Techniques used: {result.techniques_used}')
    print(f'Latency: {result.latency_ms:.0f}ms')
    print(f'Cost: ${result.cost_estimate:.6f}')
