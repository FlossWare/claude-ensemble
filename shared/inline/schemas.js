// INLINE Schemas
// Copy these schemas directly into your workflow
// Reference: ../schemas.js

// ============================================================================
// ISSUE SCHEMAS
// ============================================================================

const ISSUE_SCHEMA = {
  type: 'object',
  properties: {
    severity: { type: 'string', enum: ['critical', 'major', 'minor'] },
    category: { type: 'string' },
    description: { type: 'string' },
    file: { type: 'string' },
    line_hint: { type: 'string' },
    confidence: { type: 'number', minimum: 0, maximum: 100 }
  },
  required: ['severity', 'category', 'description', 'file', 'confidence']
}

const FINDING_SCHEMA = {
  type: 'object',
  properties: {
    issues: {
      type: 'array',
      items: ISSUE_SCHEMA
    }
  }
}

// ============================================================================
// REVIEW SCHEMAS
// ============================================================================

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    is_real_issue: { type: 'boolean' },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
    reasoning: { type: 'string' },
    severity_assessment: { type: 'string', enum: ['critical', 'major', 'minor', 'false_positive'] },
    recommended_action: { type: 'string' }
  },
  required: ['is_real_issue', 'confidence', 'reasoning', 'severity_assessment']
}

const COMMIT_REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    commit_hash: { type: 'string' },
    issues: {
      type: 'array',
      items: ISSUE_SCHEMA
    }
  }
}

// ============================================================================
// ARBITER SCHEMAS
// ============================================================================

const ARBITER_SCHEMA = {
  type: 'object',
  properties: {
    final_decision: { type: 'string', enum: ['real_issue', 'false_positive', 'needs_human', 'approved', 'rejected'] },
    consensus_score: { type: 'number', minimum: 0, maximum: 100 },
    accepted_model: { type: 'string' },
    accepted_reasoning: { type: 'string' },
    rejected_models: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          model: { type: 'string' },
          rejection_reason: { type: 'string' }
        },
        required: ['model', 'rejection_reason']
      }
    },
    create_issue: { type: 'boolean' },
    issue_priority: { type: 'string', enum: ['P0', 'P1', 'P2', 'P3', 'P4'] }
  },
  required: ['final_decision', 'consensus_score', 'accepted_model', 'accepted_reasoning', 'rejected_models']
}

// ============================================================================
// FIX SCHEMAS
// ============================================================================

const FIX_SCHEMA = {
  type: 'object',
  properties: {
    approach: { type: 'string' },
    code_changes: { type: 'string' },
    files_modified: { type: 'array', items: { type: 'string' } },
    rationale: { type: 'string' },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
    risks: { type: 'array', items: { type: 'string' } },
    test_plan: { type: 'string' }
  },
  required: ['approach', 'code_changes', 'rationale', 'confidence']
}

// ============================================================================
// PR SCHEMAS
// ============================================================================

const PR_REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    overall_quality: { type: 'number', minimum: 0, maximum: 100 },
    approval_recommendation: { type: 'string', enum: ['approve', 'request_changes', 'comment'] },
    issues_found: { type: 'array', items: ISSUE_SCHEMA },
    strengths: { type: 'array', items: { type: 'string' } },
    improvements_needed: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'number', minimum: 0, maximum: 100 }
  },
  required: ['overall_quality', 'approval_recommendation', 'issues_found', 'confidence']
}

// ============================================================================
// QUALITY SCHEMAS
// ============================================================================

const QUALITY_SCORE_SCHEMA = {
  type: 'object',
  properties: {
    score: { type: 'number', minimum: 0, maximum: 100 },
    critical_count: { type: 'number' },
    major_count: { type: 'number' },
    minor_count: { type: 'number' },
    meets_threshold: { type: 'boolean' }
  },
  required: ['score', 'critical_count', 'major_count', 'minor_count']
}

// ============================================================================
// PLATFORM SCHEMAS
// ============================================================================

const PLATFORM_SCHEMA = {
  type: 'object',
  properties: {
    platform: { type: 'string', enum: ['github', 'gitlab', 'bitbucket', 'unknown'] },
    cli: { type: 'string', enum: ['gh', 'glab', 'bb', 'none'] },
    remote_url: { type: 'string' },
    repo_owner: { type: 'string' },
    repo_name: { type: 'string' }
  },
  required: ['platform']
}

// ============================================================================
// GIT SCHEMAS
// ============================================================================

const COMMIT_HISTORY_SCHEMA = {
  type: 'object',
  properties: {
    commits: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          hash: { type: 'string' },
          author: { type: 'string' },
          date: { type: 'string' },
          message: { type: 'string' }
        }
      }
    },
    total_commits: { type: 'number' }
  },
  required: ['commits', 'total_commits']
}

const DIFF_SCHEMA = {
  type: 'object',
  properties: {
    files_changed: { type: 'array', items: { type: 'string' } },
    diff: { type: 'string' },
    commit_hash: { type: 'string' }
  }
}

const FILE_LIST_SCHEMA = {
  type: 'object',
  properties: {
    files: { type: 'array', items: { type: 'string' } }
  }
}

// ============================================================================
// ISSUE LIST SCHEMAS
// ============================================================================

const ISSUE_LIST_SCHEMA = {
  type: 'object',
  properties: {
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          number: { type: 'number' },
          title: { type: 'string' },
          body: { type: 'string' },
          labels: { type: 'array' },
          createdAt: { type: 'string' },
          closedAt: { type: 'string' }
        }
      }
    }
  }
}

const ISSUE_CREATE_SCHEMA = {
  type: 'object',
  properties: {
    issue_url: { type: 'string' },
    issue_number: { type: 'number' }
  }
}

// ============================================================================
// USAGE
// ============================================================================

/*

// Use in agent calls:

// Finding issues
const result = await agent('Find bugs', {
  schema: FINDING_SCHEMA
})

// Reviewing commits
const review = await agent('Review commit', {
  schema: COMMIT_REVIEW_SCHEMA
})

// Arbiter decision
const decision = await agent('Pick best fix', {
  schema: ARBITER_SCHEMA
})

// Proposing fixes
const fix = await agent('Propose fix', {
  schema: FIX_SCHEMA
})

// PR review
const prReview = await agent('Review PR', {
  schema: PR_REVIEW_SCHEMA
})

// Platform detection
const platform = await agent('Detect platform', {
  schema: PLATFORM_SCHEMA
})

// Git operations
const history = await agent('Get commits', {
  schema: COMMIT_HISTORY_SCHEMA
})

const diff = await agent('Get diff', {
  schema: DIFF_SCHEMA
})

// Issue operations
const issues = await agent('List issues', {
  schema: ISSUE_LIST_SCHEMA
})

const created = await agent('Create issue', {
  schema: ISSUE_CREATE_SCHEMA
})

*/
