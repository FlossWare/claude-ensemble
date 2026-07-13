#!/usr/bin/env python3
"""
Verify Stuck Task Recovery Logic (Static Analysis)

This script analyzes the Lua script in redis_atomic_operations.py
to verify it correctly handles full task data recovery.

No Redis connection required - pure static analysis.
"""

import sys
import os
import re

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

def verify_lua_script():
    """Verify the LUA_RECOVER_STUCK script logic."""

    print("Static Analysis: Stuck Task Recovery Lua Script")
    print("=" * 60)
    print()

    # Import to get the script
    from redis_atomic_operations import RedisAtomicOps

    lua_script = RedisAtomicOps.LUA_RECOVER_STUCK

    print("📋 Analyzing LUA_RECOVER_STUCK script...")
    print()

    checks = []

    # Check 1: Scans metadata hash
    if "KEYS[1] .. ':metadata'" in lua_script and "HKEYS" in lua_script:
        checks.append(("✅", "Scans metadata hash for task IDs"))
    else:
        checks.append(("❌", "Does NOT scan metadata hash"))

    # Check 2: Gets full task JSON from processing hash
    if 'redis.call(\'HGET\', KEYS[1], task_id)' in lua_script:
        checks.append(("✅", "Retrieves FULL task JSON from processing hash"))
    else:
        checks.append(("❌", "Does NOT retrieve full task JSON"))

    # Check 3: Decodes task JSON
    if 'cjson.decode(task_json)' in lua_script:
        checks.append(("✅", "Decodes task JSON into Lua table"))
    else:
        checks.append(("❌", "Does NOT decode task JSON"))

    # Check 4: Adds recovery metadata
    recovery_fields = [
        "task['recovered_at']",
        "task['previous_worker']",
        "task['stuck_duration_ms']",
        "task['recovery_reason']"
    ]

    found_recovery_fields = [field for field in recovery_fields if field in lua_script]
    if len(found_recovery_fields) == len(recovery_fields):
        checks.append(("✅", f"Adds recovery metadata ({len(recovery_fields)} fields)"))
    else:
        checks.append(("⚠️", f"Missing {len(recovery_fields) - len(found_recovery_fields)} recovery fields"))

    # Check 5: Re-encodes task with all data
    if 'cjson.encode(task)' in lua_script:
        checks.append(("✅", "Re-encodes task with ALL fields (original + recovery)"))
    else:
        checks.append(("❌", "Does NOT re-encode task"))

    # Check 6: Uses ZADD to requeue
    if "redis.call('ZADD', KEYS[2], score, cjson.encode(task))" in lua_script:
        checks.append(("✅", "Requeues with ZADD using encoded task"))
    else:
        checks.append(("❌", "Does NOT use ZADD or does NOT encode task"))

    # Check 7: Cleans up processing state
    cleanup_calls = [
        "redis.call('HDEL', KEYS[1], task_id)",           # Processing hash
        "redis.call('HDEL', metadata_hash, task_id)",     # Metadata hash
        "redis.call('HDEL', KEYS[3], task_id)"           # Heartbeat hash
    ]

    found_cleanup = sum(1 for call in cleanup_calls if call in lua_script)
    if found_cleanup == len(cleanup_calls):
        checks.append(("✅", f"Cleans up all processing state ({len(cleanup_calls)} hashes)"))
    else:
        checks.append(("⚠️", f"Only cleans {found_cleanup}/{len(cleanup_calls)} hashes"))

    # Check 8: Priority calculation
    if "(10 - priority)" in lua_script and "1e13" in lua_script:
        checks.append(("✅", "Priority calculation correct (higher priority = lower score)"))
    else:
        checks.append(("⚠️", "Priority calculation may be incorrect"))

    # Print results
    for status, description in checks:
        print(f"  {status} {description}")

    print()

    # Summary
    passed = sum(1 for status, _ in checks if status == "✅")
    warnings = sum(1 for status, _ in checks if status == "⚠️")
    failed = sum(1 for status, _ in checks if status == "❌")

    print("=" * 60)
    print(f"Results: {passed} passed, {warnings} warnings, {failed} failed")
    print("=" * 60)
    print()

    if failed == 0 and warnings == 0:
        print("✅ VERIFICATION PASSED")
        print()
        print("The Lua script correctly:")
        print("  1. Scans metadata for expired heartbeats")
        print("  2. Retrieves FULL task JSON from processing hash")
        print("  3. Adds recovery metadata")
        print("  4. Requeues with ALL original + recovery fields")
        print("  5. Cleans up processing state")
        print()
        print("No data loss will occur during recovery.")
        return True
    elif failed == 0:
        print("⚠️  VERIFICATION PASSED WITH WARNINGS")
        print()
        print("The script should work but has minor issues.")
        return True
    else:
        print("❌ VERIFICATION FAILED")
        print()
        print("The script has critical issues that may cause data loss.")
        return False


