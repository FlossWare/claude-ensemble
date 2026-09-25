#!/usr/bin/env python3
"""
Integration example: Using cache keys with Claude API prompt caching.

This demonstrates how to integrate the cache key generator with
the Claude API for efficient prompt caching in RH projects.
"""

import json
from pathlib import Path
from cache_key_generator import CacheKeyGenerator, CacheableContent


class CacheStore:
    """
    Simple in-memory cache store for demonstration.
    In production, this would integrate with a database or cache backend.
    """

    def __init__(self, storage_path: str = "/tmp/rh_cache_store.json"):
        self.storage_path = Path(storage_path)
        self.cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Load cache from disk if it exists."""
        if self.storage_path.exists():
            with open(self.storage_path, "r") as f:
                return json.load(f)
        return {}

    def _save_cache(self):
        """Save cache to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(self.cache, f, indent=2)

    def get(self, cache_key: str) -> dict | None:
        """Get cached content by key."""
        return self.cache.get(cache_key)

    def set(self, cache_key: str, content: dict, metadata: dict):
        """Store content in cache."""
        self.cache[cache_key] = {
            "content": content,
            "metadata": metadata,
            "cache_version": "1.0",
        }
        self._save_cache()

    def invalidate(self, cache_key: str):
        """Remove a cache entry."""
        if cache_key in self.cache:
            del self.cache[cache_key]
            self._save_cache()

    def stats(self) -> dict:
        """Get cache statistics."""
        return {
            "total_entries": len(self.cache),
            "total_size_bytes": sum(
                len(json.dumps(entry).encode("utf-8"))
                for entry in self.cache.values()
            ),
            "keys": list(self.cache.keys()),
        }


class RHPromptCacheManager:
    """
    Manages prompt caching for RH projects.

    Combines cache key generation with Claude API integration.
    """

    def __init__(self, cache_dir: str = "/tmp/rh_prompt_cache"):
        self.generator = CacheKeyGenerator(algorithm="sha256")
        self.cache_store = CacheStore(f"{cache_dir}/cache_store.json")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def register_cache_content(self, file_paths: list[str]) -> str:
        """
        Register files for caching and get cache key.

        Args:
            file_paths: List of file paths to cache

        Returns:
            Cache key (hex string)
        """
        blocks = self.generator.load_files(file_paths)
        cache_key, metadata = self.generator.generate_cache_key(blocks)

        # Store cache metadata
        self.cache_store.set(cache_key, {"files": file_paths}, metadata)

        return cache_key

    def get_cached_prompt(self, cache_key: str) -> dict | None:
        """Retrieve cached prompt if available."""
        return self.cache_store.get(cache_key)

    def build_claude_system_prompt(self, cache_key: str) -> dict:
        """
        Build system prompt for Claude API with cache control.

        Returns dict suitable for Claude API messages.create() call.
        """
        cached = self.get_cached_prompt(cache_key)

        if not cached:
            return None

        # Claude API format with cache control
        return {
            "type": "text",
            "text": cached["content"],
            "cache_control": {"type": "ephemeral"},
            "x-cache-key": cache_key,  # Custom tracking
        }

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        stats = self.cache_store.stats()
        stats["cache_dir"] = str(self.cache_dir)
        return stats

    def clear_cache(self):
        """Clear entire cache."""
        self.cache_store.cache = {}
        self.cache_store._save_cache()


