#!/bin/bash
# Skill Helper Functions
# Source this in skills for common utilities

# Source visual indicators if available
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/visual-indicators.sh" ]; then
  source "$SCRIPT_DIR/visual-indicators.sh"
fi

# ============================================================================
# PATH HELPERS
# ============================================================================

get_skills_dir() {
  echo "$HOME/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"
}

get_memory_dir() {
  echo "$(get_skills_dir)/memory"
}

get_workflows_dir() {
  echo "$(get_skills_dir)/workflows"
}

# ============================================================================
# WORKFLOW EXECUTION
# ============================================================================

run_workflow() {
  local workflow_name=$1
  shift
  local args="$@"

  local workflows_dir=$(get_workflows_dir)

  if [ ! -f "$workflows_dir/${workflow_name}.js" ]; then
    error "Workflow not found: ${workflow_name}"
    return 1
  fi

  info "Running workflow: ${workflow_name}"

  # Run with claude CLI (if available) or node
  if command -v claude &> /dev/null; then
    claude workflow run "$workflow_name" $args
  else
    # Fallback to direct execution (requires proper setup)
    cd "$workflows_dir" && node "${workflow_name}.js" $args
  fi
}

# ============================================================================
# MEMORY OPERATIONS
# ============================================================================

search_memory() {
  local query=$1
  local memory_dir=$(get_memory_dir)

  info "Searching memory for: $query"

  # Simple grep-based search (upgrade to vector search later)
  grep -r -i "$query" "$memory_dir"/*.md 2>/dev/null | while IFS=: read -r file line; do
    local basename=$(basename "$file")
    echo "  ${CYAN}${basename}${RESET}: ${DIM}${line}${RESET}"
  done
}

list_memory() {
  local memory_type=$1
  local memory_dir=$(get_memory_dir)

  if [ -z "$memory_type" ]; then
    info "All memory files:"
    ls -1 "$memory_dir"/*.md 2>/dev/null | while read -r file; do
      echo "  - $(basename "$file")"
    done
  else
    info "Memory files (type: $memory_type):"
    grep -l "type: $memory_type" "$memory_dir"/*.md 2>/dev/null | while read -r file; do
      echo "  - $(basename "$file")"
    done
  fi
}

# ============================================================================
# GIT OPERATIONS
# ============================================================================

ensure_git_clean() {
  local skills_dir=$(get_skills_dir)
  cd "$skills_dir" || return 1

  if ! git diff --quiet || ! git diff --cached --quiet; then
    warning "Uncommitted changes in skills repo"
    git status --short
    return 1
  fi

  success "Git working directory clean"
  return 0
}

commit_and_push() {
  local message=$1
  local skills_dir=$(get_skills_dir)

  cd "$skills_dir" || return 1

  git add -A

  if git diff --cached --quiet; then
    warning "No changes to commit"
    return 0
  fi

  info "Committing changes..."
  git commit -m "$message

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

  info "Pushing to remote..."
  if git push; then
    success "Changes pushed to GitLab"
  else
    error "Push failed"
    return 1
  fi
}

# ============================================================================
# VALIDATION
# ============================================================================

validate_workflow_name() {
  local name=$1

  if [[ ! "$name" =~ ^[a-z0-9-]+$ ]]; then
    error "Invalid workflow name: $name (use lowercase, numbers, hyphens only)"
    return 1
  fi

  return 0
}

validate_memory_name() {
  local name=$1

  if [[ ! "$name" =~ ^[a-z0-9_-]+$ ]]; then
    error "Invalid memory name: $name (use lowercase, numbers, underscores, hyphens only)"
    return 1
  fi

  return 0
}

# ============================================================================
# INTERACTIVE HELPERS
# ============================================================================

ask_confirm() {
  local prompt=$1
  local default=${2:-n}

  if [ "$default" = "y" ]; then
    read -p "${prompt} [Y/n]: " response
    response=${response:-y}
  else
    read -p "${prompt} [y/N]: " response
    response=${response:-n}
  fi

  [[ "$response" =~ ^[Yy] ]]
}

select_from_list() {
  local prompt=$1
  shift
  local options=("$@")

  echo "$prompt"
  for i in "${!options[@]}"; do
    echo "  $((i+1)). ${options[$i]}"
  done

  read -p "Select (1-${#options[@]}): " selection

  if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le "${#options[@]}" ]; then
    echo "${options[$((selection-1))]}"
    return 0
  else
    error "Invalid selection"
    return 1
  fi
}

# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================

export -f get_skills_dir get_memory_dir get_workflows_dir
export -f run_workflow
export -f search_memory list_memory
export -f ensure_git_clean commit_and_push
export -f validate_workflow_name validate_memory_name
export -f ask_confirm select_from_list
