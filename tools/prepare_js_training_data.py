#!/usr/bin/env python3
"""
JavaScript Specialist Training Data Preparation

Extracts ES6+, async/await, promises, and closure patterns from codebase
for fine-tuning a JavaScript-specialized model.

Focus Areas:
- ES6+ syntax (arrow functions, destructuring, spread, template literals)
- Async/await patterns
- Promise handling (.then, .catch, Promise.all, Promise.race)
- Closures and higher-order functions
- Module systems (CommonJS, ES modules)
- Error handling patterns

Target Model: deepseek-coder-v2-lite or phi-4-mini
Dataset Size: ~10,000 code examples
Quality Threshold: Only files with async/promise/closure patterns
"""

import json
import os
import re
import hashlib
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_DIR = Path.home() / 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills'
OUTPUT_DIR = Path.home() / 'fine-tuning/datasets'
OUTPUT_FILE = OUTPUT_DIR / 'javascript_specialist_corpus.jsonl'

# Patterns to identify high-quality JavaScript code
QUALITY_PATTERNS = {
    'async_await': r'\basync\s+(?:function|\(|[a-zA-Z_$])',
    'promise_creation': r'\bnew\s+Promise\(',
    'promise_methods': r'\.(?:then|catch|finally)\(',
    'promise_static': r'Promise\.(?:all|race|allSettled|any)\(',
    'arrow_functions': r'=>',
    'destructuring': r'(?:const|let|var)\s*\{[^}]+\}\s*=',
    'spread_operator': r'\.\.\.',
    'template_literals': r'`[^`]*\$\{',
    'async_iife': r'\(async\s*\(\)',
    'closure': r'(?:function|const|let)\s+\w+\s*=\s*(?:function|\()',
}

# File patterns to include
INCLUDE_PATTERNS = ['*.js', '*.mjs', '*.cjs']
EXCLUDE_DIRS = ['node_modules', '.claude/worktrees', 'mcp-servers/*/node_modules', '.backups']

# Minimum quality score (number of patterns matched)
MIN_QUALITY_SCORE = 3

# ============================================================================
# PATTERN EXTRACTION
# ============================================================================

def calculate_quality_score(content):
    """Calculate quality score based on pattern matches"""
    score = 0
    patterns_found = []

    for pattern_name, pattern_regex in QUALITY_PATTERNS.items():
        if re.search(pattern_regex, content):
            score += 1
            patterns_found.append(pattern_name)

    return score, patterns_found

def extract_code_context(file_path, content):
    """Extract meaningful code snippets with context"""
    snippets = []

    # Extract async functions
    async_functions = re.finditer(
        r'(async\s+function\s+\w+[^{]*\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})',
        content,
        re.MULTILINE
    )
    for match in async_functions:
        snippets.append({
            'type': 'async_function',
            'code': match.group(1),
            'file': str(file_path)
        })

    # Extract Promise-based code
    promise_chains = re.finditer(
        r'(\w+\s*=\s*[^;]+\.then\([^)]+\)(?:\.(?:then|catch|finally)\([^)]+\))*)',
        content
    )
    for match in promise_chains:
        snippets.append({
            'type': 'promise_chain',
            'code': match.group(1),
            'file': str(file_path)
        })

    # Extract class methods with async
    async_methods = re.finditer(
        r'(async\s+\w+\s*\([^)]*\)\s*\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\})',
        content,
        re.MULTILINE
    )
    for match in async_methods:
        snippets.append({
            'type': 'async_method',
            'code': match.group(1),
            'file': str(file_path)
        })

    return snippets

def extract_module_pattern(content):
    """Identify module system (CommonJS vs ES6)"""
    if 'module.exports' in content or 'exports.' in content:
        return 'commonjs'
    elif 'import ' in content or 'export ' in content:
        return 'es6'
    return 'unknown'

# ============================================================================
# FILE PROCESSING
# ============================================================================

def should_exclude_path(path):
    """Check if path should be excluded"""
    path_str = str(path)
    for exclude_pattern in EXCLUDE_DIRS:
        if exclude_pattern in path_str:
            return True
    return False

