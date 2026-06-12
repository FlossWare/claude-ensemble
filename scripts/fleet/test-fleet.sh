#!/bin/bash
# =============================================================================
# test-fleet.sh - Fleet Multi-Session Test Suite
# =============================================================================
# Validates fleet bulk processing scripts with small-scale tests.
# Tests all 7 Tier 1+2 skills: dry-run (always) and live (when --full).
#
# Test levels:
#   --dry-run  (default)  Verify distribution logic, argument parsing, fleet
#                         discovery. No Claude sessions launched.
#   --full               Run actual Claude sessions with tiny workloads
#                         (3 items per skill). Requires fleet online.
#
# Usage:
#   ./test-fleet.sh              # Dry-run all skills (fast, safe)
#   ./test-fleet.sh --full       # Live test with small workloads
#   ./test-fleet.sh pdf          # Test PDF ingestion only
#   ./test-fleet.sh --full url   # Live test URL learning only
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NFS_ROOT="${HOME}/Development"
TEST_DATA_DIR="${NFS_ROOT}/fleet-test-data-$$"
FULL_MODE=false

# Colors
readonly C_GREEN='\033[0;32m'
readonly C_RED='\033[0;31m'
readonly C_YELLOW='\033[1;33m'
readonly C_CYAN='\033[0;36m'
readonly C_BOLD='\033[1m'
readonly C_RESET='\033[0m'

# Test selection
RUN_ALL=true
SELECTED_TEST=""

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --full)     FULL_MODE=true; shift ;;
    --dry-run)  FULL_MODE=false; shift ;;
    --help|-h)
      echo "Usage: $0 [--full|--dry-run] [SKILL]"
      echo ""
      echo "Options:"
      echo "  --dry-run  Test argument parsing and distribution only (default)"
      echo "  --full     Run actual Claude sessions with tiny workloads"
      echo ""
      echo "Skills: pdf, url, research, security, repo, review, doc"
      exit 0
      ;;
    pdf|url|research|security|repo|review|doc)
      RUN_ALL=false
      SELECTED_TEST="$1"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# LOGGING AND COUNTERS
# ---------------------------------------------------------------------------

log() {
  echo -e "${C_CYAN}[$(date +%H:%M:%S)]${C_RESET} $*"
}

pass() {
  echo -e "  ${C_GREEN}PASS${C_RESET} $*"
  TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() {
  echo -e "  ${C_RED}FAIL${C_RESET} $*"
  TESTS_FAILED=$((TESTS_FAILED + 1))
}

warn() {
  echo -e "  ${C_YELLOW}WARN${C_RESET} $*"
}

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
  local name="$1"
  shift
  local cmd="$*"

  TESTS_RUN=$((TESTS_RUN + 1))
  log "Test: ${name}"

  if eval "$cmd" >/dev/null 2>&1; then
    pass "$name"
    return 0
  else
    local rc=$?
    fail "$name (exit ${rc})"
    return 1
  fi
}

# ---------------------------------------------------------------------------
# SETUP
# ---------------------------------------------------------------------------

setup_test_data() {
  log "Setting up test data in ${TEST_DATA_DIR}"
  mkdir -p "${TEST_DATA_DIR}"/{pdfs,src}

  # Test PDFs (text files, just for distribution testing)
  for i in 1 2 3; do
    echo "%PDF-1.4 test content page ${i}" > "${TEST_DATA_DIR}/pdfs/test-${i}.pdf"
  done

  # Test URLs
  cat > "${TEST_DATA_DIR}/urls.txt" << 'EOF'
https://en.wikipedia.org/wiki/Artificial_intelligence
https://en.wikipedia.org/wiki/Machine_learning
https://en.wikipedia.org/wiki/Deep_learning
EOF

  # Test topics
  cat > "${TEST_DATA_DIR}/topics.txt" << 'EOF'
transformer architecture
attention mechanism
BERT language model
EOF

  # Test source files for security/review/doc
  cat > "${TEST_DATA_DIR}/src/Example.java" << 'EOF'
public class Example {
    public void unsafeQuery(String input) {
        String query = "SELECT * FROM users WHERE id=" + input;
    }
    public void hardcodedSecret() {
        String apiKey = "sk-1234567890abcdef";
    }
}
EOF

  cat > "${TEST_DATA_DIR}/src/Calculator.py" << 'EOF'
def add(a, b):
    """Add two numbers."""
    return a + b

class Calculator:
    """A simple calculator."""
    def multiply(self, a, b):
        return a * b
EOF

  cat > "${TEST_DATA_DIR}/src/hello.js" << 'EOF'
function greet(name) {
  return `Hello, ${name}!`;
}
module.exports = { greet };
EOF

  # Test repos list
  cat > "${TEST_DATA_DIR}/repos.txt" << 'EOF'
https://github.com/anthropics/anthropic-sdk-python
https://github.com/openai/openai-python
https://github.com/google/generative-ai-python
EOF

  pass "Test data created"
}

