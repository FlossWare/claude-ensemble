#!/usr/bin/env bash

# distribute-to-nodes.sh - Distribute models from NAS to fleet nodes
#
# Usage:
#   distribute-to-nodes.sh                  # Distribute all models per registry
#   distribute-to-nodes.sh <model-name>     # Distribute specific model
#   distribute-to-nodes.sh --node <node>    # Distribute to specific node
#
# Examples:
#   distribute-to-nodes.sh
#   distribute-to-nodes.sh codestral:22b
#   distribute-to-nodes.sh --node server-02
#
# Environment Variables:
#   NAS_MODELS_DIR - NAS mount point (default: /mnt/nas/ai-models)

set -euo pipefail

# Configuration
NAS_MODELS_DIR="${NAS_MODELS_DIR:-/mnt/nas/ai-models}"
MODELS_DIR="$NAS_MODELS_DIR/ollama"
MANIFESTS_DIR="$NAS_MODELS_DIR/manifests"
INVENTORY_FILE="$MANIFESTS_DIR/model-inventory.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FLEET_REGISTRY="$PROJECT_DIR/fleet-model-registry.json"
DISTRIBUTION_LOG="$MANIFESTS_DIR/distribution-log.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_progress() {
    echo -e "${CYAN}[PROGRESS]${NC} $*"
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

    # Check if fleet registry exists
    if [[ ! -f "$FLEET_REGISTRY" ]]; then
        log_error "Fleet registry not found: $FLEET_REGISTRY"
        log_info "Please run fleet-auto-distributor first to generate registry"
        exit 1
    fi

    # Check if inventory exists
    if [[ ! -f "$INVENTORY_FILE" ]]; then
        log_error "Model inventory not found: $INVENTORY_FILE"
        log_info "Please run download-to-nas.sh first to download models"
        exit 1
    fi

    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        log_error "jq not found. Please install jq for JSON processing."
        exit 1
    fi

    # Check if rsync is available
    if ! command -v rsync &> /dev/null; then
        log_error "rsync not found. Please install rsync for efficient file transfer."
        exit 1
    fi

    # Initialize distribution log if it doesn't exist
    if [[ ! -f "$DISTRIBUTION_LOG" ]]; then
        cat > "$DISTRIBUTION_LOG" <<EOF
{
  "_comment": "Distribution log - Track model deployment to nodes",
  "distributions": []
}
EOF
    fi

    log_success "Prerequisites check passed"
}

# Get models assigned to a node from fleet registry
get_node_models() {
    local node_name="$1"

    jq -r --arg node "$node_name" \
       '.nodes[$node].models[]?' \
       "$FLEET_REGISTRY" 2>/dev/null || echo ""
}

# Get all nodes with local models
get_nodes_with_local_models() {
    jq -r '.nodes | to_entries[] |
           select(.value.local_models > 0) |
           .key' "$FLEET_REGISTRY"
}

# Check if model exists in NAS
model_exists_in_nas() {
    local model_name="$1"
    local model_dir="$MODELS_DIR/$model_name"

    [[ -d "$model_dir" ]]
}

