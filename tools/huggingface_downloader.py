#!/usr/bin/env python3
"""
HUGGINGFACE DATASETS DOWNLOADER
Pre-made training datasets - ZERO API calls needed!
Millions of examples ready to use!
"""

import json
from pathlib import Path
from datetime import datetime

NAS_BASE = Path('/mnt/nas/web-scrape')
DATA_DIR = NAS_BASE / 'synthetic-data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

print("="*70)
print("HUGGINGFACE DATASETS - THE GOLDMINE!")
print("="*70)
print("")
print("To use HuggingFace datasets, install:")
print("  pip3 install datasets")
print("")
print("Then download pre-made training datasets:")
print("")

RECOMMENDED_DATASETS = [
    {
        'name': 'OpenAssistant/oasst1',
        'description': 'Conversational Q&A (161k examples)',
        'size': '161k',
        'type': 'conversation'
    },
    {
        'name': 'yahma/alpaca-cleaned',
        'description': 'Instruction following (52k examples)',
        'size': '52k',
        'type': 'instruction'
    },
    {
        'name': 'squad',
        'description': 'Reading comprehension Q&A (100k examples)',
        'size': '100k',
        'type': 'qa'
    },
    {
        'name': 'cnn_dailymail',
        'description': 'News summarization (300k examples)',
        'size': '300k',
        'type': 'summarization'
    },
    {
        'name': 'gsm8k',
        'description': 'Math word problems (8.5k examples)',
        'size': '8.5k',
        'type': 'math'
    },
    {
        'name': 'code_search_net',
        'description': 'Code documentation (2M examples)',
        'size': '2M',
        'type': 'code'
    }
]

print("RECOMMENDED DATASETS:")
print("")
for ds in RECOMMENDED_DATASETS:
    print(f"📦 {ds['name']}")
    print(f"   {ds['description']}")
    print(f"   Size: {ds['size']} examples")
    print("")

print("EXAMPLE USAGE:")
print("")
print("from datasets import load_dataset")
print("")
print("# Download OpenAssistant conversations (161k examples)")
print("dataset = load_dataset('OpenAssistant/oasst1')")
print("")
print("# Convert to our format")
print("for item in dataset['train']:")
print("    example = {")
print("        'input': item['prompt'],")
print("        'output': item['response'],")
print("        'source': 'huggingface_oasst1'")
print("    }")
print("    # Save to /mnt/nas/web-scrape/synthetic-data/")
print("")
print("="*70)
print("💡 THIS IS THE EASIEST WAY TO GET THOUSANDS OF EXAMPLES!")
print("="*70)
print("")
print("Total examples from recommended datasets: ~2.6 MILLION")
print("")
print("Next step:")
print("  1. pip3 install datasets")
print("  2. Run this script with --download flag")
print("="*70)

def download_and_convert(dataset_name, max_examples=10000):
    """Download HuggingFace dataset and convert to our format"""
    try:
        from datasets import load_dataset
    except ImportError:
        print("❌ Install datasets: pip3 install datasets")
        return 0

    print(f"\n📦 Downloading {dataset_name}...")

    try:
        dataset = load_dataset(dataset_name, split='train')

        examples = []
        count = 0

        for item in dataset:
            if count >= max_examples:
                break

            # Convert based on dataset structure
            if 'prompt' in item and 'response' in item:
                ex = {
                    'input': item['prompt'],
                    'output': item['response'],
                    'source': f'huggingface_{dataset_name.replace("/", "_")}'
                }
            elif 'question' in item and 'answer' in item:
                ex = {
                    'input': item['question'],
                    'output': item['answer'],
                    'source': f'huggingface_{dataset_name.replace("/", "_")}'
                }
            elif 'instruction' in item and 'output' in item:
                ex = {
                    'input': item['instruction'],
                    'output': item['output'],
                    'source': f'huggingface_{dataset_name.replace("/", "_")}'
                }
            else:
                continue

            examples.append(ex)
            count += 1

        # Save
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = dataset_name.replace('/', '_')
        data_file = DATA_DIR / f'huggingface_{safe_name}_{timestamp}.jsonl'

        with open(data_file, 'w') as f:
            for ex in examples:
                f.write(json.dumps(ex) + '\n')

        print(f"  ✅ Saved {len(examples)} examples to {data_file.name}")
        return len(examples)

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return 0

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--download', action='store_true', help='Actually download datasets')
    parser.add_argument('--max-examples', type=int, default=10000, help='Max examples per dataset')

    args = parser.parse_args()

    if args.download:
        print("\n🚀 DOWNLOADING DATASETS...")
        total = 0
        for ds in RECOMMENDED_DATASETS[:3]:  # Start with first 3
            count = download_and_convert(ds['name'], args.max_examples)
            total += count

        print(f"\n✅ Total downloaded: {total} examples")
