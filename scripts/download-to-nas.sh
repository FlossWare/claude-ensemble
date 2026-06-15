#!/usr/bin/env bash

# download-to-nas.sh - Download AI models to NAS central repository
#
# ENHANCED: Now supports multiple vendors (Ollama, Hugging Face, GGUF, etc.)
# For multi-vendor support, use: download-multi-vendor.sh
#
# Usage:
#   download-to-nas.sh <model-name> [model-name...]
#   download-to-nas.sh --all
#   download-to-nas.sh --high-priority
#   download-to-nas.sh --multi-vendor MODEL_ID  (delegates to download-multi-vendor.sh)
#
# Examples:
#   download-to-nas.sh codestral:22b qwen2.5-coder:7b
#   download-to-nas.sh --all
#   download-to-nas.sh --multi-vendor hf:meta-llama/Llama-2-7b-chat-hf
#
# Environment Variables:
#   NAS_MODELS_DIR - NAS mount point (default: /mnt/nas/ai-models)
#   OLLAMA_HOST - Ollama server to download from (default: localhost:11434)

set -euo pipefail

# Configuration
NAS_MODELS_DIR="${NAS_MODELS_DIR:-/mnt/nas/ai-models}"
OLLAMA_HOST="${OLLAMA_HOST:-localhost:11434}"
MODELS_DIR="$NAS_MODELS_DIR/ollama"
MANIFESTS_DIR="$NAS_MODELS_DIR/manifests"
INVENTORY_FILE="$MANIFESTS_DIR/model-inventory.json"
VERSION_HISTORY="$MANIFESTS_DIR/version-history.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MODEL_REQUIREMENTS="$PROJECT_DIR/model-requirements.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if NAS is mounted
    if [[ ! -d "$NAS_MODELS_DIR" ]]; then
        log_error "NAS directory not found: $NAS_MODELS_DIR"
        log_info "Please mount the NAS first or set NAS_MODELS_DIR environment variable"
        exit 1
    fi

    # Check if Ollama is available
    if ! command -v ollama &> /dev/null; then
        log_error "Ollama CLI not found. Please install Ollama first."
        exit 1
    fi

    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Please install jq for JSON processing."
        exit 1
    fi

    # Create directory structure
    mkdir -p "$MODELS_DIR"
    mkdir -p "$MANIFESTS_DIR"

    # Initialize inventory if it doesn't exist
    if [[ ! -f "$INVENTORY_FILE" ]]; then
        log_info "Initializing model inventory..."
        cat > "$INVENTORY_FILE" <<EOF
{
  "_comment": "NAS Model Inventory - Central repository of downloaded models",
  "_version": "1.0",
  "_last_updated": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "nas_path": "$NAS_MODELS_DIR",
  "models": {}
}
EOF
    fi

    # Initialize version history if it doesn't exist
    if [[ ! -f "$VERSION_HISTORY" ]]; then
        cat > "$VERSION_HISTORY" <<EOF
{
  "_comment": "Version history of model downloads",
  "downloads": []
}
EOF
    fi

    log_success "Prerequisites check passed"
}

# Get model size from Ollama
get_model_size() {
    local model_name="$1"

    # Try to get model info from Ollama
    if ollama list | grep -q "^${model_name}"; then
        # Model exists locally, get size
        local size_str=$(ollama list | grep "^${model_name}" | awk '{print $(NF-1), $NF}')
        echo "$size_str"
    else
        echo "unknown"
    fi
}

# Calculate SHA256 checksum of model files
calculate_checksum() {
    local model_dir="$1"

    if [[ -d "$model_dir" ]]; then
        find "$model_dir" -type f -exec sha256sum {} \; | sort | sha256sum | awk '{print $1}'
    else
        echo "N/A"
    fi
}

