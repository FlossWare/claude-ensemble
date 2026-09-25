#!/usr/bin/env python3
"""
Comprehensive test suite for the cache key generator.

Tests include:
- Deterministic output verification
- Edge cases (empty content, special characters)
- Performance characteristics
- Algorithm comparison (MD5 vs SHA256)
"""

import time
from cache_key_generator import CacheKeyGenerator, CacheableContent


def test_determinism():
    """Test that same input always produces same output."""
    print("\n[TEST] Determinism: Same input → Same output")
    print("-" * 60)

    generator = CacheKeyGenerator(algorithm="sha256")
    blocks = [
        CacheableContent(
            path="test.md",
            content="Test content for determinism",
            content_type="memory",
        ),
        CacheableContent(
            path="test2.md",
            content="More test content",
            content_type="doc",
        ),
    ]

    # Generate key 20 times
    keys = []
    for i in range(20):
        key, _ = generator.generate_cache_key(blocks)
        keys.append(key)

    # Check all identical
    unique_count = len(set(keys))
    passed = unique_count == 1

    print(f"  Iterations: 20")
    print(f"  Unique keys: {unique_count}")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")

    return passed


def test_content_sensitivity():
    """Test that small content changes produce different keys."""
    print("\n[TEST] Content Sensitivity: Small change → Different key")
    print("-" * 60)

    generator = CacheKeyGenerator(algorithm="sha256")

    # Original
    blocks_original = [
        CacheableContent(
            path="content.md", content="Original content", content_type="memory"
        )
    ]
    key1, _ = generator.generate_cache_key(blocks_original)

    # Change one character
    blocks_modified = [
        CacheableContent(
            path="content.md", content="Original conten", content_type="memory"
        )
    ]
    key2, _ = generator.generate_cache_key(blocks_modified)

    # Keys should be different
    passed = key1 != key2

    print(f"  Original key: {key1[:32]}...")
    print(f"  Modified key: {key2[:32]}...")
    print(f"  Keys different: {passed}")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")

    return passed


def test_order_independence():
    """Test that block order doesn't matter (blocks are sorted)."""
    print("\n[TEST] Order Independence: Block order doesn't affect key")
    print("-" * 60)

    generator = CacheKeyGenerator(algorithm="sha256")

    block_a = CacheableContent(
        path="a.md", content="Content A", content_type="memory"
    )
    block_b = CacheableContent(
        path="b.md", content="Content B", content_type="memory"
    )
    block_c = CacheableContent(
        path="c.md", content="Content C", content_type="memory"
    )

    # Different orders
    blocks_order1 = [block_a, block_b, block_c]
    key1, _ = generator.generate_cache_key(blocks_order1)

    blocks_order2 = [block_c, block_a, block_b]
    key2, _ = generator.generate_cache_key(blocks_order2)

    blocks_order3 = [block_b, block_c, block_a]
    key3, _ = generator.generate_cache_key(blocks_order3)

    # All should be identical
    all_identical = key1 == key2 == key3
    passed = all_identical

    print(f"  Order 1 (a,b,c): {key1[:32]}...")
    print(f"  Order 2 (c,a,b): {key2[:32]}...")
    print(f"  Order 3 (b,c,a): {key3[:32]}...")
    print(f"  All identical: {all_identical}")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")

    return passed


def test_unicode_handling():
    """Test that Unicode content is handled correctly."""
    print("\n[TEST] Unicode Handling: Special characters → Deterministic")
    print("-" * 60)

    generator = CacheKeyGenerator(algorithm="sha256")

    unicode_content = """
    Test with special characters:
    - Emoji: 🚀 🎯 ✅
    - Accents: café, naïve, résumé
    - CJK: 日本語, 中文, 한국어
    - Math: ∑ ∏ ∫ √ ∞
    - Symbols: © ® ™ € £ ¥
    """

    blocks = [
        CacheableContent(
            path="unicode.md", content=unicode_content, content_type="memory"
        )
    ]

    # Generate multiple times
    keys = [generator.generate_cache_key(blocks)[0] for _ in range(5)]

    # All should be identical
    all_identical = len(set(keys)) == 1
    passed = all_identical

    print(f"  5 iterations: {len(set(keys))} unique key(s)")
    print(f"  Sample key: {keys[0][:32]}...")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")

    return passed


