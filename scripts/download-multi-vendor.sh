#!/usr/bin/env bash

# download-multi-vendor.sh - Download AI models from ANY vendor to NAS
#
# Supports:
#   - Ollama (native registry)
#   - Hugging Face (with conversion)
#   - Direct GGUF downloads
#   - Meta/Facebook LLaMA
#   - Mistral AI
#   - Google Gemma
#   - Microsoft Phi
#   - Alibaba Qwen
#   - Any GGUF URL
#
# Usage:
#   download-multi-vendor.sh ollama:codestral:22b
#   download-multi-vendor.sh hf:meta-llama/Llama-2-7b-chat-hf
#   download-multi-vendor.sh gguf:https://huggingface.co/.../model.gguf
#   download-multi-vendor.sh --list-vendors
#   download-multi-vendor.sh --list-models
#
# Prefix syntax:
#   ollama:MODEL_NAME              - Download from Ollama registry
#   hf:ORG/MODEL                   - Download from Hugging Face
#   gguf:URL or gguf:HF_PATH       - Download GGUF file
#   meta:MODEL                     - Official Meta models (requires auth)
#   MODEL_NAME (no prefix)         - Auto-detect vendor

set -euo pipefail

# Configuration
NAS_MODELS_DIR="${NAS_MODELS_DIR:-/mnt/nas/ai-models}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENDOR_SOURCES="$SCRIPT_DIR/vendor-sources.json"
MANIFESTS_DIR="$NAS_MODELS_DIR/manifests"
INVENTORY_FILE="$MANIFESTS_DIR/model-inventory.json"

# Vendor-specific directories
OLLAMA_DIR="$NAS_MODELS_DIR/ollama"
HUGGINGFACE_DIR="$NAS_MODELS_DIR/huggingface"
GGUF_DIR="$NAS_MODELS_DIR/gguf"
META_DIR="$NAS_MODELS_DIR/facebook"
CONVERSION_DIR="$NAS_MODELS_DIR/conversions"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
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

log_vendor() {
    local vendor="$1"
    shift
    echo -e "${MAGENTA}[${vendor}]${NC} $*"
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

    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Please install jq for JSON processing."
        exit 1
    fi

    # Create directory structure
    mkdir -p "$OLLAMA_DIR"
    mkdir -p "$HUGGINGFACE_DIR"
    mkdir -p "$GGUF_DIR"
    mkdir -p "$META_DIR"
    mkdir -p "$CONVERSION_DIR"
    mkdir -p "$MANIFESTS_DIR"

    # Initialize inventory if it doesn't exist
    if [[ ! -f "$INVENTORY_FILE" ]]; then
        log_info "Initializing model inventory..."
        cat > "$INVENTORY_FILE" <<EOF
{
  "_comment": "NAS Model Inventory - Multi-vendor central repository",
  "_version": "2.0",
  "_last_updated": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "nas_path": "$NAS_MODELS_DIR",
  "models": {}
}
EOF
    fi

    log_success "Prerequisites check passed"
}