# Get node endpoint
get_node_endpoint() {
    local node_name="$1"

    # Try to get from fleet registry
    local endpoint=$(jq -r --arg node "$node_name" \
                        '.models | to_entries[] |
                         select(.value.node == $node and .value.type == "local") |
                         .value.endpoint' "$FLEET_REGISTRY" | head -n1)

    if [[ -n "$endpoint" ]] && [[ "$endpoint" != "null" ]]; then
        # Extract hostname from endpoint (e.g., http://server-02:11434 -> server-02)
        echo "$endpoint" | sed 's|http://||' | cut -d':' -f1
    else
        echo "$node_name"
    fi
}

# Check if node is reachable
check_node_reachable() {
    local node_name="$1"
    local hostname=$(get_node_endpoint "$node_name")

    # Handle localhost specially
    if [[ "$hostname" == "localhost" ]] || [[ "$hostname" == "127.0.0.1" ]]; then
        return 0
    fi

    # Ping check
    if ping -c 1 -W 2 "$hostname" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Distribute model to node
distribute_model_to_node() {
    local model_name="$1"
    local node_name="$2"
    local model_dir="$MODELS_DIR/$model_name"
    local hostname=$(get_node_endpoint "$node_name")
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    log_progress "Distributing $model_name to $node_name ($hostname)..."

    # Check if model exists in NAS
    if ! model_exists_in_nas "$model_name"; then
        log_error "Model not found in NAS: $model_name"
        return 1
    fi

    # Check if node is reachable
    if ! check_node_reachable "$node_name"; then
        log_warn "Node unreachable: $node_name (skipping)"
        return 1
    fi

    # Get model size for progress reporting
    local model_size=$(du -sh "$model_dir" | awk '{print $1}')
    log_info "  Model size: $model_size"

    # Determine destination path
    local remote_ollama_dir="\$HOME/.ollama/models"

    # For localhost, use local path
    if [[ "$hostname" == "localhost" ]] || [[ "$hostname" == "127.0.0.1" ]]; then
        remote_ollama_dir="$HOME/.ollama/models"

        # Import to local Ollama
        log_info "  Copying model files to local Ollama directory..."

        # Copy manifests
        if [[ -d "$model_dir/manifests" ]]; then
            rsync -av --progress "$model_dir/manifests/" "$remote_ollama_dir/manifests/" || {
                log_warn "  Failed to copy manifests"
            }
        fi

        # Copy blobs
        if [[ -d "$model_dir/blobs" ]]; then
            rsync -av --progress "$model_dir/blobs/" "$remote_ollama_dir/blobs/" || {
                log_warn "  Failed to copy blobs"
            }
        fi

        # Verify model is available in Ollama
        if ollama list | grep -q "^${model_name}"; then
            log_success "  Model verified in Ollama: $model_name"
        else
            # Try to pull the model to ensure it's registered
            log_info "  Registering model with Ollama..."
            if ollama pull "$model_name" &>/dev/null; then
                log_success "  Model registered: $model_name"
            else
                log_warn "  Model may need manual verification in Ollama"
            fi
        fi
    else
        # Remote node - use rsync over SSH
        log_info "  Transferring to remote node: $hostname"

        # Copy manifests
        if [[ -d "$model_dir/manifests" ]]; then
            log_progress "    Syncing manifests..."
            rsync -avz --progress -e ssh \
                  "$model_dir/manifests/" \
                  "${hostname}:${remote_ollama_dir}/manifests/" || {
                log_warn "  Failed to sync manifests to $hostname"
            }
        fi

        # Copy blobs
        if [[ -d "$model_dir/blobs" ]]; then
            log_progress "    Syncing blobs..."
            rsync -avz --progress -e ssh \
                  "$model_dir/blobs/" \
                  "${hostname}:${remote_ollama_dir}/blobs/" || {
                log_warn "  Failed to sync blobs to $hostname"
            }
        fi

        # Try to verify model on remote node
        log_info "  Verifying model on remote node..."
        if ssh "$hostname" "ollama list | grep -q '^${model_name}'" 2>/dev/null; then
            log_success "  Model verified on $hostname: $model_name"
        else
            # Try to pull the model to register it
            log_info "  Registering model on remote node..."
            if ssh "$hostname" "ollama pull '$model_name'" &>/dev/null; then
                log_success "  Model registered on $hostname: $model_name"
            else
                log_warn "  Model may need manual verification on $hostname"
            fi
        fi
    fi

    # Update inventory
    update_distribution_tracking "$model_name" "$node_name" "$timestamp" "success"

    log_success "Distribution complete: $model_name -> $node_name"
    return 0
}

# Update distribution tracking
update_distribution_tracking() {
    local model_name="$1"
    local node_name="$2"
    local timestamp="$3"
    local status="$4"

    # Update model inventory
    local temp_file=$(mktemp)

    jq --arg model "$model_name" \
       --arg node "$node_name" \
       --arg time "$timestamp" \
       '(.models[$model].distributed_to // []) += [$node] |
        .models[$model].distributed_to |= unique |
        .models[$model].last_distributed = $time |
        ._last_updated = $time' \
       "$INVENTORY_FILE" > "$temp_file"

    mv "$temp_file" "$INVENTORY_FILE"

    # Add to distribution log
    temp_file=$(mktemp)

    jq --arg model "$model_name" \
       --arg node "$node_name" \
       --arg time "$timestamp" \
       --arg status "$status" \
       '.distributions += [{
          "model": $model,
          "node": $node,
          "timestamp": $time,
          "status": $status
        }]' "$DISTRIBUTION_LOG" > "$temp_file"

    mv "$temp_file" "$DISTRIBUTION_LOG"
}