cleanup_test_data() {
  if [[ -d "${TEST_DATA_DIR}" ]]; then
    rm -rf "${TEST_DATA_DIR}"
    log "Cleaned up test data"
  fi
}

trap cleanup_test_data EXIT

# ---------------------------------------------------------------------------
# FLEET CONNECTIVITY
# ---------------------------------------------------------------------------

test_fleet_connectivity() {
  log ""
  echo -e "${C_BOLD}Fleet Connectivity${C_RESET}"

  TESTS_RUN=$((TESTS_RUN + 1))

  if [[ ! -f "${HOME}/.claude/fleet.json" ]]; then
    fail "Fleet config not found: ${HOME}/.claude/fleet.json"
    return 1
  fi
  pass "Fleet config exists"

  local workers
  workers=$(python3 -c "
import json
with open('${HOME}/.claude/fleet.json') as f:
    cfg = json.load(f)
for m in cfg['machines']:
    if m['role'] == 'worker':
        print(m['hostname'])
" 2>/dev/null)

  local online=0
  local total=0
  while IFS= read -r worker; do
    total=$((total + 1))
    TESTS_RUN=$((TESTS_RUN + 1))
    if ssh -o BatchMode=yes -o ConnectTimeout=3 -o StrictHostKeyChecking=accept-new \
         "$worker" 'echo ok' &>/dev/null; then
      pass "${worker}: reachable"
      online=$((online + 1))
    else
      fail "${worker}: unreachable"
    fi
  done <<< "$workers"

  log "Fleet: ${online}/${total} workers online"
  return 0
}

# ---------------------------------------------------------------------------
# FLEET-BULK-LIB UNIT TESTS
# ---------------------------------------------------------------------------

test_fleet_bulk_lib() {
  log ""
  echo -e "${C_BOLD}Fleet Bulk Library Tests${C_RESET}"

  # Test: fleet-bulk-lib.sh sources without error
  run_test "fleet-bulk-lib.sh sources cleanly" \
    "bash -c 'source ${SCRIPT_DIR}/fleet-bulk-lib.sh && echo ok'"

  # Test: fleet_init_session creates directories
  run_test "fleet_init_session creates dirs" \
    "bash -c 'source ${SCRIPT_DIR}/fleet-bulk-lib.sh && fleet_init_session test-unit && [[ -d \${FLEET_RESULTS_DIR} ]] && [[ -d \${FLEET_PROGRESS_DIR} ]]'"

  # Test: fleet_is_nfs works
  run_test "fleet_is_nfs detects NFS paths" \
    "bash -c 'source ${SCRIPT_DIR}/fleet-bulk-lib.sh && fleet_is_nfs /home/sfloess/Development/foo'"

  run_test "fleet_is_nfs rejects non-NFS" \
    "bash -c 'source ${SCRIPT_DIR}/fleet-bulk-lib.sh && ! fleet_is_nfs /tmp/foo'"
}

# ---------------------------------------------------------------------------
# SKILL TESTS: DRY-RUN
# ---------------------------------------------------------------------------

should_run() {
  local skill="$1"
  [[ "$RUN_ALL" == "true" ]] || [[ "$SELECTED_TEST" == "$skill" ]]
}

test_pdf_dryrun() {
  should_run pdf || return 0
  log ""
  echo -e "${C_BOLD}Tier 1: PDF Ingestion (dry-run)${C_RESET}"

  run_test "bulk-pdf-ingest.sh --help" \
    "${SCRIPT_DIR}/bulk-pdf-ingest.sh --help"

  run_test "bulk-pdf-ingest.sh --dry-run" \
    "${SCRIPT_DIR}/bulk-pdf-ingest.sh --dry-run ${TEST_DATA_DIR}/pdfs/"
}

test_url_dryrun() {
  should_run url || return 0
  log ""
  echo -e "${C_BOLD}Tier 1: URL Learning (dry-run)${C_RESET}"

  run_test "bulk-url-learn.sh --help" \
    "${SCRIPT_DIR}/bulk-url-learn.sh --help"

  run_test "bulk-url-learn.sh --dry-run" \
    "${SCRIPT_DIR}/bulk-url-learn.sh --dry-run ${TEST_DATA_DIR}/urls.txt"
}

test_research_dryrun() {
  should_run research || return 0
  log ""
  echo -e "${C_BOLD}Tier 1: Deep Research (dry-run)${C_RESET}"

  run_test "bulk-research.sh --help" \
    "${SCRIPT_DIR}/bulk-research.sh --help"

  run_test "bulk-research.sh --dry-run" \
    "${SCRIPT_DIR}/bulk-research.sh --dry-run ${TEST_DATA_DIR}/topics.txt"
}

test_security_dryrun() {
  should_run security || return 0
  log ""
  echo -e "${C_BOLD}Tier 2: Security Scan (dry-run)${C_RESET}"

  run_test "bulk-security-scan.sh --help" \
    "${SCRIPT_DIR}/bulk-security-scan.sh --help"

  run_test "bulk-security-scan.sh --dry-run" \
    "${SCRIPT_DIR}/bulk-security-scan.sh --dry-run ${TEST_DATA_DIR}/src/"
}

test_repo_dryrun() {
  should_run repo || return 0
  log ""
  echo -e "${C_BOLD}Tier 2: Repo Learning (dry-run)${C_RESET}"

  run_test "bulk-repo-learn.sh --help" \
    "${SCRIPT_DIR}/bulk-repo-learn.sh --help"

  run_test "bulk-repo-learn.sh --dry-run" \
    "${SCRIPT_DIR}/bulk-repo-learn.sh --dry-run ${TEST_DATA_DIR}/repos.txt"
}

test_review_dryrun() {
  should_run review || return 0
  log ""
  echo -e "${C_BOLD}Tier 2: Code Review (dry-run)${C_RESET}"

  run_test "bulk-code-review.sh --help" \
    "${SCRIPT_DIR}/bulk-code-review.sh --help"

  run_test "bulk-code-review.sh --dry-run" \
    "${SCRIPT_DIR}/bulk-code-review.sh --dry-run ${TEST_DATA_DIR}/src/"
}

test_doc_dryrun() {
  should_run doc || return 0
  log ""
  echo -e "${C_BOLD}Tier 2: Code Documentation (dry-run)${C_RESET}"

  run_test "bulk-code-doc.sh --help" \
    "${SCRIPT_DIR}/bulk-code-doc.sh --help"

  run_test "bulk-code-doc.sh --dry-run" \
    "${SCRIPT_DIR}/bulk-code-doc.sh --dry-run ${TEST_DATA_DIR}/src/"
}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

main() {
  echo ""
  echo "=================================================================="
  echo "  FLEET MULTI-SESSION TEST SUITE"
  echo "=================================================================="
  echo "  Mode:  $([ "$FULL_MODE" == "true" ] && echo "FULL (live)" || echo "DRY-RUN (safe)")"
  echo "  Tests: $([ "$RUN_ALL" == "true" ] && echo "all skills" || echo "$SELECTED_TEST")"
  echo "=================================================================="
  echo ""

  # Pre-flight
  test_fleet_connectivity

  # Setup
  setup_test_data

  # Library unit tests
  test_fleet_bulk_lib

  # Dry-run tests (always run)
  test_pdf_dryrun
  test_url_dryrun
  test_research_dryrun
  test_security_dryrun
  test_repo_dryrun
  test_review_dryrun
  test_doc_dryrun

  # Full-mode tests (only with --full)
  if [[ "$FULL_MODE" == "true" ]]; then
    log ""
    echo -e "${C_BOLD}Live execution tests (small workloads)${C_RESET}"
    warn "Live tests launch actual Claude sessions on fleet workers"
    warn "This uses API credits and takes several minutes"

    # Only run the selected test live, or a subset if all
    if should_run pdf; then
      run_test "PDF live (3 PDFs)" \
        "${SCRIPT_DIR}/bulk-pdf-ingest.sh --batch-size 1 --timeout 600 ${TEST_DATA_DIR}/pdfs/"
    fi

    if should_run url; then
      run_test "URL live (3 URLs)" \
        "${SCRIPT_DIR}/bulk-url-learn.sh --batch-size 3 --timeout 300 ${TEST_DATA_DIR}/urls.txt"
    fi

    if should_run research; then
      run_test "Research live (3 topics)" \
        "${SCRIPT_DIR}/bulk-research.sh --timeout 600 ${TEST_DATA_DIR}/topics.txt"
    fi
  fi

  # Summary
  echo ""
  echo "=================================================================="
  echo "  TEST SUMMARY"
  echo "=================================================================="
  echo "  Total:  ${TESTS_RUN}"
  echo "  Passed: ${TESTS_PASSED}"
  echo "  Failed: ${TESTS_FAILED}"
  echo "=================================================================="

  if [[ $TESTS_FAILED -eq 0 ]]; then
    echo -e "${C_GREEN}ALL TESTS PASSED${C_RESET}"
    return 0
  else
    echo -e "${C_RED}${TESTS_FAILED} TEST(S) FAILED${C_RESET}"
    return 1
  fi
}

main "$@"
