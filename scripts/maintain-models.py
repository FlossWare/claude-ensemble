#!/usr/bin/env python3
"""
Model Maintenance Script
Keeps PostgreSQL api_models table up-to-date with provider APIs
"""

import requests
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

DB_CONFIG = {
    'host': 'aio-01',
    'port': 5433,
    'database': 'learning',
    'user': 'claude'
}

# Provider API endpoints to fetch current model lists
PROVIDER_APIS = {
    'openai': {
        'url': 'https://api.openai.com/v1/models',
        'key_env': 'OPENAI_API_KEY',
        'filter': lambda m: m['id'].startswith(('gpt-', 'o1-'))
    },
    'anthropic': {
        # Anthropic doesn't have a models endpoint, use hardcoded current list
        'models': ['claude-opus-4', 'claude-sonnet-4', 'claude-haiku-4', 'claude-3-5-sonnet-20241022']
    },
    'groq': {
        'url': 'https://api.groq.com/openai/v1/models',
        'key_env': 'GROQ_API_KEY'
    },
    'google': {
        # Google Gemini models (known list)
        'models': ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.5-flash-lite', 'gemini-1.5-pro', 'gemini-1.5-flash']
    },
    'cohere': {
        # Cohere models (from their docs)
        'models': ['command-r-plus-08-2024', 'command-r-08-2024', 'command-light', 'command-a-plus-05-2026']
    }
}

def get_db():
    """Connect to PostgreSQL"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def get_current_models_from_db():
    """Get all models currently in database"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT model_name, provider, enabled, notes FROM api_models ORDER BY provider, model_name")
    models = cur.fetchall()
    conn.close()
    return models

def fetch_provider_models(provider, config):
    """Fetch current model list from provider API"""
    if 'models' in config:
        # Hardcoded list
        return config['models']
    
    if 'url' not in config:
        return []
    
    try:
        headers = {}
        if 'key_env' in config:
            import os
            api_key = os.getenv(config['key_env'])
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
        
        response = requests.get(config['url'], headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = data.get('data', [])
            
            # Apply filter if provided
            if 'filter' in config:
                models = [m for m in models if config['filter'](m)]
            
            return [m['id'] if isinstance(m, dict) else m for m in models]
    except Exception as e:
        print(f"Warning: Could not fetch {provider} models: {e}")
    
    return []

def check_for_updates():
    """Check for model updates across all providers"""
    print("=" * 60)
    print("MODEL MAINTENANCE CHECK")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    print()
    
    current_models = get_current_models_from_db()
    db_by_provider = {}
    for m in current_models:
        provider = m['provider']
        if provider not in db_by_provider:
            db_by_provider[provider] = []
        db_by_provider[provider].append(m)
    
    changes = {
        'new_models': [],
        'deprecated': [],
        'enabled_count': 0,
        'total_count': len(current_models)
    }
    
    # Check each provider
    for provider, config in PROVIDER_APIS.items():
        print(f"\n{provider.upper()}:")
        print("-" * 40)
        
        # Fetch current models from provider
        provider_models = fetch_provider_models(provider, config)
        
        if not provider_models:
            print(f"  ⚠ Could not fetch models (using DB only)")
            continue
        
        # Models in DB for this provider
        db_models = db_by_provider.get(provider, [])
        db_model_names = {m['model_name'] for m in db_models}
        provider_model_set = set(provider_models)
        
        # Find new models
        new = provider_model_set - db_model_names
        if new:
            print(f"  ✓ New models available: {', '.join(sorted(new))}")
            for model_name in new:
                changes['new_models'].append((provider, model_name))
        
        # Find potentially deprecated
        deprecated = db_model_names - provider_model_set
        if deprecated:
            print(f"  ⚠ Potentially deprecated: {', '.join(sorted(deprecated))}")
            for model_name in deprecated:
                changes['deprecated'].append((provider, model_name))
        
        if not new and not deprecated:
            enabled = sum(1 for m in db_models if m['enabled'])
            print(f"  ✓ Up to date ({enabled}/{len(db_models)} enabled)")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total models in database: {changes['total_count']}")
    print(f"New models found: {len(changes['new_models'])}")
    print(f"Potentially deprecated: {len(changes['deprecated'])}")
    
    return changes

def apply_updates(changes, auto_approve=False):
    """Apply updates to database"""
    if not changes['new_models'] and not changes['deprecated']:
        print("\n✓ No changes needed")
        return
    
    print("\n" + "=" * 60)
    print("PROPOSED CHANGES")
    print("=" * 60)
    
    if changes['new_models']:
        print("\nADD NEW MODELS:")
        for provider, model in changes['new_models']:
            print(f"  + {provider}/{model}")
    
    if changes['deprecated']:
        print("\nDISABLE DEPRECATED:")
        for provider, model in changes['deprecated']:
            print(f"  - {provider}/{model}")
    
    if not auto_approve:
        response = input("\nApply changes? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled")
            return
    
    # Apply changes
    conn = get_db()
    cur = conn.cursor()
    
    try:
        for provider, model in changes['deprecated']:
            cur.execute("""
                UPDATE api_models 
                SET enabled = false, 
                    notes = COALESCE(notes || ' | ', '') || 'Auto-disabled: ' || CURRENT_DATE
                WHERE provider = %s AND model_name = %s
            """, (provider, model))
            print(f"  ✓ Disabled {provider}/{model}")
        
        for provider, model in changes['new_models']:
            # Auto-assign tier based on model name patterns
            tier = 'medium'  # default
            if any(x in model.lower() for x in ['gpt-4o', 'opus', 'pro', 'plus', 'o1-']):
                tier = 'high'
            elif any(x in model.lower() for x in ['mini', 'haiku', 'flash', 'lite', 'light', '7b', '8b', '9b']):
                tier = 'fast'
            
            cur.execute("""
                INSERT INTO api_models (model_name, provider, tier, cost_input_per_1k, cost_output_per_1k, enabled, notes)
                VALUES (%s, %s, %s, 0.001, 0.002, true, 'Auto-added: ' || CURRENT_DATE)
                ON CONFLICT (model_name) DO NOTHING
            """, (model, provider, tier))
            print(f"  ✓ Added {provider}/{model} (tier: {tier})")
        
        conn.commit()
        print(f"\n✓ Applied {len(changes['new_models']) + len(changes['deprecated'])} changes")
    
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    import sys
    
    auto = '--auto' in sys.argv or '-y' in sys.argv
    check_only = '--check' in sys.argv
    
    changes = check_for_updates()
    
    if not check_only:
        apply_updates(changes, auto_approve=auto)
