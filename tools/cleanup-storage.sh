#!/bin/bash
#
# Storage Cleanup Script for .claude/ directory (21GB → manageable)
# Identifies and removes large logs, temp files, duplicates, old backups
#
# Usage:
#   ./cleanup-storage.sh --dry-run   # Show what would be deleted
#   ./cleanup-storage.sh --execute   # Actually delete files
#

set -euo pipefail

# Configuration
CLAUDE_DIR="${HOME}/.claude"
MIN_LOG_SIZE_MB=100          # Delete logs larger than this
TEMP_PATTERNS=("*.tmp" "*.temp" "*.swp" "*~")
OLD_BACKUP_DAYS=30           # Delete backups older than this
DRY_RUN=true

# Parse arguments
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
        --execute)
            DRY_RUN=false
            ;;
        *)
            echo "Usage: $0 [--dry-run|--execute]"
            exit 1
            ;;
    esac
done

# Safety check
if [ ! -d "$CLAUDE_DIR" ]; then
    echo "Error: $CLAUDE_DIR does not exist"
    exit 1
fi

echo "============================================"
if [ "$DRY_RUN" = true ]; then
    echo "DRY RUN MODE - No files will be deleted"
else
    echo "EXECUTE MODE - Files WILL BE DELETED"
fi
echo "============================================"
echo ""

# Current disk usage
echo "Current disk usage:"
du -sh "$CLAUDE_DIR"
du -sh "$CLAUDE_DIR"/* 2>/dev/null | sort -hr | head -10
echo ""

# Track space to be freed
TOTAL_FREED=0

# Function to delete or show file
delete_file() {
    local file="$1"
    local size_bytes=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
    local size_mb=$((size_bytes / 1024 / 1024))

    if [ "$DRY_RUN" = true ]; then
        echo "  [DRY RUN] Would delete: $file ($size_mb MB)"
    else
        echo "  Deleting: $file ($size_mb MB)"
        rm -f "$file"
    fi

    TOTAL_FREED=$((TOTAL_FREED + size_mb))
}

# 1. Find and remove large log files (>100MB)
echo "1. Scanning for large log files (>${MIN_LOG_SIZE_MB}MB)..."
while IFS= read -r -d '' file; do
    delete_file "$file"
done < <(find "$CLAUDE_DIR" -type f \( -name "*.log" -o -name "*.jsonl" \) -size +${MIN_LOG_SIZE_MB}M -print0 2>/dev/null)
echo ""

# 2. Find and remove temporary files
echo "2. Scanning for temporary files..."
for pattern in "${TEMP_PATTERNS[@]}"; do
    while IFS= read -r -d '' file; do
        delete_file "$file"
    done < <(find "$CLAUDE_DIR" -type f -name "$pattern" -print0 2>/dev/null)
done
echo ""

# 3. Find and remove old backups (>30 days)
echo "3. Scanning for old backups (>${OLD_BACKUP_DAYS} days)..."
while IFS= read -r -d '' file; do
    delete_file "$file"
done < <(find "$CLAUDE_DIR" -type f \( -name "*.bak" -o -name "*.backup" -o -path "*/backups/*" \) -mtime +${OLD_BACKUP_DAYS} -print0 2>/dev/null)
echo ""

# 4. Find duplicate files (same size and name in different dirs)
echo "4. Scanning for potential duplicates..."
find "$CLAUDE_DIR" -type f -exec du -b {} + 2>/dev/null | \
    sort -n | \
    awk 'BEGIN{prev_size=0; prev_file=""}
         {
             size=$1;
             file=$2;
             basename_file=file;
             sub(/.*\//, "", basename_file);
             if (size == prev_size && basename_file == prev_basename && file != prev_file) {
                 print prev_file " (duplicate of " file ")"
             }
             prev_size=size;
             prev_file=file;
             prev_basename=basename_file;
         }' | head -20
echo "  (Manual review recommended for duplicates)"
echo ""

# 5. Find corrupted files
echo "5. Scanning for corrupted files..."
while IFS= read -r -d '' file; do
    delete_file "$file"
done < <(find "$CLAUDE_DIR" -type f -name "*.corrupt.*" -print0 2>/dev/null)
echo ""

# 6. Identify large directories
echo "6. Largest directories:"
du -sh "$CLAUDE_DIR"/*/ 2>/dev/null | sort -hr | head -10
echo ""

# Summary
echo "============================================"
echo "SUMMARY"
echo "============================================"
echo "Estimated space to be freed: ${TOTAL_FREED} MB"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo "This was a DRY RUN. No files were deleted."
    echo "Run with --execute to actually delete files."
else
    echo "Files deleted successfully."
    echo ""
    echo "New disk usage:"
    du -sh "$CLAUDE_DIR"
fi