# Parse model identifier to detect vendor
parse_model_id() {
    local model_id="$1"
    local vendor=""
    local model_name=""
    local source_url=""

    if [[ "$model_id" =~ ^ollama:(.+)$ ]]; then
        vendor="ollama"
        model_name="${BASH_REMATCH[1]}"
        source_url="ollama.com/library/$model_name"
    elif [[ "$model_id" =~ ^hf:(.+)$ ]]; then
        vendor="huggingface"
        model_name="${BASH_REMATCH[1]}"
        source_url="https://huggingface.co/$model_name"
    elif [[ "$model_id" =~ ^gguf:(https?://.+)$ ]]; then
        vendor="gguf-direct"
        model_name=$(basename "${BASH_REMATCH[1]}")
        source_url="${BASH_REMATCH[1]}"
    elif [[ "$model_id" =~ ^gguf:(.+)$ ]]; then
        vendor="thebloke"
        model_name=$(basename "${BASH_REMATCH[1]}")
        # Assume it's a HuggingFace path
        source_url="https://huggingface.co/${BASH_REMATCH[1]}/resolve/main/$model_name"
    elif [[ "$model_id" =~ ^meta:(.+)$ ]]; then
        vendor="meta"
        model_name="${BASH_REMATCH[1]}"
        source_url="https://llama.meta.com/llama-downloads"
    else
        # No prefix - try to auto-detect from vendor-sources.json
        if [[ -f "$VENDOR_SOURCES" ]]; then
            local lookup=$(jq -r --arg model "$model_id" '.models[$model] // .models["ollama:" + $model] // empty' "$VENDOR_SOURCES")
            if [[ -n "$lookup" ]]; then
                vendor=$(echo "$lookup" | jq -r '.vendor')
                model_name="$model_id"
                source_url=$(echo "$lookup" | jq -r '.source_url')
            else
                # Default to Ollama
                vendor="ollama"
                model_name="$model_id"
                source_url="ollama.com/library/$model_id"
            fi
        else
            # Default to Ollama
            vendor="ollama"
            model_name="$model_id"
            source_url="ollama.com/library/$model_id"
        fi
    fi

    echo "$vendor|$model_name|$source_url"
}

# Download from Ollama
download_ollama() {
    local model_name="$1"
    local model_dir="$OLLAMA_DIR/$model_name"

    log_vendor "OLLAMA" "Downloading: $model_name"

    # Check if Ollama is available
    if ! command -v ollama &> /dev/null; then
        log_error "Ollama CLI not found. Please install Ollama first."
        return 1
    fi

    # Create model directory
    mkdir -p "$model_dir"

    # Download model using Ollama
    log_info "Pulling model from Ollama registry..."
    if ollama pull "$model_name"; then
        log_success "Model pulled successfully: $model_name"
    else
        log_error "Failed to pull model: $model_name"
        return 1
    fi

    # Export model to NAS
    log_info "Exporting model to NAS: $model_dir"

    # Get model manifest and blobs from Ollama storage
    local ollama_models_dir="$HOME/.ollama/models"

    if [[ -d "$ollama_models_dir" ]]; then
        # Copy manifests
        if [[ -d "$ollama_models_dir/manifests" ]]; then
            rsync -av "$ollama_models_dir/manifests/" "$model_dir/manifests/" || true
        fi

        # Copy blobs
        if [[ -d "$ollama_models_dir/blobs" ]]; then
            rsync -av "$ollama_models_dir/blobs/" "$model_dir/blobs/" || true
        fi
    fi

    # Get actual disk usage
    local disk_usage=$(du -sh "$model_dir" | awk '{print $1}')
    log_success "Model exported: $model_name ($disk_usage)"

    # Update inventory
    update_inventory "ollama" "$model_name" "$disk_usage" "ollama-native" "ollama.com/library/$model_name"

    return 0
}

# Download from Hugging Face
download_huggingface() {
    local model_path="$1"  # e.g., "meta-llama/Llama-2-7b-chat-hf"
    local model_dir="$HUGGINGFACE_DIR/$model_path"

    log_vendor "HUGGINGFACE" "Downloading: $model_path"

    # Check if huggingface-cli is available
    if ! command -v huggingface-cli &> /dev/null; then
        log_error "huggingface-cli not found. Installing..."
        pip install -U huggingface_hub || {
            log_error "Failed to install huggingface_hub. Please install manually: pip install -U huggingface_hub"
            return 1
        }
    fi

    # Create model directory
    mkdir -p "$model_dir"

    # Download model
    log_info "Downloading from Hugging Face hub..."
    if huggingface-cli download "$model_path" --local-dir "$model_dir"; then
        log_success "Model downloaded successfully: $model_path"
    else
        log_error "Failed to download model: $model_path"
        log_warn "Note: Some models require authentication. Use: huggingface-cli login"
        return 1
    fi

    # Get disk usage
    local disk_usage=$(du -sh "$model_dir" | awk '{print $1}')
    log_success "Model saved: $model_path ($disk_usage)"

    # Check if conversion is needed
    local needs_conversion=false
    if [[ -f "$model_dir/pytorch_model.bin" ]] || [[ -f "$model_dir/model.safetensors" ]]; then
        log_info "Model is in PyTorch/SafeTensors format - GGUF conversion recommended for Ollama/llama.cpp"
        needs_conversion=true
    fi

    # Update inventory
    update_inventory "huggingface" "$model_path" "$disk_usage" "safetensors" "https://huggingface.co/$model_path" "$needs_conversion"

    return 0
}

# Download direct GGUF file
download_gguf() {
    local url="$1"
    local filename=$(basename "$url")
    local model_file="$GGUF_DIR/$filename"

    log_vendor "GGUF" "Downloading: $filename"

    # Create directory
    mkdir -p "$GGUF_DIR"

    # Download using wget
    log_info "Downloading GGUF file..."
    if wget -O "$model_file" "$url"; then
        log_success "GGUF file downloaded successfully: $filename"
    else
        log_error "Failed to download GGUF file from: $url"
        return 1
    fi

    # Get file size
    local disk_usage=$(du -sh "$model_file" | awk '{print $1}')
    log_success "GGUF file saved: $filename ($disk_usage)"

    # Update inventory
    update_inventory "gguf-direct" "$filename" "$disk_usage" "gguf" "$url" false

    return 0
}

# Download from Meta (requires authentication)
download_meta() {
    local model_name="$1"

    log_vendor "META" "Downloading: $model_name"
    log_error "Meta models require manual download with license approval"
    log_info "Steps to download Meta LLaMA models:"
    log_info "  1. Visit: https://llama.meta.com/llama-downloads"
    log_info "  2. Fill out the license agreement form"
    log_info "  3. You'll receive an email with download instructions"
    log_info "  4. Use the provided download script or link"
    log_info ""
    log_info "Alternative: Use pre-converted models from Hugging Face or TheBloke"
    log_info "  download-multi-vendor.sh hf:meta-llama/Llama-2-7b-chat-hf"
    log_info "  download-multi-vendor.sh gguf:TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_K_M.gguf"

    return 1
}

# Convert Hugging Face model to GGUF
convert_hf_to_gguf() {
    local hf_path="$1"
    local model_dir="$HUGGINGFACE_DIR/$hf_path"
    local output_dir="$GGUF_DIR/$(basename "$hf_path")"

    log_info "Converting Hugging Face model to GGUF format..."

    # Check if llama.cpp is available
    if [[ ! -d "$HOME/llama.cpp" ]]; then
        log_warn "llama.cpp not found. Cloning repository..."
        git clone https://github.com/ggerganov/llama.cpp "$HOME/llama.cpp" || {
            log_error "Failed to clone llama.cpp"
            return 1
        }
    fi

    # Run conversion
    cd "$HOME/llama.cpp"

    log_info "Running conversion script..."
    if python3 convert-hf-to-gguf.py "$model_dir" --outfile "$output_dir/model.gguf" --outtype f16; then
        log_success "Conversion completed: $output_dir/model.gguf"

        # Optionally quantize
        log_info "Quantizing to Q4_K_M..."
        if ./quantize "$output_dir/model.gguf" "$output_dir/model-q4_k_m.gguf" Q4_K_M; then
            log_success "Quantization completed: $output_dir/model-q4_k_m.gguf"
        fi
    else
        log_error "Conversion failed"
        return 1
    fi

    cd - > /dev/null
    return 0
}

# Update inventory with downloaded model
update_inventory() {
    local vendor="$1"
    local model_name="$2"
    local disk_usage="$3"
    local format="$4"
    local source_url="$5"
    local needs_conversion="${6:-false}"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Determine NAS path based on vendor
    local nas_path=""
    case "$vendor" in
        ollama)
            nas_path="$OLLAMA_DIR/$model_name"
            ;;
        huggingface)
            nas_path="$HUGGINGFACE_DIR/$model_name"
            ;;
        gguf-direct|thebloke)
            nas_path="$GGUF_DIR/$model_name"
            ;;
        meta)
            nas_path="$META_DIR/$model_name"
            ;;
    esac

    # Create temporary file
    local temp_file=$(mktemp)

    # Update inventory using jq
    jq --arg model "$model_name" \
       --arg vendor "$vendor" \
       --arg disk "$disk_usage" \
       --arg format "$format" \
       --arg source "$source_url" \
       --arg path "$nas_path" \
       --arg time "$timestamp" \
       --argjson conversion "$needs_conversion" \
       '._last_updated = $time |
        .models[$model] = {
          "vendor": $vendor,
          "format": $format,
          "disk_usage": $disk,
          "downloaded": $time,
          "source_url": $source,
          "nas_path": $path,
          "needs_conversion": $conversion,
          "distributed_to": [],
          "version": "latest"
        }' "$INVENTORY_FILE" > "$temp_file"

    mv "$temp_file" "$INVENTORY_FILE"

    log_info "Inventory updated for: $model_name (vendor: $vendor)"
}

