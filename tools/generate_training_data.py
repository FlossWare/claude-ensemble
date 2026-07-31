#!/usr/bin/env python3
"""
Generate synthetic training data using FREE APIs
Uses Cloudflare Workers AI (unlimited free) + Mistral
"""

import json
import os
import sys
import time
import asyncio
import asyncpg
import requests
from datetime import datetime
from typing import List, Dict

# API Configuration
PERSONAL_CLOUDFLARE_ACCOUNT_ID = os.getenv('PERSONAL_CLOUDFLARE_ACCOUNT_ID', '')
PERSONAL_CLOUDFLARE_API_KEY = os.getenv('PERSONAL_CLOUDFLARE_API_KEY', '')
PERSONAL_MISTRAL_API_KEY = os.getenv('PERSONAL_MISTRAL_API_KEY')

OUTPUT_DIR = os.path.expanduser('~/.claude/ml-training/synthetic-data')

class DatasetGenerator:
    def __init__(self, output_dir=OUTPUT_DIR):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.stats = {
            'cloudflare': 0,
            'mistral': 0,
            'failed': 0
        }

    def call_cloudflare(self, prompt: str, model: str = '@cf/meta/llama-3.3-70b-instruct-fp8-fast') -> str:
        """Call Cloudflare Workers AI - FREE and UNLIMITED"""

        url = f"https://api.cloudflare.com/client/v4/accounts/{PERSONAL_CLOUDFLARE_ACCOUNT_ID}/ai/run/{model}"

        headers = {
            'Authorization': f'Bearer {PERSONAL_CLOUDFLARE_API_KEY}',
            'Content-Type': 'application/json'
        }

        payload = {
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 1024
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                data = response.json()
                self.stats['cloudflare'] += 1
                return data['result']['response']
            else:
                print(f"  ⚠ Cloudflare error {response.status_code}: {response.text[:100]}")
                self.stats['failed'] += 1
                return None

        except Exception as e:
            print(f"  ⚠ Cloudflare exception: {e}")
            self.stats['failed'] += 1
            return None

    def call_mistral(self, prompt: str) -> str:
        """Call Mistral API"""

        if not PERSONAL_MISTRAL_API_KEY:
            return None

        url = "https://api.mistral.ai/v1/chat/completions"

        headers = {
            'Authorization': f'Bearer {PERSONAL_MISTRAL_API_KEY}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': 'mistral-small-latest',
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 1024
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                data = response.json()
                self.stats['mistral'] += 1
                return data['choices'][0]['message']['content']
            else:
                print(f"  ⚠ Mistral error {response.status_code}")
                self.stats['failed'] += 1
                return None

        except Exception as e:
            print(f"  ⚠ Mistral exception: {e}")
            self.stats['failed'] += 1
            return None

    async def get_code_prompts(self, limit: int = 100) -> List[str]:
        """Extract Python code snippets to complete"""

        conn = await asyncpg.connect(
            host='aio-01',
            port=5433,
            database='learning',
            user='claude'
        )

        rows = await conn.fetch("""
            SELECT content_preview
            FROM learning.code_embeddings
            WHERE language = 'python'
            AND char_length(content_preview) > 200
            ORDER BY RANDOM()
            LIMIT $1
        """, limit)

        prompts = []
        for row in rows:
            code = row['content_preview']
            lines = code.split('\n')

            # Take first 50% as prompt
            cutoff = len(lines) // 2
            prompt_code = '\n'.join(lines[:cutoff])
            target_code = '\n'.join(lines[cutoff:])

            prompts.append({
                'prompt': f"Complete this Python code:\n\n{prompt_code}\n\n# Continue here:",
                'reference': target_code
            })

        await conn.close()
        return prompts

    async def get_kubernetes_prompts(self, limit: int = 100) -> List[str]:
        """Extract kubernetes questions from PDFs"""

        conn = await asyncpg.connect(
            host='aio-01',
            port=5433,
            database='learning',
            user='claude'
        )

        rows = await conn.fetch("""
            SELECT text_preview, pdf_path
            FROM learning.pdf_metadata
            WHERE (pdf_path ILIKE '%kubernetes%' OR pdf_path ILIKE '%k8s%')
            AND char_length(text_preview) > 500
            ORDER BY RANDOM()
            LIMIT $1
        """, limit)

        prompts = []
        for row in rows:
            text = row['text_preview'][:500]
            filename = row['pdf_path'].split('/')[-1]

            prompts.append({
                'prompt': f"Based on this excerpt from '{filename}':\n\n{text}\n\nExplain the key concepts in simple terms:",
                'reference': None
            })

        await conn.close()
        return prompts

    async def generate_dataset(self, domain: str, size: int = 100):
        """
        Generate synthetic training dataset

        Args:
            domain: 'code' or 'kubernetes'
            size: Number of examples to generate
        """

        print(f"\n{'='*70}")
        print(f"🚀 SYNTHETIC DATASET GENERATION")
        print(f"{'='*70}")
        print(f"Domain: {domain}")
        print(f"Target size: {size} examples")
        print(f"Provider: Cloudflare Workers AI (FREE)")
        print(f"{'='*70}\n")

        # Get prompts
        print(f"📝 Extracting prompts from your data...")
        if domain == 'code':
            prompts = await self.get_code_prompts(size)
        elif domain == 'kubernetes':
            prompts = await self.get_kubernetes_prompts(size)
        else:
            print(f"❌ Unknown domain: {domain}")
            return

        print(f"✓ Found {len(prompts)} prompts\n")

        # Generate completions
        dataset = []

        print(f"🤖 Generating completions with Cloudflare Llama-3.3-70B...")

        for i, prompt_data in enumerate(prompts):
            prompt = prompt_data['prompt']

            # Call Cloudflare (unlimited free!)
            completion = self.call_cloudflare(prompt)

            if completion:
                dataset.append({
                    'prompt': prompt,
                    'completion': completion,
                    'reference': prompt_data.get('reference'),
                    'provider': 'cloudflare-llama-3.3-70b',
                    'domain': domain,
                    'timestamp': datetime.utcnow().isoformat()
                })

            # Progress
            if (i + 1) % 10 == 0:
                print(f"  Progress: {i+1}/{len(prompts)} ({self.stats['cloudflare']} success, {self.stats['failed']} failed)")

            # Rate limit (be nice to free API)
            time.sleep(1)

        # Save
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"{self.output_dir}/{domain}_dataset_{len(dataset)}_{timestamp}.jsonl"

        with open(output_file, 'w') as f:
            for example in dataset:
                f.write(json.dumps(example) + '\n')

        print(f"\n{'='*70}")
        print(f"✅ DATASET GENERATION COMPLETE")
        print(f"{'='*70}")
        print(f"Examples generated: {len(dataset)}/{size}")
        print(f"Success rate: {len(dataset)/size*100:.1f}%")
        print(f"Output file: {output_file}")
        print(f"\nProvider stats:")
        print(f"  - Cloudflare: {self.stats['cloudflare']}")
        print(f"  - Mistral: {self.stats['mistral']}")
        print(f"  - Failed: {self.stats['failed']}")
        print(f"{'='*70}\n")

        # Show sample
        if dataset:
            print("📄 Sample example:")
            print(f"Prompt: {dataset[0]['prompt'][:200]}...")
            print(f"Completion: {dataset[0]['completion'][:200]}...")

        return output_file


# Main
if __name__ == '__main__':
    domain = sys.argv[1] if len(sys.argv) > 1 else 'code'
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    generator = DatasetGenerator()
    output_file = asyncio.run(generator.generate_dataset(domain, size))

    print("\n📚 Next steps:")
    print(f"1. Review dataset: cat {output_file} | jq")
    print(f"2. Generate more: python3 {__file__} {domain} 1000")
    print(f"3. Train model: python3 train_mamba.py --data {output_file}")