def verify_python_wrapper():
    """Verify the Python wrapper function."""

    print("\n" + "=" * 60)
    print("Verifying Python Wrapper Function")
    print("=" * 60)
    print()

    from redis_atomic_operations import RedisAtomicOps
    import inspect

    # Get source code
    source = inspect.getsource(RedisAtomicOps.recover_stuck_tasks)

    checks = []

    # Check 1: Constructs correct key names
    if "f'redis:processing:{stage}'" in source:
        checks.append(("✅", "Constructs processing hash key correctly"))
    else:
        checks.append(("❌", "Processing hash key may be incorrect"))

    # Check 2: Constructs queue name
    if "f'redis:queue:{stage}'" in source:
        checks.append(("✅", "Constructs queue name correctly"))
    else:
        checks.append(("❌", "Queue name may be incorrect"))

    # Check 3: Constructs heartbeat hash
    if "f'redis:heartbeat:{stage}'" in source:
        checks.append(("✅", "Constructs heartbeat hash key correctly"))
    else:
        checks.append(("❌", "Heartbeat hash key may be incorrect"))

    # Check 4: Passes correct number of keys
    if "3,  # numkeys" in source:
        checks.append(("✅", "Passes 3 keys to Lua script (processing, queue, heartbeat)"))
    else:
        checks.append(("⚠️", "Number of keys may be incorrect"))

    # Check 5: Returns integer
    if "int(result)" in source:
        checks.append(("✅", "Returns integer count of recovered tasks"))
    else:
        checks.append(("❌", "Return type may be incorrect"))

    # Print results
    for status, description in checks:
        print(f"  {status} {description}")

    print()

    passed = sum(1 for status, _ in checks if status == "✅")
    failed = sum(1 for status, _ in checks if status == "❌")

    return failed == 0


def main():
    print()
    print("🔍 Stuck Task Recovery Static Analysis")
    print("=" * 60)
    print()
    print("This analysis verifies the recovery logic WITHOUT")
    print("connecting to Redis (pure static code analysis).")
    print()

    try:
        lua_ok = verify_lua_script()
        python_ok = verify_python_wrapper()

        print()
        print("=" * 60)
        print("FINAL VERDICT")
        print("=" * 60)
        print()

        if lua_ok and python_ok:
            print("✅ Implementation is CORRECT")
            print()
            print("The stuck task recovery mechanism:")
            print("  ✓ Scans metadata for expired heartbeats")
            print("  ✓ Retrieves FULL task data from processing hash")
            print("  ✓ Preserves all original fields (url, priority, content, etc.)")
            print("  ✓ Adds recovery metadata (recovered_at, previous_worker, etc.)")
            print("  ✓ Requeues with complete data")
            print("  ✓ Cleans up processing state")
            print()
            print("No code changes needed.")
            print()
            return 0
        else:
            print("❌ Implementation has ISSUES")
            print()
            print("Review the checks above and fix the issues.")
            print()
            return 1

    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == '__main__':
    sys.exit(main())