# List supported vendors
list_vendors() {
    if [[ ! -f "$VENDOR_SOURCES" ]]; then
        log_error "Vendor sources file not found: $VENDOR_SOURCES"
        return 1
    fi

    echo ""
    echo -e "${CYAN}Supported Vendors${NC}"
    echo "================="
    echo ""

    jq -r '.vendors | to_entries[] |
           "\(.key):\n  Name: \(.value.name)\n  Type: \(.value.type)\n  Download: \(.value.download_method)\n  Formats: \(.value.supported_formats | join(", "))\n  Auth: \(if .value.requires_auth then "Required" else "Not required" end)\n  Notes: \(.value.notes)\n"' \
       "$VENDOR_SOURCES"
}

# List available models
list_models() {
    if [[ ! -f "$VENDOR_SOURCES" ]]; then
        log_error "Vendor sources file not found: $VENDOR_SOURCES"
        return 1
    fi

    echo ""
    echo -e "${CYAN}Pre-configured Models${NC}"
    echo "====================="
    echo ""

    jq -r '.models | to_entries[] |
           "\(.key)\n  Vendor: \(.value.vendor)\n  Format: \(.value.format)\n  License: \(.value.license // "N/A")\n  Approval: \(if .value.requires_approval then "Required" else "Not required" end)\n  URL: \(.value.source_url)\n"' \
       "$VENDOR_SOURCES"
}

