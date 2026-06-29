#!/usr/bin/env bash
# Sync knowledge between Claude Code workflows and Universal AI

set -euo pipefail

UNIVERSAL_AI_DIR="${HOME}/Development/redhat/scm/gitlab/cee/sfloess/universal-ai"
CLAUDE_KNOWLEDGE_DIR="${HOME}/.claude/knowledge"
UNIVERSAL_AI_KNOWLEDGE_DIR="${HOME}/.universal-ai/expert-knowledge"
UNIVERSAL_AI_KBASE_DIR="${HOME}/.universal-ai/kbases"

show_help() {
    cat << 'EOF'
sync-universal-ai - Sync knowledge between Claude Code and Universal AI

USAGE:
    sync-universal-ai <command> [options]

COMMANDS:
    import              Import Universal AI expert knowledge to Claude
    export              Export Claude workflow learnings to Universal AI
    bidirectional       Two-way sync (import + export)
    generate-skills     Generate Claude workflows from Universal AI experts
    status              Show sync status

OPTIONS:
    --dry-run          Show what would be synced without doing it
    --expert <name>    Sync specific expert only

EXAMPLES:
    # Import all Universal AI knowledge
    sync-universal-ai import

    # Export Claude learnings to Universal AI
    sync-universal-ai export

    # Two-way sync
    sync-universal-ai bidirectional

    # Generate Claude workflows from experts
    sync-universal-ai generate-skills

    # Dry run
    sync-universal-ai import --dry-run
EOF
}

