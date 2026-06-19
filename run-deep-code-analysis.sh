#!/bin/bash
#
# Run deep code analysis on all specified repositories
# Analyzes: Solenopsis (session, soap, metadata, Solenopsis), FlossWare (all *-java repos), sfdeasy
#

set -e

echo "======================================================================"
echo "DEEP CODE ANALYSIS - All Repositories"
echo "======================================================================"
echo ""

# Define repository groups
SOLENOPSIS_REPOS=(
  ~/Development/github/solenopsis/session
  ~/Development/github/solenopsis/soap
  ~/Development/github/solenopsis/metadata
  ~/Development/github/solenopsis/Solenopsis
)

FLOSSWARE_REPOS=(
  ~/Development/github/FlossWare/civilization-simulator-java
  ~/Development/github/FlossWare/classloader-java
  ~/Development/github/FlossWare/cloudstorage-java
  ~/Development/github/FlossWare/collections-java
  ~/Development/github/FlossWare/commons-java
  ~/Development/github/FlossWare/container-java
  ~/Development/github/FlossWare/curses-java
  ~/Development/github/FlossWare/diskwipe-java
  ~/Development/github/FlossWare/encrypt-java
  ~/Development/github/FlossWare/eventbus-java
  ~/Development/github/FlossWare/filetransfer-java
  ~/Development/github/FlossWare/fs-watcher-java
  ~/Development/github/FlossWare/messaging-java
  ~/Development/github/FlossWare/nexus-java
  ~/Development/github/FlossWare/platform-java
  ~/Development/github/FlossWare/remote-java
  ~/Development/github/FlossWare/resource-monitor-java
  ~/Development/github/FlossWare/threadpool-java
  ~/Development/github/FlossWare/vcs-java
)

SFDEASY_REPOS=(
  ~/Development/redhat/scm/gitlab/cee/customer-platform/sfdeasy
)

# Count repositories
SOLENOPSIS_COUNT=${#SOLENOPSIS_REPOS[@]}
FLOSSWARE_COUNT=${#FLOSSWARE_REPOS[@]}
SFDEASY_COUNT=${#SFDEASY_REPOS[@]}
TOTAL_COUNT=$((SOLENOPSIS_COUNT + FLOSSWARE_COUNT + SFDEASY_COUNT))

echo "Repositories to analyze:"
echo "  Solenopsis: $SOLENOPSIS_COUNT repos"
echo "  FlossWare:  $FLOSSWARE_COUNT repos"
echo "  sfdeasy:    $SFDEASY_COUNT repos"
echo "  TOTAL:      $TOTAL_COUNT repos"
echo ""

# Check before database count
echo "Checking existing code analysis data..."
BEFORE_COUNT=$(psql -h laptop-01 -U sfloess -d learning -t -c "SELECT COUNT(*) FROM code_analysis.chunks;" 2>/dev/null || echo "0")
echo "  Existing chunks: $BEFORE_COUNT"
echo ""

echo "======================================================================"
echo "RUNNING DEEP CODE ANALYSIS"
echo "======================================================================"
echo ""
echo "This will:"
echo "  1. Discover all Java files in ${TOTAL_COUNT} repositories"
echo "  2. Chunk code by method/class/function"
echo "  3. Generate 384-dim vector embeddings"
echo "  4. Store in PostgreSQL code_analysis.chunks table"
echo "  5. Build knowledge graph relationships"
echo ""
echo "Estimated time: 30-60 minutes (depends on codebase size)"
echo ""

# Run via Claude Code workflow
# NOTE: This would need to be invoked through Claude Code, not directly via bash
echo "To run this analysis, use Claude Code:"
echo ""
echo "  Option 1: Via skill invocation"
echo "  Ask Claude: 'Run the deep-code-analysis workflow on all Solenopsis, FlossWare, and sfdeasy repos'"
echo ""
echo "  Option 2: Direct workflow call (in Claude Code session)"
echo "  workflow('deep-code-analysis', {"
echo "    repositories: ["
for repo in "${SOLENOPSIS_REPOS[@]}" "${FLOSSWARE_REPOS[@]}" "${SFDEASY_REPOS[@]}"; do
  echo "      '$repo',"
done
echo "    ],"
echo "    file_patterns: ['**/*.java', '**/*.cls', '**/*.trigger'],"
echo "    chunk_strategy: 'method',"
echo "    enable_graphdb: true,"
echo "    enable_vectordb: true"
echo "  })"
echo ""

echo "======================================================================"
echo "VERIFICATION QUERIES (after analysis completes)"
echo "======================================================================"
echo ""

echo "Check total chunks created:"
echo "  psql -h laptop-01 -U sfloess -d learning -c \\"
echo "    \"SELECT COUNT(*) FROM code_analysis.chunks;\""
echo ""

echo "Check chunks by repository:"
echo "  psql -h laptop-01 -U sfloess -d learning -c \\"
echo "    \"SELECT repository, COUNT(*) as chunks, "
echo "           COUNT(DISTINCT file_path) as files "
echo "     FROM code_analysis.chunks "
echo "     GROUP BY repository "
echo "     ORDER BY chunks DESC;\""
echo ""

echo "Check chunks by type:"
echo "  psql -h laptop-01 -U sfloess -d learning -c \\"
echo "    \"SELECT chunk_type, COUNT(*) as count "
echo "     FROM code_analysis.chunks "
echo "     GROUP BY chunk_type "
echo "     ORDER BY count DESC;\""
echo ""

echo "Check embeddings generated:"
echo "  psql -h laptop-01 -U sfloess -d learning -c \\"
echo "    \"SELECT COUNT(*) as total, "
echo "           COUNT(embedding) as with_embedding, "
echo "           (COUNT(embedding)::float / COUNT(*)::float * 100)::int as percent "
echo "     FROM code_analysis.chunks;\""
echo ""

echo "Semantic search example (find similar code):"
echo "  psql -h laptop-01 -U sfloess -d learning -c \\"
echo "    \"SELECT name, repository, chunk_type, "
echo "           SUBSTRING(code, 1, 100) as code_preview "
echo "     FROM code_analysis.chunks "
echo "     WHERE embedding IS NOT NULL "
echo "     ORDER BY embedding <=> (SELECT embedding FROM code_analysis.chunks LIMIT 1) "
echo "     LIMIT 10;\""
echo ""
