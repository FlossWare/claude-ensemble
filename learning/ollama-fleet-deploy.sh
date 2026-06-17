#!/bin/bash

################################################################################
# Ollama Fleet Deployment Script
#
# Deploys Ollama and distributes models across fleet nodes
#
# Usage:
#   ./ollama-fleet-deploy.sh install-ollama <node>    Install Ollama on node
#   ./ollama-fleet-deploy.sh migrate-model <model> <target-node>    Migrate model
#   ./ollama-fleet-deploy.sh deploy-all               Full fleet deployment
#   ./ollama-fleet-deploy.sh verify                   Verify deployment
################################################################################

set -euo pipefail

REGISTRY_FILE="$HOME/.claude/learning/ollama-fleet-distribution.json"
OLLAMA_MODELS_DIR="$HOME/.ollama/models"
LOG_FILE="$HOME/.claude/learning/logs/ollama-deploy-$(date +%Y%m%d-%H%M%S).log"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $*" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE" >&2
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $*" | tee -a "$LOG_FILE"
}

# Check prerequisites
check_prereqs() {
    if [[ ! -f "$REGISTRY_FILE" ]]; then
        error "Registry file not found: $REGISTRY_FILE"
        exit 1
    fi

    if ! command -v jq &> /dev/null; then
        error "jq is required but not installed"
        exit 1
    fi

    mkdir -p "$(dirname "$LOG_FILE")"
}

# Install Ollama on a remote node
install_ollama_remote() {
    local node=$1

    log "Installing Ollama on $node..."

    # Check if node is reachable
    if ! ssh "$node" "echo 'Connection successful'" 2>/dev/null; then
        error "Cannot connect to $node via SSH"
        return 1
    fi

    # Install Ollama (official install script)
    ssh "$node" 'bash -c "curl -fsSL https://ollama.com/install.sh | sh"'

    # Start Ollama service
    ssh "$node" 'sudo systemctl enable ollama && sudo systemctl start ollama'

    # Wait for Ollama to be ready
    for i in {1..30}; do
        if ssh "$node" "curl -s http://localhost:11434/api/tags" &>/dev/null; then
            log "Ollama is ready on $node"
            return 0
        fi
        sleep 2
    done

    error "Ollama failed to start on $node"
    return 1
}