# Download model using Ollama
download_model() {
    local model_name="$1"
    local model_dir="$MODELS_DIR/$model_name"

    log_info "Downloading model: $model_name"

    # Create model directory
    mkdir -p "$model_dir"

    # Download model using Ollama
    log_info "Pulling model from Ollama registry..."
    if OLLAMA_HOST="$OLLAMA_HOST" ollama pull "$model_name"; then
        log_success "Model pulled successfully: $model_name"
    else
        log_error "Failed to pull model: $model_name"
        return 1
    fi

    # Export model to NAS
    log_info "Exporting model to NAS: $model_dir"

    # Get model manifest and blobs
    # Ollama stores models in ~/.ollama/models
    local ollama_models_dir="$HOME/.ollama/models"

    if [[ -d "$ollama_models_dir" ]]; then
        # Copy manifests
        if [[ -d "$ollama_models_dir/manifests" ]]; then
            rsync -av "$ollama_models_dir/manifests/" "$model_dir/manifests/" || true
        fi

        # Copy blobs
        if [[ -d "$ollama_models_dir/blobs" ]]; then
            # Get model-specific blobs based on manifest
            local model_hash=$(echo "$model_name" | sha256sum | awk '{print $1}')
            rsync -av "$ollama_models_dir/blobs/" "$model_dir/blobs/" || true
        fi
    fi

    # Get model metadata
    local size_str=$(get_model_size "$model_name")
    local size_gb="unknown"

    # Convert size to GB
    if [[ "$size_str" =~ ([0-9.]+)[[:space:]]*GB ]]; then
        size_gb="${BASH_REMATCH[1]}"
    elif [[ "$size_str" =~ ([0-9.]+)[[:space:]]*MB ]]; then
        size_gb=$(echo "scale=2; ${BASH_REMATCH[1]} / 1024" | bc)
    fi

    # Calculate checksum
    local checksum=$(calculate_checksum "$model_dir")

    # Get actual disk usage
    local disk_usage=$(du -sh "$model_dir" | awk '{print $1}')

    # Update inventory
    update_inventory "$model_name" "$size_gb" "$checksum" "$disk_usage"

    log_success "Model exported to NAS: $model_name ($disk_usage)"

    return 0
}

# Update inventory with downloaded model
update_inventory() {
    local model_name="$1"
    local size_gb="$2"
    local checksum="$3"
    local disk_usage="$4"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Create temporary file
    local temp_file=$(mktemp)

    # Update inventory using jq
    jq --arg model "$model_name" \
       --arg size "$size_gb" \
       --arg checksum "$checksum" \
       --arg disk "$disk_usage" \
       --arg time "$timestamp" \
       '._last_updated = $time |
        .models[$model] = {
          "size_gb": ($size | tonumber? // $size),
          "disk_usage": $disk,
          "downloaded": $time,
          "version": "latest",
          "checksum": $checksum,
          "distributed_to": [],
          "nas_path": (.nas_path + "/ollama/" + $model)
        }' "$INVENTORY_FILE" > "$temp_file"

    mv "$temp_file" "$INVENTORY_FILE"

    # Add to version history
    temp_file=$(mktemp)
    jq --arg model "$model_name" \
       --arg time "$timestamp" \
       --arg checksum "$checksum" \
       '.downloads += [{
          "model": $model,
          "timestamp": $time,
          "checksum": $checksum,
          "action": "download"
        }]' "$VERSION_HISTORY" > "$temp_file"

    mv "$temp_file" "$VERSION_HISTORY"

    log_info "Inventory updated for: $model_name"
}

# Get high-priority models from model-requirements.json
get_high_priority_models() {
    if [[ -f "$MODEL_REQUIREMENTS" ]]; then
        jq -r '.models | to_entries[] |
               select(.value.type == "local" and .value.priority == "high") |
               .key' "$MODEL_REQUIREMENTS"
    else
        log_warn "Model requirements file not found: $MODEL_REQUIREMENTS"
        echo ""
    fi
}

# Get all local models from model-requirements.json
get_all_local_models() {
    if [[ -f "$MODEL_REQUIREMENTS" ]]; then
        jq -r '.models | to_entries[] |
               select(.value.type == "local") |
               .key' "$MODEL_REQUIREMENTS"
    else
        log_warn "Model requirements file not found: $MODEL_REQUIREMENTS"
        echo ""
    fi
}

# Show usage
show_usage() {
    cat <<EOF
Download Ollama models to NAS central repository

Usage:
  $0 <model-name> [model-name...]
  $0 --all
  $0 --high-priority
  $0 --list
  $0 --verify <model-name>

Options:
  --all            Download all local models from model-requirements.json
  --high-priority  Download only high-priority models
  --list           List models in NAS inventory
  --verify         Verify model checksum
  -h, --help       Show this help message

Environment Variables:
  NAS_MODELS_DIR   NAS mount point (default: /mnt/nas/ai-models)
  OLLAMA_HOST      Ollama server (default: localhost:11434)

Examples:
  $0 codestral:22b qwen2.5-coder:7b
  $0 --high-priority
  $0 --all
  $0 --list
  $0 --verify codestral:22b
EOF
}

