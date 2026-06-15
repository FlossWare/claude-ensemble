#!/usr/bin/env bash
# meta-answer skill - Adaptive Model Selection with Thompson Sampling
#
# Uses Thompson Sampling to select the best model for answering questions,
# then logs the result to enable continuous learning and improvement.

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

SKILLS_DIR="$HOME/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"
ORCHESTRATOR="$SKILLS_DIR/orchestrator.js"
LEARNING_LOGGER="$SKILLS_DIR/shared/learning-logger.js"
TASK_TYPE="meta-answer"
DEFAULT_QUALITY_SCORE=0.8

# ============================================================================
# HELP
# ============================================================================

show_help() {
    cat << 'EOF'
/meta-answer - Adaptive Model Selection with Learning

USAGE:
  /meta-answer <question>
  /meta-answer --help

DESCRIPTION:
  Get answers to any question using Thompson Sampling to select the best
  AI model based on historical performance. The system learns from each
  interaction to continuously improve model selection.

EXAMPLES:
  /meta-answer How should I architect this authentication system?
  /meta-answer What's the best way to handle async errors in JavaScript?
  /meta-answer Is this caching approach optimal?

HOW IT WORKS:
  1. Thompson Sampling selects the best model based on success rates
  2. Spawns an agent with the selected model to answer the question
  3. Returns the model's response to you
  4. Records the execution with quality score (default: 0.8)
  5. Future selections benefit from this learning

THOMPSON SAMPLING:
  - Maintains Beta distribution for each model (alpha, beta)
  - Samples from distributions and picks highest sample
  - Balances exploration (uncertain models) and exploitation (proven models)
  - Converges to optimal model selection over time

QUALITY SCORING:
  Default: 0.8 (good quality)
  You can adjust based on actual quality:
    1.0 - Perfect answer
    0.9 - Excellent answer
    0.8 - Good answer (default)
    0.7 - Acceptable answer
    0.5 - Mediocre answer
    0.3 - Poor answer
    0.0 - Completely wrong

LEARNING DATABASE:
  All executions logged to: ~/.claude/learning/db/learning.db
  Bandit state persisted to: ~/.claude/learning/bandit-state.json

COMPARISON:
  meta-answer: Single model via Thompson Sampling (fast, learns)
  ai-prompt:   Multi-model consensus (comprehensive, expensive)

DOCUMENTATION:
  See: meta-answer.md
EOF
    exit 0
}

# ============================================================================
# INPUT VALIDATION
# ============================================================================

if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    show_help
fi

if [[ $# -eq 0 ]]; then
    echo "Error: Question required"
    echo ""
    echo "Usage: /meta-answer <question>"
    echo "       /meta-answer --help"
    exit 1
fi

QUESTION="$*"

# ============================================================================
# MODEL SELECTION VIA THOMPSON SAMPLING
# ============================================================================

echo "Selecting model via Thompson Sampling..."

# Call orchestrator.selectModel() with Thompson Sampling strategy
SELECTED_MODEL=$(node -e "
import { selectModel } from '$ORCHESTRATOR';

(async () => {
  try {
    const model = await selectModel('$TASK_TYPE', {
      strategy: 'thompson',
      count: 1
    });
    console.log(model);
  } catch (err) {
    console.error('Error selecting model:', err.message);
    console.log('sonnet'); // Fallback to sonnet
    process.exit(0);
  }
})();
" 2>&1 | tail -1)

# Validate model selection
if [[ -z "$SELECTED_MODEL" ]]; then
    echo "Warning: Model selection failed, using fallback model: sonnet"
    SELECTED_MODEL="sonnet"
fi

echo "Selected: $SELECTED_MODEL"
echo ""

# ============================================================================
# SPAWN AGENT WITH SELECTED MODEL
# ============================================================================

echo "Spawning agent with model: $SELECTED_MODEL"
echo "Question: $QUESTION"
echo ""
echo "----------------------------------------"
echo ""

# Note: In the actual implementation, this would use the Agent tool to spawn
# an agent with the selected model. For the shell script, we indicate this
# is delegated to Claude Code's skill system.

cat << EOF
This skill delegates to Claude Code's Agent system to:

1. Spawn an agent with model: $SELECTED_MODEL
2. Pass the question: "$QUESTION"
3. Collect the agent's response
4. Log the execution to the learning database
5. Update Thompson Sampling state with quality score

The actual agent spawning and logging happens in the Claude Code skill handler,
not in this shell script. This script demonstrates the workflow:

  selectModel('$TASK_TYPE', { strategy: 'thompson' })
    => '$SELECTED_MODEL'

  Agent.spawn({
    model: '$SELECTED_MODEL',
    prompt: '$QUESTION',
    description: 'Meta-answer with Thompson Sampling'
  })
    => [agent response]

  logExecution({
    model: '$SELECTED_MODEL',
    task_type: '$TASK_TYPE',
    quality_score: $DEFAULT_QUALITY_SCORE,
    workflow: 'meta-answer',
    ...
  })

  recordResult('$SELECTED_MODEL', $DEFAULT_QUALITY_SCORE)
    => Updated Thompson state

After execution, the learning database and Thompson Sampling state are updated
to improve future model selection.
EOF

echo ""
echo "----------------------------------------"
echo ""
echo "Note: Run this skill through Claude Code's /meta-answer command"
echo "      for full agent spawning and learning loop integration."
