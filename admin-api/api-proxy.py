#!/usr/bin/env python3
"""
Fleet API Proxy - Maximum Model Coverage with PostgreSQL Integration
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx
import hashlib
import json
import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from datetime import datetime
import time
# Auto-storage integration
import sys
sys.path.insert(0, '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tools')
try:
    from auto_storage_system import store_api_call
    AUTOSTORAGE_AVAILABLE = True
    print('✓ Auto-storage loaded')
except Exception as e:
    AUTOSTORAGE_AVAILABLE = False
    print(f'⚠ Auto-storage unavailable: {e}')


app = FastAPI(title="Fleet API Proxy")

# Database config
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'learning',
    'user': 'claude'
}

# Connection pool (global)
DB_POOL = None

# Capability tiers (hardcoded fallback)
MODEL_TIERS = {
    # Tier 1: High capability (complex reasoning, expensive)
    'high': {
        'claude-opus-4': {'provider': 'anthropic', 'cost_in': 0.015, 'cost_out': 0.075},
        'claude-sonnet-4': {'provider': 'anthropic', 'cost_in': 0.003, 'cost_out': 0.015},
        'gpt-4o': {'provider': 'openai', 'cost_in': 0.0025, 'cost_out': 0.01},
        'o1-preview': {'provider': 'openai', 'cost_in': 0.015, 'cost_out': 0.06},
        'deepseek-v4-pro': {'provider': 'deepseek', 'cost_in': 0.00014, 'cost_out': 0.00028},
        'deepseek-v4-flash': {'provider': 'deepseek', 'cost_in': 0.00014, 'cost_out': 0.00028},
        'command-r-plus': {'provider': 'cohere', 'cost_in': 0.003, 'cost_out': 0.015},
        'gemini-2.5-pro': {'provider': 'google', 'cost_in': 0.00125, 'cost_out': 0.005},
        'gemini-2.5-flash': {'provider': 'google', 'cost_in': 0.0, 'cost_out': 0.0},
        'anthropic/claude-3.5-sonnet': {'provider': 'openrouter', 'cost_in': 0.003, 'cost_out': 0.015},
        'meta-llama/llama-3.1-405b-instruct': {'provider': 'openrouter', 'cost_in': 0.003, 'cost_out': 0.003},
    },
    # Tier 2: Medium capability (general purpose, balanced)
    'medium': {
        'claude-haiku-4': {'provider': 'anthropic', 'cost_in': 0.0008, 'cost_out': 0.004},
        'llama-3.3-70b-versatile': {'provider': 'groq', 'cost_in': 0.00059, 'cost_out': 0.00079},
        'gpt-oss-120b': {'provider': 'cerebras', 'cost_in': 0.0006, 'cost_out': 0.0006},
        'gpt-4o-mini': {'provider': 'openai', 'cost_in': 0.00015, 'cost_out': 0.0006},
        'gpt-3.5-turbo': {'provider': 'openai', 'cost_in': 0.0005, 'cost_out': 0.0015},
        'o1-mini': {'provider': 'openai', 'cost_in': 0.003, 'cost_out': 0.012},
        'gemini-2.0-flash': {'provider': 'google', 'cost_in': 0.0, 'cost_out': 0.0},
        'gemini-2.5-flash-lite': {'provider': 'google', 'cost_in': 0.000075, 'cost_out': 0.0003},
        'command-r': {'provider': 'cohere', 'cost_in': 0.0005, 'cost_out': 0.0015},
        'command': {'provider': 'cohere', 'cost_in': 0.001, 'cost_out': 0.002},
        'deepseek-v4-flash': {'provider': 'deepseek', 'cost_in': 0.00014, 'cost_out': 0.00028},
        'mixtral-8x7b-32768': {'provider': 'groq', 'cost_in': 0.00024, 'cost_out': 0.00024},
        '@cf/meta/llama-3.1-70b-instruct': {'provider': 'cloudflare', 'cost_in': 0.0, 'cost_out': 0.0},
        '@cf/mistral/mistral-7b-instruct-v0.1': {'provider': 'cloudflare', 'cost_in': 0.0, 'cost_out': 0.0},
        '@cf/qwen/qwen1.5-14b-chat-awq': {'provider': 'cloudflare', 'cost_in': 0.0, 'cost_out': 0.0},
        'google/gemini-pro-1.5': {'provider': 'openrouter', 'cost_in': 0.00125, 'cost_out': 0.005},
        'qwen/qwen-2.5-72b-instruct': {'provider': 'openrouter', 'cost_in': 0.0003, 'cost_out': 0.0003},
    },
    # Tier 3: Fast (simple tasks, very cheap/free)
    'fast': {
        'llama-3.1-8b-instant': {'provider': 'groq', 'cost_in': 0.00005, 'cost_out': 0.00008},
        'gemma-4-31b': {'provider': 'cerebras', 'cost_in': 0.0001, 'cost_out': 0.0001},
        'gemma-7b-it': {'provider': 'groq', 'cost_in': 0.00007, 'cost_out': 0.00007},
        'gemma2-9b-it': {'provider': 'groq', 'cost_in': 0.0002, 'cost_out': 0.0002},
        'command-light': {'provider': 'cohere', 'cost_in': 0.0003, 'cost_out': 0.0006},
        '@cf/meta/llama-3-8b-instruct': {'provider': 'cloudflare', 'cost_in': 0.0, 'cost_out': 0.0},
        '@cf/microsoft/phi-2': {'provider': 'cloudflare', 'cost_in': 0.0, 'cost_out': 0.0},
        '@cf/tinyllama/tinyllama-1.1b-chat-v1.0': {'provider': 'cloudflare', 'cost_in': 0.0, 'cost_out': 0.0},
        '@cf/deepseek-ai/deepseek-math-7b-instruct': {'provider': 'cloudflare', 'cost_in': 0.0, 'cost_out': 0.0},
    }
}

# Embedding models (free tier only)
EMBEDDING_MODELS = {
    '@cf/baai/bge-large-en-v1.5': {
        'provider': 'cloudflare',
        'dimensions': 1024,
        'cost_per_1k': 0.0,
        'tier': 'primary'
    },
    '@cf/baai/bge-base-en-v1.5': {
        'provider': 'cloudflare',
        'dimensions': 768,
        'cost_per_1k': 0.0,
        'tier': 'primary'
    },
    'text-embedding-004': {
        'provider': 'google',
        'dimensions': 768,
        'cost_per_1k': 0.0,
        'tier': 'fallback'
    }
}

# Provider configurations
API_PROVIDERS = {
    'groq': {
        'url': 'https://api.groq.com/openai/v1/chat/completions',
        'key': os.getenv('PERSONAL_GROQ_API_KEY'),
        'format': 'openai'
    },
    'cerebras': {
        'url': 'https://api.cerebras.ai/v1/chat/completions',
        'key': os.getenv('PERSONAL_CEREBRAS_API_KEY'),
        'format': 'openai'
    },
    'openai': {
        'url': 'https://api.openai.com/v1/chat/completions',
        'key': os.getenv('PERSONAL_OPENAI_API_KEY'),
        'format': 'openai'
    },
    'deepseek': {
        'url': 'https://api.deepseek.com/v1/chat/completions',
        'key': os.getenv('PERSONAL_DEEPSEEK_API_KEY'),
        'format': 'openai'
    },
    'anthropic': {
        'url': f"https://us-east5-aiplatform.googleapis.com/v1/projects/{os.getenv('ANTHROPIC_VERTEX_PROJECT_ID', 'cloudability-it-gemini')}/locations/us-east5/publishers/anthropic/models",
        'key': None,
        'format': 'vertex',
        'project': os.getenv('ANTHROPIC_VERTEX_PROJECT_ID', 'cloudability-it-gemini'),
        'location': os.getenv('GOOGLE_CLOUD_LOCATION', 'us-east5')
    },
    'google': {
        'url': 'https://generativelanguage.googleapis.com/v1beta/models',
        'key': os.getenv('GOOGLE_API_KEY'),
        'format': 'google'
    },
    'cohere': {
        'url': 'https://api.cohere.ai/v1/chat',
        'key': os.getenv('PERSONAL_COHERE_API_KEY'),
        'format': 'cohere'
    },
    'openrouter': {
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'key': os.getenv('PERSONAL_OPENROUTER_API_KEY'),
        'format': 'openai'
    },
    'cloudflare': {
        'url': 'https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run',
        'key': os.getenv('PERSONAL_CLOUDFLARE_API_KEY'),
        'format': 'cloudflare',
        'account_id': os.getenv('PERSONAL_CLOUDFLARE_ACCOUNT_ID')
    }
}

# FIX 1: Connection pooling
def init_db_pool():
    """Initialize PostgreSQL connection pool"""
    global DB_POOL
    if DB_POOL is None:
        try:
            DB_POOL = pool.SimpleConnectionPool(
                minconn=1, maxconn=10, **DB_CONFIG, cursor_factory=RealDictCursor)
            print('✓ PostgreSQL connection pool initialized (1-10 connections)')
        except Exception as e:
            print(f'⚠ Could not initialize DB pool: {e}')

def get_db():
    """Get connection from pool"""
    if DB_POOL:
        try:
            return DB_POOL.getconn()
        except Exception as e:
            print(f'⚠ Could not get DB connection: {e}')
            return None
    return None

def return_db(conn):
    """Return connection to pool"""
    if DB_POOL and conn:
        try:
            DB_POOL.putconn(conn)
        except Exception as e:
            print(f'⚠ Could not return DB connection: {e}')

# FIX 2: Model loading from DB
def load_models_from_db():
    """Load models from PostgreSQL api_models table"""
    conn = None
    try:
        conn = get_db()
        if not conn:
            return None
        cur = conn.cursor()
        cur.execute("SELECT model_name, provider, tier, cost_input_per_1k, cost_output_per_1k FROM api_models WHERE enabled = true")
        models = {}
        for row in cur.fetchall():
            models[row['model_name']] = {
                'provider': row['provider'],
                'tier': row['tier'],
                'cost_in': float(row['cost_input_per_1k']),
                'cost_out': float(row['cost_output_per_1k'])
            }
        print(f'✓ Loaded {len(models)} models from PostgreSQL')
        return models
    except Exception as e:
        print(f'ERROR loading models from DB: {e}')
        return None
    finally:
        if conn:
            return_db(conn)

# FIX 3: Fallback mechanism
def flatten_model_tiers(tiers_dict):
    """Flatten MODEL_TIERS dict to simple model -> config mapping"""
    flat = {}
    for tier, models in tiers_dict.items():
        for model_name, config in models.items():
            flat[model_name] = {**config, 'tier': tier}
    return flat

_models_cache = None
_models_cache_time = 0
_using_fallback = False

def get_models():
    """Get models from PostgreSQL (cached 60s) or fallback to hardcoded"""
    global _models_cache, _models_cache_time, _using_fallback
    now = time.time()
    if _models_cache is None or (now - _models_cache_time) > 60:
        db_models = load_models_from_db()
        if db_models and len(db_models) > 0:
            _models_cache = db_models
            if _using_fallback:
                print('✓ Switched from fallback to PostgreSQL')
                _using_fallback = False
        else:
            if not _using_fallback:
                print('⚠ FALLBACK: Using hardcoded MODEL_TIERS')
                _using_fallback = True
            _models_cache = flatten_model_tiers(MODEL_TIERS)
        _models_cache_time = now
    return _models_cache

# FIX 4: Wire up get_models()
def get_model_tier(model: str):
    """Get tier and config for a model (from PostgreSQL or fallback)"""
    models = get_models()
    if model in models:
        config = models[model]
        return config.get('tier'), config
    return None, None

def get_fallback_model(requested_model: str, failed_provider: str):
    """Get same-tier fallback model on different provider"""
    tier, _ = get_model_tier(requested_model)
    if not tier:
        return None, None

    models = get_models()
    candidates = [
        (model, config)
        for model, config in models.items()
        if config.get('tier') == tier and config['provider'] != failed_provider
    ]

    if candidates:
        return candidates[0]

    return None, None

def init_db():
    """Check tables exist (created by DBA)"""
    conn = get_db()
    if conn:
        return_db(conn)

def hash_request(model: str, messages: list) -> str:
    """Generate cache key from request"""
    content = json.dumps({'model': model, 'messages': messages}, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()

def get_cached_response(request_hash: str):
    """Get cached response if exists"""
    conn = None
    try:
        conn = get_db()
        if not conn:
            return None
        cur = conn.cursor()

        cur.execute("""
            SELECT response FROM api_cache WHERE request_hash = %s
        """, (request_hash,))

        result = cur.fetchone()

        if result:
            # Update hit count
            cur.execute("""
                UPDATE api_cache
                SET hit_count = hit_count + 1, last_hit = NOW()
                WHERE request_hash = %s
            """, (request_hash,))
            conn.commit()
            return result['response']

        return None
    except Exception as e:
        print(f"Cache read error: {e}")
        return None
    finally:
        if conn:
            return_db(conn)

def cache_response(request_hash: str, model: str, messages: list, response: dict, provider: str):
    """Cache API response"""
    conn = None
    try:
        conn = get_db()
        if not conn:
            return
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO api_cache (request_hash, model, messages, response, provider)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (request_hash) DO UPDATE SET
                hit_count = api_cache.hit_count + 1,
                last_hit = NOW()
        """, (request_hash, model, json.dumps(messages), json.dumps(response), provider))
        conn.commit()
    except Exception as e:
        print(f"Cache write error: {e}")
    finally:
        if conn:
            return_db(conn)