# Import Universal AI knowledge to Claude
import_knowledge() {
    local dry_run="${1:-false}"
    local expert_filter="${2:-}"

    echo "📥 Importing Universal AI knowledge to Claude Code..."
    echo ""

    if [ ! -d "$UNIVERSAL_AI_KNOWLEDGE_DIR" ]; then
        echo "⚠️  Universal AI knowledge directory not found: $UNIVERSAL_AI_KNOWLEDGE_DIR"
        echo "   Run 'expert learn' in Universal AI first"
        return 1
    fi

    mkdir -p "$CLAUDE_KNOWLEDGE_DIR/universal-ai"

    local count=0
    for knowledge_file in "$UNIVERSAL_AI_KNOWLEDGE_DIR"/*.learned; do
        [ -e "$knowledge_file" ] || continue

        local expert_name=$(basename "$knowledge_file" .learned)

        # Filter if specified
        if [ -n "$expert_filter" ] && [ "$expert_name" != "$expert_filter" ]; then
            continue
        fi

        echo "  Importing: $expert_name"

        if [ "$dry_run" = "false" ]; then
            cp "$knowledge_file" "$CLAUDE_KNOWLEDGE_DIR/universal-ai/${expert_name}.md"
        fi

        count=$((count + 1))
    done

    echo ""
    echo "✅ Imported $count expert knowledge files"

    if [ "$dry_run" = "false" ]; then
        echo "   Location: $CLAUDE_KNOWLEDGE_DIR/universal-ai/"
        echo ""
        echo "Use in workflows:"
        echo "  const knowledge = Read('~/.claude/knowledge/universal-ai/python-expert.md')"
    fi
}

# Export Claude learnings to Universal AI
export_knowledge() {
    local dry_run="${1:-false}"

    echo "📤 Exporting Claude Code learnings to Universal AI..."
    echo ""

    if [ ! -d "$CLAUDE_KNOWLEDGE_DIR" ]; then
        echo "⚠️  No Claude knowledge directory found: $CLAUDE_KNOWLEDGE_DIR"
        echo "   Run web-learn workflows first"
        return 1
    fi

    mkdir -p "$UNIVERSAL_AI_KBASE_DIR/claude-code/knowledge"

    local count=0
    for knowledge_file in "$CLAUDE_KNOWLEDGE_DIR"/*.json; do
        [ -e "$knowledge_file" ] || continue

        local name=$(basename "$knowledge_file" .json)
        echo "  Exporting: $name"

        if [ "$dry_run" = "false" ]; then
            cp "$knowledge_file" "$UNIVERSAL_AI_KBASE_DIR/claude-code/knowledge/"
        fi

        count=$((count + 1))
    done

    echo ""
    echo "✅ Exported $count knowledge files"

    if [ "$dry_run" = "false" ]; then
        echo "   Location: $UNIVERSAL_AI_KBASE_DIR/claude-code/knowledge/"
        echo ""
        echo "Use in Universal AI:"
        echo "  python-expert ask 'question' --use-rag"
    fi
}

# Generate Claude workflows from Universal AI experts
generate_skills() {
    echo "🤖 Generating Claude Code workflows from Universal AI experts..."
    echo ""

    if [ ! -d "$UNIVERSAL_AI_DIR" ]; then
        echo "⚠️  Universal AI directory not found: $UNIVERSAL_AI_DIR"
        return 1
    fi

    local experts_dir="$UNIVERSAL_AI_DIR"
    local output_dir="${HOME}/.claude/repos/claude-global-skills"

    mkdir -p "$output_dir"

    # Find all *-expert.sh files
    local count=0
    for expert_script in "$experts_dir"/*-expert.sh; do
        [ -e "$expert_script" ] || continue

        local expert_name=$(basename "$expert_script" .sh)
        echo "  Generating workflow for: $expert_name"

        # Extract system prompt from expert script
        local system_prompt=$(grep -A 50 'SYSTEM_PROMPT=' "$expert_script" | sed '/^$/q' | head -20 || echo "")

        if [ -n "$system_prompt" ]; then
            # Generate workflow
            cat > "$output_dir/${expert_name}.js" << EOF
export const meta = {
  name: '${expert_name}',
  description: 'Domain expert: ${expert_name//-/ }',
  whenToUse: 'When working with ${expert_name//-/ } domain',
  phases: [
    { title: 'Analyze', detail: 'Apply domain expertise' },
    { title: 'Review', detail: 'Check against best practices' }
  ]
}

// Load expert knowledge if available
const knowledgeFile = '~/.claude/knowledge/universal-ai/${expert_name}.md'
let expertKnowledge = ''

try {
  expertKnowledge = Read(knowledgeFile)
} catch {
  // No learned knowledge yet
}

// Get user request
const request = args?.request || 'Provide domain expertise'

phase('Analyze')
log('Applying ${expert_name//-/ } domain expertise...')

const analysis = await agent(
  \`You are a ${expert_name//-/ } domain expert.

\${expertKnowledge ? 'Learned Knowledge:\\n' + expertKnowledge + '\\n\\n' : ''}

User Request: \${request}

Provide expert analysis and recommendations.\`,
  {
    phase: 'Analyze',
    label: '${expert_name}-analysis'
  }
)

phase('Review')
log('Cross-checking with domain best practices...')

const review = await agent(
  \`Review this analysis for ${expert_name//-/ } best practices:

Analysis: \${analysis}

Verify:
1. Follows domain conventions
2. No anti-patterns
3. Considers edge cases
4. Security/performance implications\`,
  {
    phase: 'Review',
    label: 'best-practices-check'
  }
)

return {
  expert: '${expert_name}',
  analysis,
  review,
  has_learned_knowledge: !!expertKnowledge
}
EOF

            count=$((count + 1))
        fi
    done

    echo ""
    echo "✅ Generated $count workflow files"
    echo "   Location: $output_dir/"
    echo ""
    echo "Test with:"
    echo "  /web-learn-mcp"
}

# Show sync status
show_status() {
    echo "📊 Sync Status: Claude Code ↔ Universal AI"
    echo ""

    # Universal AI → Claude
    echo "Universal AI → Claude:"
    if [ -d "$UNIVERSAL_AI_KNOWLEDGE_DIR" ]; then
        local ua_count=$(find "$UNIVERSAL_AI_KNOWLEDGE_DIR" -name "*.learned" | wc -l)
        echo "  Universal AI experts: $ua_count"
    else
        echo "  Universal AI: Not found"
    fi

    if [ -d "$CLAUDE_KNOWLEDGE_DIR/universal-ai" ]; then
        local c_count=$(find "$CLAUDE_KNOWLEDGE_DIR/universal-ai" -name "*.md" | wc -l)
        echo "  Imported to Claude: $c_count"
    else
        echo "  Imported to Claude: 0"
    fi

    echo ""

    # Claude → Universal AI
    echo "Claude → Universal AI:"
    if [ -d "$CLAUDE_KNOWLEDGE_DIR" ]; then
        local ck_count=$(find "$CLAUDE_KNOWLEDGE_DIR" -name "*.json" | wc -l)
        echo "  Claude knowledge files: $ck_count"
    else
        echo "  Claude knowledge: 0"
    fi

    if [ -d "$UNIVERSAL_AI_KBASE_DIR/claude-code" ]; then
        local uak_count=$(find "$UNIVERSAL_AI_KBASE_DIR/claude-code" -type f | wc -l)
        echo "  Exported to Universal AI: $uak_count"
    else
        echo "  Exported to Universal AI: 0"
    fi

    echo ""

    # Generated skills
    echo "Generated Skills:"
    if [ -d "${HOME}/.claude/repos/claude-global-skills" ]; then
        local skill_count=$(find "${HOME}/.claude/repos/claude-global-skills" -name "*-expert.js" | wc -l)
        echo "  Claude workflows from experts: $skill_count"
    else
        echo "  Claude workflows: 0"
    fi
}

# Main
main() {
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi

    local command="$1"
    shift

    local dry_run="false"
    local expert_filter=""

    # Parse options
    while [ $# -gt 0 ]; do
        case "$1" in
            --dry-run)
                dry_run="true"
                shift
                ;;
            --expert)
                expert_filter="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                shift
                ;;
        esac
    done

    case "$command" in
        import)
            import_knowledge "$dry_run" "$expert_filter"
            ;;
        export)
            export_knowledge "$dry_run"
            ;;
        bidirectional)
            import_knowledge "$dry_run" "$expert_filter"
            echo ""
            export_knowledge "$dry_run"
            ;;
        generate-skills)
            generate_skills
            ;;
        status)
            show_status
            ;;
        *)
            echo "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