# Distribute all models according to fleet registry
distribute_all() {
    log_info "Starting full fleet distribution..."
    echo ""

    # Get all nodes with local models
    mapfile -t nodes < <(get_nodes_with_local_models)

    if [[ ${#nodes[@]} -eq 0 ]]; then
        log_warn "No nodes with local models found in fleet registry"
        return 1
    fi

    log_info "Found ${#nodes[@]} nodes with local model assignments"
    echo ""

    local total_distributions=0
    local successful_distributions=0
    local failed_distributions=0
    local skipped_distributions=0

    for node in "${nodes[@]}"; do
        log_info "Processing node: $node"
        echo ""

        # Get models assigned to this node
        mapfile -t models < <(get_node_models "$node")

        if [[ ${#models[@]} -eq 0 ]]; then
            log_info "  No models assigned to $node"
            continue
        fi

        # Filter for local models only
        local local_models=()
        for model in "${models[@]}"; do
            # Check if model is a local Ollama model (contains ':')
            if [[ "$model" == *:* ]]; then
                local_models+=("$model")
            fi
        done

        if [[ ${#local_models[@]} -eq 0 ]]; then
            log_info "  No local models assigned to $node"
            continue
        fi

        log_info "  Assigned models: ${#local_models[@]}"

        for model in "${local_models[@]}"; do
            ((total_distributions++))

            if ! model_exists_in_nas "$model"; then
                log_warn "  Model not in NAS: $model (skipping)"
                ((skipped_distributions++))
                continue
            fi

            if distribute_model_to_node "$model" "$node"; then
                ((successful_distributions++))
            else
                ((failed_distributions++))
            fi

            echo ""
        done

        echo ""
    done

    # Summary
    echo ""
    echo "Distribution Summary"
    echo "===================="
    echo "Total distributions attempted: $total_distributions"
    log_success "Successful: $successful_distributions"
    if [[ $failed_distributions -gt 0 ]]; then
        log_error "Failed: $failed_distributions"
    fi
    if [[ $skipped_distributions -gt 0 ]]; then
        log_warn "Skipped: $skipped_distributions"
    fi

    return 0
}

# Distribute specific model to all assigned nodes
distribute_model() {
    local model_name="$1"

    log_info "Distributing model: $model_name"
    echo ""

    # Check if model exists in NAS
    if ! model_exists_in_nas "$model_name"; then
        log_error "Model not found in NAS: $model_name"
        log_info "Run: download-to-nas.sh $model_name"
        return 1
    fi

    # Find which node(s) should have this model
    local assigned_node=$(jq -r --arg model "$model_name" \
                             '.models[$model].node' \
                             "$FLEET_REGISTRY" 2>/dev/null)

    if [[ -z "$assigned_node" ]] || [[ "$assigned_node" == "null" ]]; then
        log_error "Model not assigned to any node in fleet registry: $model_name"
        log_info "Run: fleet-auto-distributor.js update-registry"
        return 1
    fi

    log_info "Target node: $assigned_node"
    echo ""

    if distribute_model_to_node "$model_name" "$assigned_node"; then
        log_success "Model distributed successfully"
        return 0
    else
        log_error "Distribution failed"
        return 1
    fi
}

# Distribute all models to specific node
distribute_to_node() {
    local node_name="$1"

    log_info "Distributing all models to node: $node_name"
    echo ""

    # Get models assigned to this node
    mapfile -t models < <(get_node_models "$node_name")

    if [[ ${#models[@]} -eq 0 ]]; then
        log_warn "No models assigned to $node_name"
        return 1
    fi

    # Filter for local models only
    local local_models=()
    for model in "${models[@]}"; do
        if [[ "$model" == *:* ]]; then
            local_models+=("$model")
        fi
    done

    if [[ ${#local_models[@]} -eq 0 ]]; then
        log_warn "No local models assigned to $node_name"
        return 1
    fi

    log_info "Found ${#local_models[@]} local models assigned to $node_name"
    echo ""

    local success_count=0
    local fail_count=0
    local skip_count=0

    for model in "${local_models[@]}"; do
        if ! model_exists_in_nas "$model"; then
            log_warn "Model not in NAS: $model (skipping)"
            ((skip_count++))
            continue
        fi

        if distribute_model_to_node "$model" "$node_name"; then
            ((success_count++))
        else
            ((fail_count++))
        fi

        echo ""
    done

    echo ""
    log_info "Distribution summary for $node_name:"
    log_success "  Successful: $success_count"
    if [[ $fail_count -gt 0 ]]; then
        log_error "  Failed: $fail_count"
    fi
    if [[ $skip_count -gt 0 ]]; then
        log_warn "  Skipped: $skip_count"
    fi

    return 0
}

# Show usage
show_usage() {
    cat <<EOF
Distribute models from NAS to fleet nodes

Usage:
  $0                      # Distribute all models per fleet registry
  $0 <model-name>         # Distribute specific model
  $0 --node <node-name>   # Distribute all models to specific node
  $0 --verify             # Verify distribution status
  $0 --stats              # Show distribution statistics

Options:
  --node <name>    Distribute to specific node
  --verify         Verify all distributions
  --stats          Show distribution statistics
  -h, --help       Show this help message

Environment Variables:
  NAS_MODELS_DIR   NAS mount point (default: /mnt/nas/ai-models)

Examples:
  $0                          # Full fleet distribution
  $0 codestral:22b            # Distribute one model
  $0 --node server-02         # Distribute to one node
  $0 --verify                 # Verify all distributions
  $0 --stats                  # Show statistics
EOF
}

# Show distribution statistics
show_stats() {
    log_info "Distribution Statistics"
    echo "======================="
    echo ""

    # Models in NAS
    local nas_models=$(jq -r '.models | length' "$INVENTORY_FILE")
    echo "Models in NAS: $nas_models"

    # Distribution count
    local dist_count=$(jq -r '.distributions | length' "$DISTRIBUTION_LOG")
    echo "Total distributions: $dist_count"

    echo ""
    echo "Models by distribution status:"
    jq -r '.models | to_entries[] |
           "\(.key): \(.value.distributed_to | length) nodes - [\(.value.distributed_to | join(", "))]"' \
       "$INVENTORY_FILE"

    echo ""
    echo "Recent distributions (last 10):"
    jq -r '.distributions[-10:] | reverse[] |
           "\(.timestamp): \(.model) -> \(.node) [\(.status)]"' \
       "$DISTRIBUTION_LOG"
}

# Verify distribution
verify_distribution() {
    log_info "Verifying distribution status..."
    echo ""

    mapfile -t nodes < <(get_nodes_with_local_models)

    for node in "${nodes[@]}"; do
        echo "Node: $node"
        mapfile -t models < <(get_node_models "$node")

        for model in "${models[@]}"; do
            if [[ "$model" != *:* ]]; then
                continue  # Skip cloud models
            fi

            local distributed=$(jq -r --arg model "$model" --arg node "$node" \
                                  '.models[$model].distributed_to | index($node) != null' \
                                  "$INVENTORY_FILE")

            if [[ "$distributed" == "true" ]]; then
                echo "  ✓ $model (distributed)"
            else
                echo "  ✗ $model (not distributed)"
            fi
        done
        echo ""
    done
}

# Main
main() {
    if [[ $# -eq 0 ]]; then
        check_prerequisites
        distribute_all
        exit $?
    fi

    case "$1" in
        -h|--help)
            show_usage
            exit 0
            ;;
        --verify)
            check_prerequisites
            verify_distribution
            exit 0
            ;;
        --stats)
            check_prerequisites
            show_stats
            exit 0
            ;;
        --node)
            if [[ $# -lt 2 ]]; then
                log_error "Please specify node name"
                exit 1
            fi
            check_prerequisites
            distribute_to_node "$2"
            exit $?
            ;;
        *)
            check_prerequisites
            distribute_model "$1"
            exit $?
            ;;
    esac
}

main "$@"