def log_usage(worker_id: str, provider: str, model: str, prompt_tokens: int,
              completion_tokens: int, cost_usd: float, cached: bool, latency_ms: int):
    """Log API usage for cost tracking"""
    conn = None
    try:
        conn = get_db()
        if not conn:
            return
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO api_usage
            (worker_id, provider, model, prompt_tokens, completion_tokens, cost_usd, cached, latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (worker_id, provider, model, prompt_tokens, completion_tokens, cost_usd, cached, latency_ms))
        conn.commit()
    except Exception as e:
        print(f"Logging error: {e}")
    finally:
        if conn:
            return_db(conn)

def log_failure(worker_id: str, requested_model: str, requested_provider: str,
                failure_reason: str, fallback_model: str, fallback_provider: str,
                fallback_successful: bool, http_status: int, error_message: str):
    """Log API failure and fallback attempt"""
    conn = None
    try:
        conn = get_db()
        if not conn:
            return
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO api_failures
            (worker_id, requested_model, requested_provider, failure_reason,
             fallback_model, fallback_provider, fallback_successful, http_status, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (worker_id, requested_model, requested_provider, failure_reason,
              fallback_model, fallback_provider, fallback_successful, http_status, error_message))
        conn.commit()
    except Exception as e:
        print(f"Failure logging error: {e}")
    finally:
        if conn:
            return_db(conn)