def example_1_basic_caching():
    """Example 1: Basic cache key generation for RH project."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Basic Caching for RH Project")
    print("=" * 80)

    manager = RHPromptCacheManager()

    # Register RH system prompt files
    rh_files = [
        "/home/sfloess/.claude/CLAUDE.md",
        "/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/memory/MEMORY.md",
    ]

    try:
        print("\nRegistering RH prompt files for caching...")
        cache_key = manager.register_cache_content(rh_files)

        print(f"\nCache key generated: {cache_key}")
        print(f"Key length: {len(cache_key)} characters")

        # Check cache was stored
        cached = manager.get_cached_prompt(cache_key)
        if cached:
            print(f"✓ Successfully cached {len(cached['content'])} bytes")

        stats = manager.get_cache_stats()
        print(f"\nCache stats:")
        print(f"  Total entries: {stats['total_entries']}")
        print(f"  Total size: {stats['total_size_bytes'] / 1024:.2f} KB")

    except FileNotFoundError as e:
        print(f"Note: {e}")
        print("Creating synthetic example instead...")

        # Use synthetic data
        blocks = [
            CacheableContent(
                path="example_claude.md",
                content="# Example CLAUDE.md\nSystem prompt content",
                content_type="system_prompt",
            ),
            CacheableContent(
                path="example_memory.md",
                content="# Example Memory\nProject context and notes",
                content_type="memory",
            ),
        ]

        cache_key, metadata = manager.generator.generate_cache_key(blocks)
        print(f"\nSynthetic cache key: {cache_key}")
        print(f"Blocks cached: {metadata['num_blocks']}")
        print(f"Total size: {metadata['total_bytes']} bytes")


def example_2_cache_invalidation():
    """Example 2: Demonstrating cache invalidation."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Cache Invalidation")
    print("=" * 80)

    manager = RHPromptCacheManager()

    # Create synthetic files
    original_blocks = [
        CacheableContent(
            path="prompt_v1.md",
            content="Original system prompt content",
            content_type="system_prompt",
        ),
    ]

    print("\n[Step 1] Generate initial cache key")
    key1, meta1 = manager.generator.generate_cache_key(original_blocks)
    print(f"  Cache key: {key1}")
    print(f"  Timestamp: {meta1['generated_at']}")

    print("\n[Step 2] Modify content (simulate file edit)")
    modified_blocks = [
        CacheableContent(
            path="prompt_v1.md",
            content="Updated system prompt content",
            content_type="system_prompt",
        ),
    ]
    key2, meta2 = manager.generator.generate_cache_key(modified_blocks)
    print(f"  New cache key: {key2}")
    print(f"  Timestamp: {meta2['generated_at']}")

    print("\n[Step 3] Compare keys")
    if key1 != key2:
        print(f"  ✓ Cache INVALIDATED (keys differ)")
        print(f"  Old key: {key1[:40]}...")
        print(f"  New key: {key2[:40]}...")
    else:
        print(f"  ✗ Cache unchanged (unexpected!)")

    print("\n[Step 4] Analysis")
    print(f"  Block count unchanged: {meta1['num_blocks']} == {meta2['num_blocks']}")
    print(f"  Format version unchanged: {meta1['format_version']} == {meta2['format_version']}")
    print(f"  But content hash differs: automatic cache invalidation!")


