#!/usr/bin/env python3
"""Data validation and cleanup for session IDs before Cypher generation"""
import sys
import re

# UUID v4 format: 8-4-4-4-12 hex digits
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.IGNORECASE)
# Agent format: agent-<uuid> (case-sensitive prefix for Neo4j consistency)
AGENT_PATTERN = re.compile(r'^agent-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')

def validate_and_clean_session_ids(input_file, output_file):
    """
    Fix 1: Strip leading spaces from UUIDs
    Fix 2: Reject empty session_id values
    Fix 3: Validate proper UUID v4 format
    """
    valid_count = 0
    invalid_count = 0
    reject_log_path = f"{output_file}.rejected"

    with open(input_file, 'r') as inf, \
         open(output_file, 'w') as outf, \
         open(reject_log_path, 'w') as reject_log:

        for line_num, line in enumerate(inf, 1):
            original = line.rstrip('\n')
            session_id = line.strip()

            # Reject empty
            if not session_id:
                invalid_count += 1
                reject_log.write(f"Line {line_num}: '{original}' - REASON: empty\n")
                continue

            # Validate UUID format
            if not (UUID_PATTERN.match(session_id) or AGENT_PATTERN.match(session_id)):
                invalid_count += 1
                reject_log.write(f"Line {line_num}: '{original}' - REASON: invalid UUID format\n")
                continue

            # Write valid session_id
            outf.write(f"{session_id}\n")
            valid_count += 1

    return valid_count, invalid_count, reject_log_path

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: fix_data_validation.py <input_file> <output_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    valid, invalid, reject_log = validate_and_clean_session_ids(input_file, output_file)
    print(f"Valid: {valid}, Invalid: {invalid}")
    if invalid > 0:
        print(f"Rejected records logged to: {reject_log}")