def hash_embedding_request(model: str, input_text: str) -> str:
    """Generate cache key for embedding request"""
    content = json.dumps({'model': model, 'input': input_text}, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()

def log_embedding_usage(worker_id: str, provider: str, model: str, input_tokens: int,
                        dimensions: int, cost_usd: float, cached: bool, latency_ms: int):
    """Log embedding usage"""
    conn = None
    try:
        conn = get_db()
        if not conn:
            return
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO api_embedding_usage
            (worker_id, provider, model, input_tokens, dimensions, cost_usd, cached, latency_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (worker_id, provider, model, input_tokens, dimensions, cost_usd, cached, latency_ms))
        conn.commit()
    except Exception as e:
        print(f"Embedding logging error: {e}")
    finally:
        if conn:
            return_db(conn)

def get_embedding_fallback(requested_model: str, failed_provider: str):
    """Get fallback embedding model"""
    fallbacks = [(m, c) for m, c in EMBEDDING_MODELS.items()
                 if c['provider'] != failed_provider and c['tier'] == 'fallback']
    if fallbacks:
        return fallbacks[0]
    return None, None

async def call_embedding_provider(client: httpx.AsyncClient, provider_name: str, model: str, input_text: str):
    """Call embedding API"""
    provider_config = API_PROVIDERS[provider_name]

    if provider_name == 'cloudflare':
        base_url = provider_config['url'].format(account_id=provider_config['account_id'])
        url = f"{base_url}/{model}"
        request_body = {'text': input_text}
        headers = {
            'Authorization': f"Bearer {provider_config['key']}",
            'Content-Type': 'application/json'
        }
    elif provider_name == 'google':
        url = f"{provider_config['url']}/{model}:embedContent?key={provider_config['key']}"
        request_body = {'content': {'parts': [{'text': input_text}]}}
        headers = {'Content-Type': 'application/json'}
    else:
        return None

    response = await client.post(url, headers=headers, json=request_body)

    if response.status_code == 200:
        result = response.json()
        if provider_name == 'cloudflare':
            embedding = result.get('result', {}).get('data', [[]])[0]
            return {'embedding': embedding, 'dimensions': len(embedding)}
        elif provider_name == 'google':
            embedding = result.get('embedding', {}).get('values', [])
            return {'embedding': embedding, 'dimensions': len(embedding)}

    return None

def convert_to_openai_format(messages: list, provider_format: str):
    """Convert messages to provider-specific format"""
    if provider_format == 'openai':
        return messages
    elif provider_format == 'cohere':
        if not messages:
            return {'message': '', 'chat_history': []}
        return {
            'message': messages[-1]['content'],
            'chat_history': [{'role': m['role'], 'message': m['content']} for m in messages[:-1]]
        }
    elif provider_format == 'google':
        return {'contents': [{'role': m['role'], 'parts': [{'text': m['content']}]} for m in messages]}
    else:
        return messages

def convert_from_provider_format(response: dict, provider_format: str):
    """Convert provider response to OpenAI format"""
    if provider_format == 'openai':
        return response
    elif provider_format == 'cohere':
        return {
            'choices': [{'message': {'role': 'assistant', 'content': response.get('text', '')}}],
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0}
        }
    elif provider_format == 'google':
        content = response.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        return {
            'choices': [{'message': {'role': 'assistant', 'content': content}}],
            'usage': response.get('usageMetadata', {})
        }
    elif provider_format == 'cloudflare':
        return {
            'choices': [{'message': {'role': 'assistant', 'content': response.get('result', {}).get('response', '')}}],
            'usage': {'prompt_tokens': 0, 'completion_tokens': 0}
        }
    else:
        return response

