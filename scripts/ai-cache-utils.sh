#!/bin/bash
# AI Response Cache Utilities - shared across fleet via NAS
# Reduces FREE API calls by caching responses

CACHE_DIR="/mnt/nas/ai-cache"
TTL_RESPONSES=7  # days
TTL_EMBEDDINGS=30  # days

# Generate cache key from model + prompt
cache_key() {
    local model="$1"
    local prompt="$2"
    echo -n "${model}:${prompt}" | sha256sum | cut -d' ' -f1
}

# Check if response is cached
check_cache() {
    local model="$1"
    local prompt="$2"
    local key=$(cache_key "$model" "$prompt")
    local cache_file="$CACHE_DIR/responses/$key.json"

    if [ -f "$cache_file" ]; then
        # Check if not expired
        if [ $(find "$cache_file" -mtime -$TTL_RESPONSES | wc -l) -eq 1 ]; then
            cat "$cache_file"
            return 0
        else
            rm "$cache_file"  # Expired
        fi
    fi

    return 1
}

# Store response in cache
store_cache() {
    local model="$1"
    local prompt="$2"
    local response="$3"
    local key=$(cache_key "$model" "$prompt")
    local cache_file="$CACHE_DIR/responses/$key.json"

    echo "$response" > "$cache_file"
}

# Check embedding cache
check_embedding() {
    local text="$1"
    local key=$(echo -n "$text" | sha256sum | cut -d' ' -f1)
    local cache_file="$CACHE_DIR/embeddings/$key.json"

    if [ -f "$cache_file" ]; then
        if [ $(find "$cache_file" -mtime -$TTL_EMBEDDINGS | wc -l) -eq 1 ]; then
            cat "$cache_file"
            return 0
        else
            rm "$cache_file"
        fi
    fi

    return 1
}

# Store embedding in cache
store_embedding() {
    local text="$1"
    local embedding="$2"
    local key=$(echo -n "$text" | sha256sum | cut -d' ' -f1)
    local cache_file="$CACHE_DIR/embeddings/$key.json"

    echo "$embedding" > "$cache_file"
}

# Clean expired cache entries
clean_cache() {
    echo "🧹 Cleaning expired cache entries..."

    # Clean old responses (>7 days)
    local responses_deleted=$(find "$CACHE_DIR/responses" -name "*.json" -mtime +$TTL_RESPONSES -delete -print | wc -l)

    # Clean old embeddings (>30 days)
    local embeddings_deleted=$(find "$CACHE_DIR/embeddings" -name "*.json" -mtime +$TTL_EMBEDDINGS -delete -print | wc -l)

    echo "  Responses deleted: $responses_deleted"
    echo "  Embeddings deleted: $embeddings_deleted"
}

# Cache stats
cache_stats() {
    local responses=$(find "$CACHE_DIR/responses" -name "*.json" | wc -l)
    local embeddings=$(find "$CACHE_DIR/embeddings" -name "*.json" | wc -l)
    local total_size=$(du -sh "$CACHE_DIR" | cut -f1)

    echo "📊 AI Cache Statistics"
    echo "  Cached responses: $responses"
    echo "  Cached embeddings: $embeddings"
    echo "  Total size: $total_size"
}

# Usage examples
case "${1:-}" in
    check)
        check_cache "$2" "$3"
        ;;
    store)
        store_cache "$2" "$3" "$4"
        ;;
    check-embedding)
        check_embedding "$2"
        ;;
    store-embedding)
        store_embedding "$2" "$3"
        ;;
    clean)
        clean_cache
        ;;
    stats)
        cache_stats
        ;;
    *)
        echo "Usage: $0 {check|store|check-embedding|store-embedding|clean|stats} [args...]"
        echo
        echo "Examples:"
        echo "  $0 check opus 'What is 2+2?'"
        echo "  $0 store opus 'What is 2+2?' '{\"response\": \"4\"}'"
        echo "  $0 clean"
        echo "  $0 stats"
        ;;
esac
