#!/usr/bin/env python3
"""
Synthetic Dataset Generator
Uses FREE APIs to create training data for CPU model training

Strategy:
1. Generate prompts from your data (PDFs, code, workflows)
2. Get completions from FREE APIs (Gemini, Cloudflare, Mistral)
3. Store high-quality examples for training
4. Train small model to replicate API outputs
"""

import json
import os
import time
import asyncio
import asyncpg
from typing import List, Dict
from datetime import datetime

# API clients
import google.generativeai as genai
from anthropic import Anthropic

# Configure free APIs
GEMINI_API_KEY = os.getenv('GOOGLE_API_KEY')
PERSONAL_CLOUDFLARE_ACCOUNT_ID = os.getenv('PERSONAL_CLOUDFLARE_ACCOUNT_ID')
PERSONAL_CLOUDFLARE_API_KEY = os.getenv('PERSONAL_CLOUDFLARE_API_KEY')

# Gemini is FREE: 1500 requests/day
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

class SyntheticDatasetGenerator:
    """Generate training data using free LLM APIs"""

    def __init__(self, output_dir: str = '/tmp/synthetic_dataset'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # Rate limits
        self.gemini_daily_limit = 1500
        self.gemini_requests_today = 0
        self.reset_time = None

    async def get_source_prompts(self, domain: str, count: int = 1000) -> List[str]:
        """
        Extract prompts from your existing data

        Domains:
        - code: From learning.code_embeddings
        - kubernetes: From PDFs (k8s subset)
        - docs: From documentation
        - sql: From database examples
        """

        conn = await asyncpg.connect(
            host='aio-01',
            port=5433,
            database='learning',
            user='claude'
        )

        prompts = []

        if domain == 'code':
            # Get incomplete code snippets
            rows = await conn.fetch("""
                SELECT content_preview
                FROM learning.code_embeddings
                WHERE language = 'python'
                ORDER BY RANDOM()
                LIMIT $1
            """, count)

            for row in rows:
                code = row['content_preview']
                # Truncate to create prompt
                lines = code.split('\n')
                prompt = '\n'.join(lines[:len(lines)//2])
                prompts.append(prompt)

        elif domain == 'kubernetes':
            # Get k8s questions from PDFs
            rows = await conn.fetch("""
                SELECT text_preview
                FROM learning.pdf_metadata
                WHERE pdf_path LIKE '%kubernetes%'
                OR pdf_path LIKE '%k8s%'
                ORDER BY RANDOM()
                LIMIT $1
            """, count)

            for row in rows:
                # Extract sentences, make questions
                text = row['text_preview']
                # Use first part as context, ask to explain
                prompt = f"Explain: {text[:200]}"
                prompts.append(prompt)

        await conn.close()
        return prompts

    def generate_with_gemini(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Generate completion using Gemini Flash (FREE)

        Rate limit: 1500 requests/day
        """

        # Check rate limit
        if self.gemini_requests_today >= self.gemini_daily_limit:
            print(f"⚠️  Hit Gemini daily limit, waiting until reset...")
            return None

        try:
            response = gemini_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=1000
                )
            )

            self.gemini_requests_today += 1

            return response.text

        except Exception as e:
            print(f"Gemini error: {e}")
            return None

    def generate_with_cloudflare(self, prompt: str) -> str:
        """
        Generate completion using Cloudflare Workers AI (FREE)

        Model: Llama-3.3-70B
        """
        import requests

        url = f"https://api.cloudflare.com/client/v4/accounts/{PERSONAL_CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast"

        headers = {
            'Authorization': f'Bearer {PERSONAL_CLOUDFLARE_API_KEY}',
            'Content-Type': 'application/json'
        }

        payload = {
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': 1000
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                data = response.json()
                return data['result']['response']
            else:
                print(f"Cloudflare error: {response.status_code}")
                return None

        except Exception as e:
            print(f"Cloudflare error: {e}")
            return None

    async def generate_dataset(self, domain: str, size: int = 10000):
        """
        Generate complete training dataset

        Strategy:
        - Use Gemini (1500/day) for primary generation
        - Use Cloudflare for overflow
        - Store all examples with metadata
        """

        print(f"\n🚀 Generating {size} examples for '{domain}'...")

        # Get source prompts
        print("📝 Extracting prompts from your data...")
        prompts = await self.get_source_prompts(domain, size)
        print(f"✓ Found {len(prompts)} prompts")

        # Generate completions
        dataset = []
        gemini_count = 0
        cloudflare_count = 0

        for i, prompt in enumerate(prompts):
            # Use Gemini first (better quality)
            completion = self.generate_with_gemini(prompt)

            if completion:
                provider = 'gemini-1.5-flash'
                gemini_count += 1
            else:
                # Fallback to Cloudflare
                completion = self.generate_with_cloudflare(prompt)
                provider = 'cloudflare-llama-3.3-70b'
                cloudflare_count += 1

            if completion:
                dataset.append({
                    'prompt': prompt,
                    'completion': completion,
                    'provider': provider,
                    'domain': domain,
                    'timestamp': datetime.utcnow().isoformat()
                })

            # Progress
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i+1}/{len(prompts)} (Gemini: {gemini_count}, Cloudflare: {cloudflare_count})")

            # Rate limit
            time.sleep(0.5)  # Don't hammer APIs

        # Save dataset
        output_file = f"{self.output_dir}/{domain}_dataset_{size}.jsonl"
        with open(output_file, 'w') as f:
            for example in dataset:
                f.write(json.dumps(example) + '\n')

        print(f"\n✅ Generated {len(dataset)} examples")
        print(f"📁 Saved to: {output_file}")
        print(f"📊 Stats:")
        print(f"  - Gemini: {gemini_count} ({gemini_count/len(dataset)*100:.1f}%)")
        print(f"  - Cloudflare: {cloudflare_count} ({cloudflare_count/len(dataset)*100:.1f}%)")

        return output_file


class MultiProviderDistillation:
    """
    Use MULTIPLE free APIs to create diverse training data

    Strategy: Ensemble distillation
    - Same prompt → 3 different APIs
    - Keep all 3 completions
    - Model learns from diverse perspectives
    """

    def __init__(self):
        self.providers = {
            'gemini': self.call_gemini,
            'cloudflare': self.call_cloudflare,
            'mistral': self.call_mistral  # If you have free credits
        }

    def call_gemini(self, prompt):
        """Gemini Flash - FREE"""
        response = gemini_model.generate_content(prompt)
        return response.text

    def call_cloudflare(self, prompt):
        """Cloudflare Llama-3.3-70B - FREE"""
        # Implementation from above
        pass

    def call_mistral(self, prompt):
        """Mistral (if free tier available)"""
        # Implementation
        pass

    def distill_prompt(self, prompt: str) -> List[Dict]:
        """
        Get completions from ALL providers

        Returns:
        [
            {'provider': 'gemini', 'completion': '...'},
            {'provider': 'cloudflare', 'completion': '...'},
            {'provider': 'mistral', 'completion': '...'}
        ]
        """

        results = []

        for provider_name, provider_fn in self.providers.items():
            try:
                completion = provider_fn(prompt)
                results.append({
                    'provider': provider_name,
                    'completion': completion
                })
            except Exception as e:
                print(f"  {provider_name} failed: {e}")

        return results


# CLI Usage
if __name__ == '__main__':
    import sys

    generator = SyntheticDatasetGenerator()

    # Generate dataset
    domain = sys.argv[1] if len(sys.argv) > 1 else 'code'
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

    asyncio.run(generator.generate_dataset(domain, size))

    print("\n📚 Next steps:")
    print("1. Review the generated dataset")
    print("2. Filter low-quality examples")
    print("3. Train your CPU model with:")
    print(f"   python train_mamba.py --data /tmp/synthetic_dataset/{domain}_dataset_{size}.jsonl")