async def call_provider(client: httpx.AsyncClient, provider_name: str, model: str, body: dict):
    """Call a specific provider with proper format conversion"""
    provider_config = API_PROVIDERS[provider_name]
    provider_format = provider_config.get('format', 'openai')

    if provider_format == 'openai':
        request_body = body
        url = provider_config['url']
    elif provider_format == 'cohere':
        converted = convert_to_openai_format(body['messages'], 'cohere')
        request_body = {**converted, 'model': model}
        url = provider_config['url']
    elif provider_format == 'google':
        url = f"{provider_config['url']}/{model}:generateContent?key={provider_config['key']}"
        request_body = convert_to_openai_format(body['messages'], 'google')
    elif provider_format == 'cloudflare':
        url = f"{provider_config['url']}/{model}"
        request_body = {'messages': body['messages']}
    elif provider_format == 'vertex':
        url = f"{provider_config['url']}/{model}:streamRawPredict"
        request_body = {
            'anthropic_version': 'vertex-2023-10-16',
            'messages': body['messages'],
            'max_tokens': body.get('max_tokens', 1024)
        }
    else:
        request_body = body
        url = provider_config['url']

    headers = {'Content-Type': 'application/json'}
    if provider_config.get('key'):
        if provider_format == 'cloudflare':
            headers['Authorization'] = f"Bearer {provider_config['key']}"
        else:
            headers['Authorization'] = f"Bearer {provider_config['key']}"

    response = await client.post(url, headers=headers, json=request_body)

    if response.status_code == 200:
        result = response.json()
        return convert_from_provider_format(result, provider_format)
    else:
        return None

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Proxy endpoint with tier-based fallback"""
    start_time = time.time()

    body = await request.json()
    model = body.get('model', 'llama-3.3-70b-versatile')
    messages = body.get('messages', [])

    worker_id = request.headers.get('X-Worker-ID', request.client.host)

    request_hash = hash_request(model, messages)

    cached_response = get_cached_response(request_hash)
    if cached_response:
        latency_ms = int((time.time() - start_time) * 1000)
        log_usage(worker_id, 'cache', model, 0, 0, 0, True, latency_ms)

        # Auto-storage for cached responses
        if AUTOSTORAGE_AVAILABLE:
            try:
                store_api_call({
                    'messages': messages,
                    'response': cached_response.get('choices', [{}])[0].get('message', {}),
                    'model': model,
                    'provider': 'cache',
                    'worker_id': worker_id,
                    'prompt_tokens': 0,
                    'completion_tokens': 0,
                    'cost_usd': 0.0,
                    'latency_ms': latency_ms,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                print(f"[autostorage-cache] ERROR: {e}")
                import traceback
                traceback.print_exc()
        return JSONResponse(content=cached_response)

    tier, model_config = get_model_tier(model)
    if not model_config:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model}")

    primary_provider = model_config['provider']
    provider_config = API_PROVIDERS.get(primary_provider)

    if not provider_config:
        raise HTTPException(status_code=503, detail=f"Provider {primary_provider} not configured")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            result = await call_provider(client, primary_provider, model, body)

            if result:
                usage = result.get('usage', {})
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0)
                cost_usd = (
                    (prompt_tokens / 1000) * model_config['cost_in'] +
                    (completion_tokens / 1000) * model_config['cost_out']
                )

                cache_response(request_hash, model, messages, result, primary_provider)

                latency_ms = int((time.time() - start_time) * 1000)
                log_usage(worker_id, primary_provider, model, prompt_tokens, completion_tokens, cost_usd, False, latency_ms)
                # Auto-storage
                if AUTOSTORAGE_AVAILABLE:
                    print(f"[autostorage] Storing API call for worker={worker_id}, model={model}")
                    try:
                        store_api_call({
                            'messages': messages, 'response': result.get('choices', [{}])[0].get('message', {}).get('content', ''),
                            'model': model, 'provider': primary_provider, 'worker_id': worker_id,
                            'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens,
                            'cost_usd': cost_usd, 'latency_ms': latency_ms, 'timestamp': datetime.now().isoformat()
                        })
                    except Exception as e: print(f"[autostorage] Error: {e}")


                return JSONResponse(content=result, headers={
                    'X-Actual-Model': model,
                    'X-Provider': primary_provider
                })

            failure_reason = "API returned error"
            error_msg = "Provider returned null response"

            fallback_model, fallback_config = get_fallback_model(model, primary_provider)

            if not fallback_model:
                log_failure(worker_id, model, primary_provider, failure_reason,
                           None, None, False, 0, error_msg)
                raise HTTPException(status_code=503,
                                   detail=f"{primary_provider} failed, no same-tier fallback available")

            fallback_provider_name = fallback_config['provider']

            print(f"⚠ {model} on {primary_provider} failed, trying {fallback_model} on {fallback_provider_name}")

            fallback_result = await call_provider(client, fallback_provider_name, fallback_model, body)

            if fallback_result:
                usage = fallback_result.get('usage', {})
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0)
                cost_usd = (
                    (prompt_tokens / 1000) * fallback_config['cost_in'] +
                    (completion_tokens / 1000) * fallback_config['cost_out']
                )

                log_failure(worker_id, model, primary_provider, failure_reason,
                           fallback_model, fallback_provider_name, True, 0, error_msg)

                cache_response(request_hash, fallback_model, messages, fallback_result, fallback_provider_name)

                latency_ms = int((time.time() - start_time) * 1000)
                log_usage(worker_id, fallback_provider_name, fallback_model,
                         prompt_tokens, completion_tokens, cost_usd, False, latency_ms)

                return JSONResponse(content=fallback_result, headers={
                    'X-Actual-Model': fallback_model,
                    'X-Provider': fallback_provider_name,
                    'X-Fallback-From': f"{model}@{primary_provider}",
                    'X-Fallback-Reason': failure_reason
                })
            else:
                log_failure(worker_id, model, primary_provider, failure_reason,
                           fallback_model, fallback_provider_name, False, 0, "Both providers failed")
                raise HTTPException(status_code=503,
                                   detail=f"Both {primary_provider} and {fallback_provider_name} failed")

        except httpx.TimeoutException as e:
            fallback_model, fallback_config = get_fallback_model(model, primary_provider)

            if fallback_model:
                fallback_provider_name = fallback_config['provider']
                log_failure(worker_id, model, primary_provider, "timeout",
                           fallback_model, fallback_provider_name, False, 0, str(e))
            else:
                log_failure(worker_id, model, primary_provider, "timeout",
                           None, None, False, 0, str(e))

            raise HTTPException(status_code=504, detail=f"Provider timeout: {str(e)}")

        except Exception as e:
            log_failure(worker_id, model, primary_provider, "exception",
                       None, None, False, 0, str(e)[:500])
            raise HTTPException(status_code=502, detail=f"Provider error: {str(e)}")

@app.post("/v1/embeddings")
async def embeddings(request: Request):
    """Embeddings endpoint with tier-based fallback"""
    start_time = time.time()

    body = await request.json()
    input_text = body.get('input', '')
    model = body.get('model', '@cf/baai/bge-large-en-v1.5')

    worker_id = request.headers.get('X-Worker-ID', request.client.host)
    request_hash = hash_embedding_request(model, input_text)

    cached_response = get_cached_response(request_hash)
    if cached_response:
        latency_ms = int((time.time() - start_time) * 1000)
        cached_data = json.loads(cached_response) if isinstance(cached_response, str) else cached_response
        log_embedding_usage(worker_id, 'cache', model, 0, cached_data.get('dimensions', 0), 0, True, latency_ms)
        return JSONResponse(content=cached_data)

    model_config = EMBEDDING_MODELS.get(model)
    if not model_config:
        raise HTTPException(status_code=400, detail=f"Unknown embedding model: {model}")

    primary_provider = model_config['provider']

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            result = await call_embedding_provider(client, primary_provider, model, input_text)

            if result:
                dimensions = result['dimensions']
                input_tokens = len(input_text.split())
                cost_usd = (input_tokens / 1000) * model_config['cost_per_1k']

                response_data = {
                    'object': 'list',
                    'data': [{'object': 'embedding', 'embedding': result['embedding'], 'index': 0}],
                    'model': model,
                    'usage': {'prompt_tokens': input_tokens, 'total_tokens': input_tokens},
                    'dimensions': dimensions
                }
                cache_response(request_hash, model, [input_text], response_data, primary_provider)

                latency_ms = int((time.time() - start_time) * 1000)
                log_embedding_usage(worker_id, primary_provider, model, input_tokens, dimensions, cost_usd, False, latency_ms)

                return JSONResponse(content=response_data, headers={
                    'X-Actual-Model': model,
                    'X-Provider': primary_provider
                })

            fallback_model, fallback_config = get_embedding_fallback(model, primary_provider)

            if not fallback_model:
                log_failure(worker_id, model, primary_provider, "API error", None, None, False, 0, "No fallback")
                raise HTTPException(status_code=503, detail=f"{primary_provider} failed, no fallback available")

            fallback_provider = fallback_config['provider']
            print(f"⚠ {model} on {primary_provider} failed, trying {fallback_model} on {fallback_provider}")

            fallback_result = await call_embedding_provider(client, fallback_provider, fallback_model, input_text)

            if fallback_result:
                dimensions = fallback_result['dimensions']
                input_tokens = len(input_text.split())
                cost_usd = (input_tokens / 1000) * fallback_config['cost_per_1k']

                response_data = {
                    'object': 'list',
                    'data': [{'object': 'embedding', 'embedding': fallback_result['embedding'], 'index': 0}],
                    'model': fallback_model,
                    'usage': {'prompt_tokens': input_tokens, 'total_tokens': input_tokens},
                    'dimensions': dimensions
                }

                log_failure(worker_id, model, primary_provider, "API error", fallback_model, fallback_provider, True, 0, "Fallback succeeded")
                cache_response(request_hash, fallback_model, [input_text], response_data, fallback_provider)

                latency_ms = int((time.time() - start_time) * 1000)
                log_embedding_usage(worker_id, fallback_provider, fallback_model, input_tokens, dimensions, cost_usd, False, latency_ms)

                return JSONResponse(content=response_data, headers={
                    'X-Actual-Model': fallback_model,
                    'X-Provider': fallback_provider,
                    'X-Fallback-From': f"{model}@{primary_provider}"
                })
            else:
                log_failure(worker_id, model, primary_provider, "API error", fallback_model, fallback_provider, False, 0, "Both failed")
                raise HTTPException(status_code=503, detail="Both embedding providers failed")

        except Exception as e:
            log_failure(worker_id, model, primary_provider, "exception", None, None, False, 0, str(e)[:500])
            raise HTTPException(status_code=502, detail=f"Embedding error: {str(e)}")

@app.get("/stats")
async def get_stats():
    """Get usage statistics"""
    conn = None
    try:
        conn = get_db()
        if not conn:
            return {"error": "Database unavailable"}
        cur = conn.cursor()

        cur.execute("""
            SELECT
                worker_id,
                SUM(cost_usd) as total_cost,
                COUNT(*) as total_requests,
                SUM(CASE WHEN cached THEN 1 ELSE 0 END) as cached_requests
            FROM api_usage
            GROUP BY worker_id
            ORDER BY total_cost DESC
        """)
        usage_stats = cur.fetchall()

        cur.execute("""
            SELECT
                requested_provider,
                COUNT(*) as total_failures,
                SUM(CASE WHEN fallback_successful THEN 1 ELSE 0 END) as successful_fallbacks,
                COUNT(DISTINCT failure_reason) as unique_errors
            FROM api_failures
            WHERE timestamp > NOW() - INTERVAL '24 hours'
            GROUP BY requested_provider
            ORDER BY total_failures DESC
        """)
        failure_stats = cur.fetchall()

        return {
            "usage_by_worker": usage_stats,
            "failures_24h": failure_stats
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        if conn:
            return_db(conn)

@app.get("/health")
async def health():
    """Health check"""
    models = get_models()
    tier_counts = {}
    for model_name, config in models.items():
        tier = config.get('tier', 'unknown')
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    return {
        "status": "ok",
        "providers": list(API_PROVIDERS.keys()),
        "total_models": len(models),
        "models_by_tier": tier_counts,
        "db_status": "fallback" if _using_fallback else "postgresql"
    }

@app.on_event("startup")
async def startup():
    """Initialize on startup"""
    init_db_pool()
    init_db()
    
    models = get_models()
    tier_counts = {}
    for model_name, config in models.items():
        tier = config.get('tier', 'unknown')
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    print(f"✓ API Proxy started ({len(API_PROVIDERS)} providers, {len(models)} models)")
    print(f"✓ Providers: {', '.join(API_PROVIDERS.keys())}")
    for tier, count in tier_counts.items():
        print(f"✓ {tier.capitalize()} tier: {count} models")
    print(f"✓ Cache: PostgreSQL on {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"✓ Failure tracking enabled")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