def test_empty_content():
    """Test edge case of empty content."""
    print("\n[TEST] Edge Case: Empty content block")
    print("-" * 60)

    generator = CacheKeyGenerator(algorithm="sha256")

    blocks = [
        CacheableContent(path="empty.md", content="", content_type="memory")
    ]

    try:
        key, metadata = generator.generate_cache_key(blocks)
        passed = True
        print(f"  Empty block handled: ✓")
        print(f"  Generated key: {key[:32]}...")
        print(f"  Total bytes: {metadata['total_bytes']}")
    except Exception as e:
        passed = False
        print(f"  Error with empty block: {e}")

    print(f"  Result: {'PASS' if passed else 'FAIL'}")

    return passed


def test_large_content():
    """Test performance with large content blocks."""
    print("\n[TEST] Performance: Large content (10MB total)")
    print("-" * 60)

    generator = CacheKeyGenerator(algorithm="sha256")

    # Create large blocks (total ~10 MB)
    large_content = "x" * (1024 * 1024)  # 1 MB

    blocks = [
        CacheableContent(
            path=f"large_{i}.md", content=large_content, content_type="memory"
        )
        for i in range(10)
    ]

    start_time = time.time()
    key, metadata = generator.generate_cache_key(blocks)
    end_time = time.time()

    elapsed = end_time - start_time
    throughput = metadata["total_bytes"] / (1024 * 1024) / elapsed

    passed = elapsed < 5.0  # Should complete in under 5 seconds

    print(f"  Total size: {metadata['total_bytes'] / (1024*1024):.1f} MB")
    print(f"  Time taken: {elapsed:.3f} seconds")
    print(f"  Throughput: {throughput:.1f} MB/s")
    print(f"  Generated key: {key[:32]}...")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")

    return passed


def test_algorithm_comparison():
    """Compare MD5 vs SHA256."""
    print("\n[TEST] Algorithm Comparison: MD5 vs SHA256")
    print("-" * 60)

    blocks = [
        CacheableContent(
            path="test.md",
            content="Test content for algorithm comparison",
            content_type="memory",
        )
    ]

    # MD5
    generator_md5 = CacheKeyGenerator(algorithm="md5")
    key_md5, _ = generator_md5.generate_cache_key(blocks)

    # SHA256
    generator_sha256 = CacheKeyGenerator(algorithm="sha256")
    key_sha256, _ = generator_sha256.generate_cache_key(blocks)

    md5_len = len(key_md5)
    sha256_len = len(key_sha256)

    print(f"  MD5 key:    {key_md5} ({md5_len} chars)")
    print(f"  SHA256 key: {key_sha256[:32]}... ({sha256_len} chars)")
    print(f"  MD5 is faster but less collision-resistant")
    print(f"  SHA256 is recommended for cache keys")
    print(f"  Result: PASS (both algorithms work)")

    return True


def test_metadata_completeness():
    """Test that metadata contains all necessary information."""
    print("\n[TEST] Metadata Completeness: All info captured")
    print("-" * 60)

    generator = CacheKeyGenerator(algorithm="sha256")

    blocks = [
        CacheableContent(path="file1.md", content="Content 1", content_type="memory"),
        CacheableContent(path="file2.md", content="Content 2", content_type="doc"),
    ]

    key, metadata = generator.generate_cache_key(blocks)

    required_keys = [
        "algorithm",
        "format_version",
        "num_blocks",
        "block_count_by_type",
        "total_bytes",
        "blocks",
        "generated_at",
    ]

    missing_keys = [k for k in required_keys if k not in metadata]
    passed = len(missing_keys) == 0

    print(f"  Required fields: {required_keys}")
    print(f"  Missing fields: {missing_keys if missing_keys else 'None'}")
    print(f"  Sample metadata:")
    for key_name in required_keys[:4]:
        print(f"    - {key_name}: {metadata[key_name]}")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")

    return passed


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE CACHE KEY GENERATOR TEST SUITE")
    print("=" * 80)

    tests = [
        test_determinism,
        test_content_sensitivity,
        test_order_independence,
        test_unicode_handling,
        test_empty_content,
        test_large_content,
        test_algorithm_comparison,
        test_metadata_completeness,
    ]

    results = []
    for test_func in tests:
        try:
            passed = test_func()
            results.append((test_func.__name__, passed))
        except Exception as e:
            print(f"\n  ERROR: {e}")
            results.append((test_func.__name__, False))

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name}")

    print(f"\nTotal: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")

    print("=" * 80)

    return passed_count == total_count


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