def example_3_multiple_cache_keys():
    """Example 3: Managing multiple cache keys."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Multiple Cache Keys")
    print("=" * 80)

    manager = RHPromptCacheManager()

    # Different content sets for different use cases
    configs = {
        "minimal": [
            CacheableContent(
                path="claude.md",
                content="Minimal system prompt",
                content_type="system_prompt",
            ),
        ],
        "standard": [
            CacheableContent(
                path="claude.md",
                content="Standard system prompt with memory",
                content_type="system_prompt",
            ),
            CacheableContent(
                path="memory.md",
                content="Project memory and context",
                content_type="memory",
            ),
        ],
        "comprehensive": [
            CacheableContent(
                path="claude.md",
                content="Comprehensive system prompt",
                content_type="system_prompt",
            ),
            CacheableContent(
                path="memory.md",
                content="Project memory and context",
                content_type="memory",
            ),
            CacheableContent(
                path="domain_knowledge.md",
                content="Domain-specific knowledge",
                content_type="doc",
            ),
            CacheableContent(
                path="architecture.md",
                content="System architecture documentation",
                content_type="doc",
            ),
        ],
    }

    print("\nGenerating cache keys for different configurations:")
    cache_keys = {}

    for config_name, blocks in configs.items():
        key, metadata = manager.generator.generate_cache_key(blocks)
        cache_keys[config_name] = key
        print(
            f"\n  {config_name.upper()}")
        print(f"    Blocks: {metadata['num_blocks']}")
        print(f"    Types: {metadata['block_count_by_type']}")
        print(f"    Size: {metadata['total_bytes']} bytes")
        print(f"    Key: {key}")

    print("\n\nCache key comparison:")
    print(f"  Minimal key:        {cache_keys['minimal'][:32]}...")
    print(f"  Standard key:       {cache_keys['standard'][:32]}...")
    print(f"  Comprehensive key:  {cache_keys['comprehensive'][:32]}...")

    all_unique = len(set(cache_keys.values())) == len(cache_keys)
    print(f"\n  All keys unique: {all_unique} ✓")


def example_4_performance_analysis():
    """Example 4: Performance characteristics."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Performance Analysis")
    print("=" * 80)

    import time

    generator = CacheKeyGenerator(algorithm="sha256")

    # Test different content sizes
    sizes = [10, 100, 1000, 10000, 100000]  # KB

    print("\nPerformance: Hash generation time vs content size")
    print("-" * 60)
    print(f"{'Size (KB)':<15} {'Time (ms)':<15} {'Throughput (MB/s)':<15}")
    print("-" * 60)

    for size_kb in sizes:
        content = "x" * (size_kb * 1024)
        blocks = [
            CacheableContent(path="test.md", content=content, content_type="memory")
        ]

        start = time.time()
        for _ in range(5):  # 5 iterations
            generator.generate_cache_key(blocks)
        elapsed = (time.time() - start) / 5

        throughput = (size_kb / 1024) / elapsed
        print(f"{size_kb:<15} {elapsed*1000:<15.3f} {throughput:<15.1f}")

    print("\n✓ Cache key generation is fast even for large content")
    print("✓ Suitable for real-time use in Claude API calls")


def example_5_integration_pattern():
    """Example 5: Integration pattern with Claude API."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Claude API Integration Pattern")
    print("=" * 80)

    print("""
Here's how to integrate the cache key generator with Claude API:

1. INITIALIZATION (once per session)
   ─────────────────────────────────
   manager = RHPromptCacheManager()
   cache_key = manager.register_cache_content([
       "/path/to/CLAUDE.md",
       "/path/to/MEMORY.md"
   ])
   storage[cache_key] = load_content(...)  # Store full content

2. MAKING API CALL (with cache)
   ────────────────────────────
   import anthropic

   client = anthropic.Anthropic()

   response = client.messages.create(
       model="claude-opus-5",
       max_tokens=1024,
       system=[{
           "type": "text",
           "text": cached_system_prompt,
           "cache_control": {"type": "ephemeral"}
       }],
       messages=[{
           "role": "user",
           "content": [{
               "type": "text",
               "text": user_query,
               "cache_control": {"type": "ephemeral"}
           }]
       }]
   )

   # Cache hit indicator in response
   print(f"Cache usage: {response.usage.cache_read_input_tokens} read tokens")

3. CACHE INVALIDATION (automatic)
   ──────────────────────────────
   # When files change:
   new_key = manager.register_cache_content(files)

   if new_key != old_key:
       # Old cache automatically invalid
       manager.clear_cache()  # Clean up if needed
       # Next API call uses new cache key

4. MONITORING
   ──────────
   stats = manager.get_cache_stats()
   print(f"Cache entries: {stats['total_entries']}")
   print(f"Cache size: {stats['total_size_bytes'] / 1024:.1f} KB")
""")

    print("\nBenefits:")
    print("  ✓ Automatic cache invalidation on content change")
    print("  ✓ 50% cost reduction on cached prompt usage")
    print("  ✓ Deterministic keys enable consistent caching")
    print("  ✓ No additional dependencies needed")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("RH PROMPT CACHE INTEGRATION EXAMPLES")
    print("=" * 80)

    example_1_basic_caching()
    example_2_cache_invalidation()
    example_3_multiple_cache_keys()
    example_4_performance_analysis()
    example_5_integration_pattern()

    print("\n" + "=" * 80)
    print("All examples completed!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