# Export a model from localhost Ollama
export_model() {
    local model=$1
    local export_dir=$2

    log "Exporting model: $model"

    # Create export directory
    mkdir -p "$export_dir"

    # Copy model blobs and manifests
    # Ollama stores models in ~/.ollama/models/
    # Structure: blobs/sha256-* and manifests/registry.ollama.ai/library/<model>/latest

    local model_name="${model%%:*}"
    local model_tag="${model#*:}"
    [[ "$model_tag" == "$model" ]] && model_tag="latest"

    local manifest_path="$OLLAMA_MODELS_DIR/manifests/registry.ollama.ai/library/$model_name/$model_tag"

    if [[ ! -f "$manifest_path" ]]; then
        error "Model manifest not found: $manifest_path"
        return 1
    fi

    # Parse manifest to find required blobs
    local blobs=()
    while IFS= read -r digest; do
        blobs+=("$digest")
    done < <(jq -r '.layers[].digest, .config.digest' "$manifest_path" 2>/dev/null || echo "")

    if [[ ${#blobs[@]} -eq 0 ]]; then
        error "No blobs found in manifest for $model"
        return 1
    fi

    # Copy blobs
    for digest in "${blobs[@]}"; do
        local blob_file="$OLLAMA_MODELS_DIR/blobs/$digest"
        if [[ -f "$blob_file" ]]; then
            cp "$blob_file" "$export_dir/"
            log "Copied blob: $digest"
        else
            warn "Blob not found: $blob_file"
        fi
    done

    # Copy manifest
    mkdir -p "$export_dir/manifests"
    cp "$manifest_path" "$export_dir/manifests/"

    log "Model $model exported to $export_dir"
}

# Import a model to remote Ollama
import_model_remote() {
    local node=$1
    local model=$2
    local export_dir=$3

    log "Importing model $model to $node..."

    # Create remote directories
    ssh "$node" "mkdir -p ~/.ollama/models/blobs ~/.ollama/models/manifests/registry.ollama.ai/library"

    # Copy blobs
    rsync -avz --progress "$export_dir/"*.sha256-* "$node:~/.ollama/models/blobs/" 2>/dev/null || true

    # Copy manifest
    local model_name="${model%%:*}"
    local model_tag="${model#*:}"
    [[ "$model_tag" == "$model" ]] && model_tag="latest"

    ssh "$node" "mkdir -p ~/.ollama/models/manifests/registry.ollama.ai/library/$model_name"
    scp "$export_dir/manifests/"* "$node:~/.ollama/models/manifests/registry.ollama.ai/library/$model_name/$model_tag"

    # Verify model is available
    if ssh "$node" "ollama list | grep -q '$model_name'" 2>/dev/null; then
        log "Model $model successfully imported to $node"
        return 0
    else
        warn "Model import verification failed - trying direct pull"
        ssh "$node" "ollama pull $model"
    fi
}

# Migrate a single model from localhost to target node
migrate_model() {
    local model=$1
    local target_node=$2

    log "Migrating $model to $target_node..."

    # Skip localhost
    if [[ "$target_node" == "localhost" ]]; then
        info "$model staying on localhost - skipping migration"
        return 0
    fi

    # Export model
    local export_dir="/tmp/ollama-export-$model"
    export_dir="${export_dir//:/-}" # Replace : with - for filesystem

    if ! export_model "$model" "$export_dir"; then
        error "Failed to export $model"
        return 1
    fi

    # Import to target
    if ! import_model_remote "$target_node" "$model" "$export_dir"; then
        error "Failed to import $model to $target_node"
        rm -rf "$export_dir"
        return 1
    fi

    # Cleanup export
    rm -rf "$export_dir"

    log "Migration complete: $model -> $target_node"
}

# Deploy all models according to registry
deploy_all() {
    log "Starting full fleet deployment..."

    # Extract node assignments from registry
    local nodes=$(jq -r '.fleet_strategy.node_assignments | keys[]' "$REGISTRY_FILE")

    # Install Ollama on each node (except localhost)
    for node in $nodes; do
        if [[ "$node" != "localhost" ]]; then
            install_ollama_remote "$node" || warn "Failed to install Ollama on $node"
        fi
    done

    # Migrate models
    for node in $nodes; do
        log "Deploying models to $node..."

        local models=$(jq -r ".fleet_strategy.node_assignments[\"$node\"].models[].name" "$REGISTRY_FILE")

        for model in $models; do
            if [[ "$node" == "localhost" ]]; then
                # Verify model exists locally
                if ! ollama list | grep -q "${model%%:*}"; then
                    warn "Model $model not found on localhost - pulling..."
                    ollama pull "$model"
                fi
            else
                # Migrate to remote node
                migrate_model "$model" "$node" || warn "Failed to migrate $model to $node"
            fi
        done
    done

    log "Fleet deployment complete!"
}

# Verify deployment
verify_deployment() {
    log "Verifying fleet deployment..."

    local nodes=$(jq -r '.fleet_strategy.node_assignments | keys[]' "$REGISTRY_FILE")
    local total_models=0
    local verified_models=0

    for node in $nodes; do
        info "Checking $node..."

        local expected_models=$(jq -r ".fleet_strategy.node_assignments[\"$node\"].models[].name" "$REGISTRY_FILE")

        for model in $expected_models; do
            total_models=$((total_models + 1))

            local model_name="${model%%:*}"

            if [[ "$node" == "localhost" ]]; then
                if ollama list | grep -q "$model_name"; then
                    echo -e "  ${GREEN}✓${NC} $model"
                    verified_models=$((verified_models + 1))
                else
                    echo -e "  ${RED}✗${NC} $model"
                fi
            else
                if ssh "$node" "ollama list | grep -q '$model_name'" 2>/dev/null; then
                    echo -e "  ${GREEN}✓${NC} $model"
                    verified_models=$((verified_models + 1))
                else
                    echo -e "  ${RED}✗${NC} $model"
                fi
            fi
        done
    done

    log "Verification complete: $verified_models/$total_models models deployed successfully"

    if [[ $verified_models -eq $total_models ]]; then
        return 0
    else
        return 1
    fi
}

# Main command dispatcher
main() {
    check_prereqs

    local command=${1:-}

    case "$command" in
        install-ollama)
            local node=${2:-}
            if [[ -z "$node" ]]; then
                error "Usage: $0 install-ollama <node>"
                exit 1
            fi
            install_ollama_remote "$node"
            ;;

        migrate-model)
            local model=${2:-}
            local node=${3:-}
            if [[ -z "$model" || -z "$node" ]]; then
                error "Usage: $0 migrate-model <model> <target-node>"
                exit 1
            fi
            migrate_model "$model" "$node"
            ;;

        deploy-all)
            deploy_all
            ;;

        verify)
            verify_deployment
            ;;

        *)
            echo "Ollama Fleet Deployment Script"
            echo ""
            echo "Usage:"
            echo "  $0 install-ollama <node>              Install Ollama on remote node"
            echo "  $0 migrate-model <model> <node>       Migrate single model to node"
            echo "  $0 deploy-all                         Deploy all models per registry"
            echo "  $0 verify                             Verify deployment"
            echo ""
            echo "Examples:"
            echo "  $0 install-ollama server-01"
            echo "  $0 migrate-model 'qwen2.5-coder:7b' server-02"
            echo "  $0 deploy-all"
            echo "  $0 verify"
            exit 0
            ;;
    esac
}

main "$@"
