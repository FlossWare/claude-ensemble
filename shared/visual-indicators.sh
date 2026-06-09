#!/bin/bash
# Visual Indicators for Multi-AI Consensus
# Borrowed from skills-ai for testing

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;90m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# Unicode symbols
CHECK="✓"
CROSS="✗"
ARROW="→"
BULLET="•"
ROBOT="🤖"
BRAIN="🧠"
GEAR="⚙️"
SPARKLE="✨"
THINKING="💭"
CONSENSUS="🎯"

# Model colors (for visual distinction)
MODEL_COLORS=(
  "$BLUE"     # Opus
  "$CYAN"     # Sonnet
  "$PURPLE"   # GPT-4o
  "$YELLOW"   # Gemini
  "$GREEN"    # Haiku
)

# Header functions
header() {
  echo -e "\n${BOLD}${BLUE}═══════════════════════════════════════════════════════${RESET}"
  echo -e "${BOLD}${WHITE}  $1${RESET}"
  echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════${RESET}\n"
}

subheader() {
  echo -e "\n${BOLD}${CYAN}▸ $1${RESET}"
}

# Status functions
success() {
  echo -e "${GREEN}${CHECK}${RESET} $1"
}

error() {
  echo -e "${RED}${CROSS}${RESET} $1"
}

warning() {
  echo -e "${YELLOW}${BULLET}${RESET} $1"
}

info() {
  echo -e "${BLUE}${BULLET}${RESET} $1"
}

# Multi-AI specific
worker_start() {
  local worker_num=$1
  local model=$2
  local color=${MODEL_COLORS[$worker_num]}
  echo -e "${color}${ROBOT} Worker ${worker_num}: ${model}${RESET} ${DIM}analyzing...${RESET}"
}

worker_complete() {
  local worker_num=$1
  local model=$2
  local color=${MODEL_COLORS[$worker_num]}
  echo -e "${color}${CHECK} Worker ${worker_num}: ${model}${RESET} ${DIM}complete${RESET}"
}

arbiter_start() {
  local model=$1
  echo -e "\n${BOLD}${PURPLE}${BRAIN} Arbiter: ${model}${RESET} ${DIM}synthesizing consensus...${RESET}"
}

arbiter_complete() {
  echo -e "${BOLD}${GREEN}${CONSENSUS} Consensus reached!${RESET}"
}

# Progress indicator
progress_bar() {
  local current=$1
  local total=$2
  local width=40
  local percent=$((current * 100 / total))
  local filled=$((current * width / total))

  printf "\r${BLUE}Progress: [${RESET}"
  for ((i=0; i<filled; i++)); do printf "${GREEN}█${RESET}"; done
  for ((i=filled; i<width; i++)); do printf "${GRAY}░${RESET}"; done
  printf "${BLUE}] ${percent}%%${RESET}"

  if [ "$current" -eq "$total" ]; then
    echo ""
  fi
}

# Phase indicator
phase() {
  local phase_name=$1
  echo -e "\n${BOLD}${CYAN}${GEAR} Phase: ${phase_name}${RESET}"
}

# Consensus quality indicator
consensus_quality() {
  local score=$1  # 0.0 - 1.0

  if (( $(echo "$score >= 0.8" | bc -l) )); then
    echo -e "${GREEN}${CONSENSUS} High consensus (${score})${RESET}"
  elif (( $(echo "$score >= 0.6" | bc -l) )); then
    echo -e "${YELLOW}${CONSENSUS} Medium consensus (${score})${RESET}"
  else
    echo -e "${RED}${CONSENSUS} Low consensus (${score})${RESET}"
  fi
}

# Model comparison table
model_comparison() {
  echo -e "\n${BOLD}Model Comparison:${RESET}"
  echo -e "${GRAY}┌─────────────┬──────────────────────────────────────┐${RESET}"
  echo -e "${GRAY}│${RESET} ${BOLD}Model${RESET}       ${GRAY}│${RESET} ${BOLD}Finding${RESET}                              ${GRAY}│${RESET}"
  echo -e "${GRAY}├─────────────┼──────────────────────────────────────┤${RESET}"
}

model_row() {
  local model=$1
  local finding=$2
  local color=$3

  printf "${GRAY}│${RESET} ${color}%-11s${RESET} ${GRAY}│${RESET} %-36s ${GRAY}│${RESET}\n" "$model" "$finding"
}

model_comparison_end() {
  echo -e "${GRAY}└─────────────┴──────────────────────────────────────┘${RESET}"
}

# Summary box
summary_box() {
  local title=$1
  shift
  local lines=("$@")

  echo -e "\n${BOLD}${BLUE}┌────────────────────────────────────────────────────┐${RESET}"
  echo -e "${BOLD}${BLUE}│${RESET} ${BOLD}${WHITE}${title}${RESET}"
  echo -e "${BOLD}${BLUE}├────────────────────────────────────────────────────┤${RESET}"

  for line in "${lines[@]}"; do
    printf "${BOLD}${BLUE}│${RESET} %-50s ${BOLD}${BLUE}│${RESET}\n" "$line"
  done

  echo -e "${BOLD}${BLUE}└────────────────────────────────────────────────────┘${RESET}\n"
}

# Export functions for use in other scripts
export -f header subheader success error warning info
export -f worker_start worker_complete arbiter_start arbiter_complete
export -f progress_bar phase consensus_quality
export -f model_comparison model_row model_comparison_end summary_box
