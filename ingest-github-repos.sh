#!/bin/bash
# Ingest GitHub Repositories into ChromaDB
# Usage: ./ingest-github-repos.sh repos.txt
#        ./ingest-github-repos.sh https://github.com/user/repo

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOS_DIR="$HOME/Development/github-repos"
CHROMA_PATH="$SCRIPT_DIR/knowledge/chromadb"
LOG_FILE="$SCRIPT_DIR/github-ingest.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

# Create repos directory
mkdir -p "$REPOS_DIR"

# Function to clone or update a repo
clone_or_update() {
    local repo_url="$1"
    local repo_name=$(basename "$repo_url" .git)
    local repo_path="$REPOS_DIR/$repo_name"

    if [ -d "$repo_path" ]; then
        info "Repo exists, updating: $repo_name"
        cd "$repo_path"
        git pull --quiet || warn "Failed to update $repo_name"
    else
        log "Cloning: $repo_url"
        cd "$REPOS_DIR"
        if git clone --depth 1 "$repo_url" 2>&1 | tee -a "$LOG_FILE"; then
            log "✅ Cloned: $repo_name"
        else
            error "Failed to clone: $repo_url"
            return 1
        fi
    fi

    echo "$repo_path"
}

# Function to ingest a repo
ingest_repo() {
    local repo_path="$1"
    local repo_name=$(basename "$repo_path")

    log "📦 Ingesting: $repo_name"

    if [ ! -f "$SCRIPT_DIR/ingest-codebase.sh" ]; then
        error "ingest-codebase.sh not found!"
        return 1
    fi

    if bash "$SCRIPT_DIR/ingest-codebase.sh" "$repo_path" 2>&1 | tee -a "$LOG_FILE"; then
        log "✅ Ingested: $repo_name"
        return 0
    else
        error "Failed to ingest: $repo_name"
        return 1
    fi
}

# Main script
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 GitHub Repository Ingestion"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
log "Repos directory: $REPOS_DIR"
log "ChromaDB path: $CHROMA_PATH"
log "Log file: $LOG_FILE"
echo

# Check if input is a file or a single URL
INPUT="$1"

if [ -z "$INPUT" ]; then
    echo "Usage: $0 <repos.txt | github-url>"
    echo
    echo "Examples:"
    echo "  $0 repos.txt"
    echo "  $0 https://github.com/torvalds/linux"
    echo
    exit 1
fi

REPOS=()

if [ -f "$INPUT" ]; then
    # Read from file
    log "Reading repos from: $INPUT"
    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^#.*$ ]] && continue
        [[ -z "$line" ]] && continue
        REPOS+=("$line")
    done < "$INPUT"
else
    # Single repo URL
    REPOS=("$INPUT")
fi

log "Found ${#REPOS[@]} repositories to process"
echo

# Process each repo
SUCCESS=0
FAILED=0

for repo_url in "${REPOS[@]}"; do
    echo
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Processing: $repo_url"

    # Clone or update
    if repo_path=$(clone_or_update "$repo_url"); then
        # Ingest
        if ingest_repo "$repo_path"; then
            ((SUCCESS++))
        else
            ((FAILED++))
        fi
    else
        ((FAILED++))
    fi

    echo
done

# Summary
echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "✅ Success: $SUCCESS"
log "❌ Failed:  $FAILED"
log "📝 Log: $LOG_FILE"
echo

# Show ChromaDB status
python3 << EOF
import chromadb

client = chromadb.PersistentClient(path="$CHROMA_PATH")
collections = client.list_collections()

print("📚 ChromaDB Collections:")
total_vectors = 0
for coll in collections:
    count = coll.count()
    total_vectors += count
    print(f"   • {coll.name}: {count:,} vectors")

print(f"\n   Total: {total_vectors:,} vectors")
EOF

echo
log "🎉 All done!"