# List models in inventory
list_models() {
    if [[ ! -f "$INVENTORY_FILE" ]]; then
        log_warn "No inventory file found"
        return
    fi

    echo ""
    echo "NAS Model Inventory"
    echo "==================="
    echo ""

    jq -r '.models | to_entries[] |
           "\(.key):\n  Size: \(.value.size_gb)GB (\(.value.disk_usage))\n  Downloaded: \(.value.downloaded)\n  Checksum: \(.value.checksum)\n  Distributed to: \(.value.distributed_to | join(", ") | if . == "" then "none" else . end)\n"' \
       "$INVENTORY_FILE"

    echo ""
    local total_models=$(jq -r '.models | length' "$INVENTORY_FILE")
    local last_updated=$(jq -r '._last_updated' "$INVENTORY_FILE")
    echo "Total models: $total_models"
    echo "Last updated: $last_updated"
}

# Verify model checksum
verify_model() {
    local model_name="$1"
    local model_dir="$MODELS_DIR/$model_name"

    if [[ ! -d "$model_dir" ]]; then
        log_error "Model not found in NAS: $model_name"
        return 1
    fi

    log_info "Verifying model: $model_name"

    # Get stored checksum
    local stored_checksum=$(jq -r --arg model "$model_name" '.models[$model].checksum' "$INVENTORY_FILE")

    if [[ "$stored_checksum" == "null" ]] || [[ "$stored_checksum" == "N/A" ]]; then
        log_warn "No checksum stored for model: $model_name"
        return 1
    fi

    # Calculate current checksum
    local current_checksum=$(calculate_checksum "$model_dir")

    if [[ "$stored_checksum" == "$current_checksum" ]]; then
        log_success "Checksum verified: $model_name"
        return 0
    else
        log_error "Checksum mismatch for $model_name"
        log_error "  Stored:  $stored_checksum"
        log_error "  Current: $current_checksum"
        return 1
    fi
}

# Main
main() {
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 0
    fi

    # Check for multi-vendor delegation
    if [[ "$1" == "--multi-vendor" ]]; then
        shift
        if [[ $# -eq 0 ]]; then
            log_error "Please specify model identifier for multi-vendor download"
            exit 1
        fi

        log_info "Delegating to multi-vendor downloader..."
        exec "$SCRIPT_DIR/download-multi-vendor.sh" "$@"
    fi

    # Auto-detect multi-vendor model identifiers
    if [[ "$1" =~ ^(hf|gguf|meta): ]]; then
        log_info "Multi-vendor model detected, delegating to download-multi-vendor.sh..."
        exec "$SCRIPT_DIR/download-multi-vendor.sh" "$@"
    fi

    check_prerequisites

    case "$1" in
        -h|--help)
            show_usage
            exit 0
            ;;
        --list)
            list_models
            exit 0
            ;;
        --verify)
            if [[ $# -lt 2 ]]; then
                log_error "Please specify model name to verify"
                exit 1
            fi
            verify_model "$2"
            exit $?
            ;;
        --all)
            log_info "Downloading all local models..."
            mapfile -t models < <(get_all_local_models)

            if [[ ${#models[@]} -eq 0 ]]; then
                log_error "No models found in model-requirements.json"
                exit 1
            fi

            log_info "Found ${#models[@]} models to download"

            success_count=0
            fail_count=0

            for model in "${models[@]}"; do
                if download_model "$model"; then
                    ((success_count++))
                else
                    ((fail_count++))
                fi
            done

            echo ""
            log_info "Download summary:"
            log_success "  Successful: $success_count"
            if [[ $fail_count -gt 0 ]]; then
                log_error "  Failed: $fail_count"
            fi
            ;;
        --high-priority)
            log_info "Downloading high-priority models..."
            mapfile -t models < <(get_high_priority_models)

            if [[ ${#models[@]} -eq 0 ]]; then
                log_error "No high-priority models found in model-requirements.json"
                exit 1
            fi

            log_info "Found ${#models[@]} high-priority models to download"

            success_count=0
            fail_count=0

            for model in "${models[@]}"; do
                if download_model "$model"; then
                    ((success_count++))
                else
                    ((fail_count++))
                fi
            done

            echo ""
            log_info "Download summary:"
            log_success "  Successful: $success_count"
            if [[ $fail_count -gt 0 ]]; then
                log_error "  Failed: $fail_count"
            fi
            ;;
        *)
            # Download specific models
            success_count=0
            fail_count=0

            for model in "$@"; do
                if download_model "$model"; then
                    ((success_count++))
                else
                    ((fail_count++))
                fi
            done

            echo ""
            log_info "Download summary:"
            log_success "  Successful: $success_count"
            if [[ $fail_count -gt 0 ]]; then
                log_error "  Failed: $fail_count"
            fi
            ;;
    esac

    echo ""
    log_success "Done! Models stored in: $NAS_MODELS_DIR"
}

main "$@"