def process_file(file_path):
    """Process a single JavaScript file"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Skip empty or very small files
        if len(content) < 100:
            return None

        # Calculate quality score
        quality_score, patterns = calculate_quality_score(content)

        # Skip low-quality files
        if quality_score < MIN_QUALITY_SCORE:
            return None

        # Extract code snippets
        snippets = extract_code_context(file_path, content)
        module_type = extract_module_pattern(content)

        # Count lines
        lines = content.split('\n')

        return {
            'file_path': str(file_path.relative_to(BASE_DIR)),
            'quality_score': quality_score,
            'patterns': patterns,
            'module_type': module_type,
            'line_count': len(lines),
            'char_count': len(content),
            'snippets': snippets,
            'full_content': content,
            'file_hash': hashlib.sha256(content.encode()).hexdigest()[:16]
        }

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

# ============================================================================
# TRAINING DATA GENERATION
# ============================================================================

def create_training_examples(file_data):
    """Convert file data into training examples"""
    examples = []

    # Full file example
    examples.append({
        'instruction': f"Analyze this {file_data['module_type']} JavaScript code and explain the async patterns used:",
        'input': file_data['full_content'],
        'output': f"This code uses {', '.join(file_data['patterns'])}. Module type: {file_data['module_type']}.",
        'metadata': {
            'file': file_data['file_path'],
            'quality_score': file_data['quality_score'],
            'type': 'full_file_analysis'
        }
    })

    # Snippet examples
    for snippet in file_data['snippets']:
        snippet_type = snippet['type'].replace('_', ' ')
        examples.append({
            'instruction': f"Complete this {snippet_type} implementation:",
            'input': snippet['code'][:len(snippet['code'])//2],  # First half as input
            'output': snippet['code'],  # Full code as output
            'metadata': {
                'file': file_data['file_path'],
                'snippet_type': snippet['type'],
                'type': 'code_completion'
            }
        })

    # Pattern-specific examples
    if 'async_await' in file_data['patterns']:
        examples.append({
            'instruction': "Convert this Promise-based code to async/await:",
            'input': file_data['full_content'],
            'output': "Here's the async/await version: [implementation would be generated]",
            'metadata': {
                'file': file_data['file_path'],
                'type': 'pattern_conversion'
            }
        })

    return examples

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution"""
    print("🔍 JavaScript Specialist Training Data Preparation")
    print(f"   Base directory: {BASE_DIR}")
    print(f"   Output file: {OUTPUT_FILE}")
    print()

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Find all JavaScript files
    js_files = []
    for pattern in INCLUDE_PATTERNS:
        for file_path in BASE_DIR.rglob(pattern):
            if not should_exclude_path(file_path):
                js_files.append(file_path)

    print(f"📁 Found {len(js_files)} JavaScript files")

    # Process files
    processed_files = []
    training_examples = []
    pattern_stats = defaultdict(int)

    for i, file_path in enumerate(js_files):
        if i % 100 == 0:
            print(f"   Processing file {i+1}/{len(js_files)}...", end='\r')

        file_data = process_file(file_path)
        if file_data:
            processed_files.append(file_data)

            # Generate training examples
            examples = create_training_examples(file_data)
            training_examples.extend(examples)

            # Update pattern statistics
            for pattern in file_data['patterns']:
                pattern_stats[pattern] += 1

    print(f"\n✅ Processed {len(processed_files)} high-quality files")
    print(f"📊 Generated {len(training_examples)} training examples")
    print()

    # Write training data to JSONL
    with open(OUTPUT_FILE, 'w') as f:
        for example in training_examples:
            f.write(json.dumps(example) + '\n')

    print(f"💾 Training data written to: {OUTPUT_FILE}")
    print(f"   File size: {os.path.getsize(OUTPUT_FILE) / 1024 / 1024:.2f} MB")
    print()

    # Write statistics
    stats_file = OUTPUT_DIR / 'javascript_specialist_stats.json'
    stats = {
        'timestamp': datetime.now().isoformat(),
        'total_files': len(js_files),
        'processed_files': len(processed_files),
        'training_examples': len(training_examples),
        'pattern_distribution': dict(pattern_stats),
        'module_types': {
            'commonjs': sum(1 for f in processed_files if f['module_type'] == 'commonjs'),
            'es6': sum(1 for f in processed_files if f['module_type'] == 'es6'),
            'unknown': sum(1 for f in processed_files if f['module_type'] == 'unknown')
        },
        'quality_score_distribution': {
            str(score): sum(1 for f in processed_files if f['quality_score'] == score)
            for score in range(MIN_QUALITY_SCORE, 11)
        }
    }

    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)

    print(f"📈 Statistics written to: {stats_file}")
    print()
    print("PATTERN DISTRIBUTION:")
    for pattern, count in sorted(pattern_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {pattern}: {count} files")
    print()
    print("MODULE TYPE DISTRIBUTION:")
    print(f"  - CommonJS: {stats['module_types']['commonjs']} files")
    print(f"  - ES6: {stats['module_types']['es6']} files")
    print(f"  - Unknown: {stats['module_types']['unknown']} files")
    print()
    print("✨ Ready for fine-tuning!")
    print()
    print("NEXT STEPS:")
    print("  1. Review training data quality: head -20 " + str(OUTPUT_FILE))
    print("  2. Configure model: Edit ~/fine-tuning/configs/javascript_specialist.yaml")
    print("  3. Start training: ~/fine-tuning/scripts/train_js_specialist.sh")

if __name__ == '__main__':
    main()