# Show usage
show_usage() {
    cat <<EOF
${CYAN}Multi-Vendor Model Downloader${NC}
Download AI models from ANY vendor to NAS central repository

${GREEN}Supported Vendors:${NC}
  - Ollama (native registry)
  - Hugging Face (with optional GGUF conversion)
  - Direct GGUF downloads (TheBloke, etc.)
  - Meta/Facebook LLaMA (manual)
  - Mistral AI
  - Google Gemma
  - Microsoft Phi
  - Alibaba Qwen

${GREEN}Usage:${NC}
  $0 <model-identifier>
  $0 --list-vendors
  $0 --list-models
  $0 --convert-to-gguf <hf-model-path>

${GREEN}Model Identifier Formats:${NC}
  ollama:MODEL_NAME                    - Ollama registry
  hf:ORG/MODEL                         - Hugging Face
  gguf:URL                             - Direct GGUF download
  gguf:HF_ORG/HF_MODEL/file.gguf      - GGUF from HuggingFace
  meta:MODEL_NAME                      - Meta (manual)
  MODEL_NAME (no prefix)               - Auto-detect

${GREEN}Examples:${NC}
  # Ollama models (easiest)
  $0 ollama:codestral:22b
  $0 codestral:22b                     # Auto-detects Ollama

  # Hugging Face models
  $0 hf:meta-llama/Llama-2-7b-chat-hf
  $0 hf:mistralai/Mistral-7B-v0.1
  $0 hf:microsoft/phi-2

  # Pre-quantized GGUF (ready to use, no conversion)
  $0 gguf:TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_K_M.gguf
  $0 gguf:https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q5_K_M.gguf

  # List available vendors and models
  $0 --list-vendors
  $0 --list-models

  # Convert HF model to GGUF
  $0 --convert-to-gguf meta-llama/Llama-2-7b-chat-hf

${GREEN}Environment Variables:${NC}
  NAS_MODELS_DIR   NAS mount point (default: /mnt/nas/ai-models)

${GREEN}Directory Structure:${NC}
  /mnt/nas/ai-models/
  ├── ollama/              # Ollama models
  ├── huggingface/         # HuggingFace models (original format)
  ├── gguf/                # GGUF files (converted or direct)
  ├── facebook/            # Official Meta models
  └── manifests/           # Inventory and metadata
EOF
}

# Main
main() {
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 0
    fi

    check_prerequisites

    case "$1" in
        -h|--help)
            show_usage
            exit 0
            ;;
        --list-vendors)
            list_vendors
            exit 0
            ;;
        --list-models)
            list_models
            exit 0
            ;;
        --convert-to-gguf)
            if [[ $# -lt 2 ]]; then
                log_error "Please specify Hugging Face model path"
                exit 1
            fi
            convert_hf_to_gguf "$2"
            exit $?
            ;;
        *)
            # Parse model identifier
            local model_id="$1"
            IFS='|' read -r vendor model_name source_url <<< "$(parse_model_id "$model_id")"

            log_info "Model: $model_name"
            log_info "Vendor: $vendor"
            log_info "Source: $source_url"
            echo ""

            # Download based on vendor
            case "$vendor" in
                ollama)
                    download_ollama "$model_name"
                    ;;
                huggingface)
                    download_huggingface "$model_name"
                    ;;
                gguf-direct|thebloke)
                    download_gguf "$source_url"
                    ;;
                meta)
                    download_meta "$model_name"
                    ;;
                *)
                    log_error "Unknown vendor: $vendor"
                    exit 1
                    ;;
            esac

            exit_code=$?

            if [[ $exit_code -eq 0 ]]; then
                echo ""
                log_success "Model downloaded successfully!"
                log_info "Model stored in: $NAS_MODELS_DIR"
                log_info "Next step: Distribute to nodes using distribute-to-nodes.sh"
            else
                echo ""
                log_error "Model download failed"
            fi

            exit $exit_code
            ;;
    esac
}

main "$@"
