#!/usr/bin/env python3
"""Categorize a memory file for the FlossWare knowledge repo.

Usage: categorize-memory.py <memory_file_path>

Reads YAML frontmatter to get the memory type, then:
- reference -> MIGRATE-REFERENCE (no AI needed)
- user, test -> SKIP (tool-specific)
- feedback, project -> calls Gemini via aio-01 for categorization

Prints a single line: CATEGORY|target_dir|filename
Example: MIGRATE-PATTERN|patterns|retry-with-backoff.md
"""
import json
import os
import re
import subprocess
import sys


def parse_frontmatter(text):
    """Extract YAML frontmatter fields from a memory file."""
    meta = {}
    if not text.startswith('---'):
        return meta, text
    end = text.find('---', 3)
    if end < 0:
        return meta, text
    fm = text[3:end]
    body = text[end + 3:].strip()
    for line in fm.strip().split('\n'):
        line = line.strip()
        if ':' in line and not line.startswith('#'):
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            meta[key] = val
    return meta, body


def get_gemini_key():
    """Get Gemini API key from orchestrator via SSH jump proxy."""
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=3', 'aio-01',
             'curl -s http://localhost:5000/secrets/PERSONAL_GOOGLE_API_KEY'],
            capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get('value')
    except Exception:
        pass
    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=3', 'aio-01',
             'curl -s http://localhost:5000/secrets/GOOGLE_API_KEY'],
            capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get('value')
    except Exception:
        pass
    return None


def categorize_with_gemini(name, description, content, mem_type):
    """Call Gemini to categorize a feedback or project memory."""
    key = get_gemini_key()
    if not key:
        # Fallback: use heuristics
        return heuristic_categorize(name, description, content, mem_type)

    prompt = f"""Categorize this memory file for migration to a knowledge repository.

Categories:
- MIGRATE-DECISION: A deliberate architectural CHOICE between alternatives.
- MIGRATE-PATTERN: A REUSABLE, validated approach to a recurring problem.
- MIGRATE-LEARNING: Something that WENT WRONG or was SURPRISING.
- MIGRATE-AGENT: Behavioral guidance applicable to ANY AI agent.
- MIGRATE-REFERENCE: Factual system/infrastructure information.
- SKIP: Tool-specific tuning, test data, or duplicates.

Memory type: {mem_type}
Name: {name}
Description: {description}
Content preview: {content[:500]}

Output ONLY one line: the category name (e.g., MIGRATE-DECISION)"""

    body = json.dumps({
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'temperature': 0.1, 'maxOutputTokens': 50}
    })

    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=3', 'aio-01',
             f"curl -s --max-time 15 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}' "
             f"-H 'Content-Type: application/json' -d '{body}'"],
            capture_output=True, text=True, timeout=25)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            text = data['candidates'][0]['content']['parts'][0]['text'].strip()
            # Extract just the category
            for cat in ['MIGRATE-DECISION', 'MIGRATE-PATTERN', 'MIGRATE-LEARNING',
                        'MIGRATE-AGENT', 'MIGRATE-REFERENCE', 'SKIP']:
                if cat in text:
                    return cat
    except Exception:
        pass

    return heuristic_categorize(name, description, content, mem_type)


def heuristic_categorize(name, description, content, mem_type):
    """Fallback heuristic when Gemini is unavailable."""
    text = (name + ' ' + description + ' ' + content).lower()

    if mem_type == 'project':
        if any(w in text for w in ['halted', 'failed', 'broke', 'issue', 'bug']):
            return 'MIGRATE-LEARNING'
        return 'MIGRATE-REFERENCE'

    # feedback type
    if any(w in text for w in ['decided', 'chose', 'switched', 'policy', 'never use', 'only use']):
        return 'MIGRATE-DECISION'
    if any(w in text for w in ['pattern', 'always', 'workflow', 'approach', 'convention']):
        return 'MIGRATE-PATTERN'
    if any(w in text for w in ['learned', 'broke', 'failed', 'mistake', 'wrong', 'caught']):
        return 'MIGRATE-LEARNING'
    if any(w in text for w in ['agent', 'should', 'must', 'prefer', 'style', 'ask before']):
        return 'MIGRATE-AGENT'

    return 'MIGRATE-REFERENCE'


CATEGORY_DIR_MAP = {
    'MIGRATE-DECISION': 'decisions',
    'MIGRATE-PATTERN': 'patterns',
    'MIGRATE-LEARNING': 'learnings',
    'MIGRATE-AGENT': 'agents',
    'MIGRATE-REFERENCE': 'reference',
}


def make_filename(name, category):
    """Generate a filename for the knowledge repo."""
    # Strip common prefixes
    clean = name
    for prefix in ['feedback_', 'reference_', 'project_', 'session_', 'learning_']:
        if clean.startswith(prefix):
            clean = clean[len(prefix):]

    # For decisions, use next available number
    if category == 'MIGRATE-DECISION':
        knowledge_dir = os.path.expanduser('~/Development/github/FlossWare/knowledge/decisions')
        existing = [f for f in os.listdir(knowledge_dir) if re.match(r'\d{4}-', f)] if os.path.isdir(knowledge_dir) else []
        next_num = max([int(f[:4]) for f in existing] + [0]) + 1
        clean = re.sub(r'[^a-z0-9_]', '-', clean.lower())
        clean = re.sub(r'-+', '-', clean).strip('-')
        return f'{next_num:04d}-{clean}.md'

    # For agents, append to operational-preferences.md (handled by caller)
    if category == 'MIGRATE-AGENT':
        return 'operational-preferences.md'

    # For everything else, kebab-case
    clean = re.sub(r'[^a-z0-9_]', '-', clean.lower())
    clean = re.sub(r'-+', '-', clean).strip('-')
    return f'{clean}.md'


def main():
    if len(sys.argv) < 2:
        print('Usage: categorize-memory.py <memory_file>', file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f'File not found: {filepath}', file=sys.stderr)
        sys.exit(1)

    text = open(filepath).read()
    meta, body = parse_frontmatter(text)

    mem_type = meta.get('type', '')
    name = meta.get('name', os.path.basename(filepath).replace('.md', ''))
    description = meta.get('description', '')

    # Fast path: skip tool-specific types
    if mem_type in ('user', 'test'):
        print(f'SKIP|skip|{name}')
        sys.exit(0)

    # Block secrets and credentials
    basename = os.path.basename(filepath).lower()
    if any(s in basename for s in ['secret', 'credential', 'password', 'token', '.env']):
        print(f'SKIP|skip|{name}')
        sys.exit(0)

    # Fast path: reference goes straight to reference/
    if mem_type == 'reference':
        fname = make_filename(name, 'MIGRATE-REFERENCE')
        print(f'MIGRATE-REFERENCE|reference|{fname}')
        sys.exit(0)

    # AI-assisted categorization for feedback and project
    category = categorize_with_gemini(name, description, body, mem_type)

    if category == 'SKIP':
        print(f'SKIP|skip|{name}')
        sys.exit(0)

    target_dir = CATEGORY_DIR_MAP.get(category, 'reference')
    fname = make_filename(name, category)
    print(f'{category}|{target_dir}|{fname}')


if __name__ == '__main__':
    main()
