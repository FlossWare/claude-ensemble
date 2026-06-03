// Shared JSON Schemas for all workflows
// Used by: auto-review-brutal, pr-review, code-solve, code-improve

export const ISSUE_SCHEMA = {
  type: 'object',
  properties: {
    severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
    category: { type: 'string' },
    description: { type: 'string' },
    file_path: { type: 'string' },
    line_number: { type: 'number' },
    evidence: { type: 'string' },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
  },
  required: ['severity', 'category', 'description', 'file_path', 'confidence'],
}

export const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    is_real_issue: { type: 'boolean' },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
    reasoning: { type: 'string' },
    severity_assessment: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'false_positive'] },
    recommended_action: { type: 'string' },
  },
  required: ['is_real_issue', 'confidence', 'reasoning', 'severity_assessment'],
}

export const ARBITER_SCHEMA = {
  type: 'object',
  properties: {
    final_decision: { type: 'string', enum: ['real_issue', 'false_positive', 'needs_human', 'approved', 'rejected'] },
    consensus_score: { type: 'number', minimum: 0, maximum: 100, description: 'Agreement percentage' },
    accepted_model: { type: 'string', description: 'Which AI model had the best analysis' },
    accepted_reasoning: { type: 'string', description: 'WHY this model was chosen' },
    rejected_models: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          model: { type: 'string' },
          rejection_reason: { type: 'string' },
        },
        required: ['model', 'rejection_reason'],
      },
    },
    create_issue: { type: 'boolean' },
    issue_priority: { type: 'string', enum: ['P0', 'P1', 'P2', 'P3', 'P4'] },
  },
  required: ['final_decision', 'consensus_score', 'accepted_model', 'accepted_reasoning', 'rejected_models'],
}

export const FIX_SCHEMA = {
  type: 'object',
  properties: {
    approach: { type: 'string' },
    code_changes: { type: 'string' },
    files_modified: { type: 'array', items: { type: 'string' } },
    rationale: { type: 'string' },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
    risks: { type: 'array', items: { type: 'string' } },
    test_plan: { type: 'string' },
  },
  required: ['approach', 'code_changes', 'rationale', 'confidence'],
}

export const PR_REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    overall_quality: { type: 'number', minimum: 0, maximum: 100 },
    approval_recommendation: { type: 'string', enum: ['approve', 'request_changes', 'comment'] },
    issues_found: { type: 'array', items: ISSUE_SCHEMA },
    strengths: { type: 'array', items: { type: 'string' } },
    improvements_needed: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
  },
  required: ['overall_quality', 'approval_recommendation', 'issues_found', 'confidence'],
}

export const QUALITY_SCORE_SCHEMA = {
  type: 'object',
  properties: {
    score: { type: 'number', minimum: 0, maximum: 100 },
    critical_count: { type: 'number' },
    high_count: { type: 'number' },
    medium_count: { type: 'number' },
    low_count: { type: 'number' },
    meets_threshold: { type: 'boolean' },
  },
  required: ['score', 'critical_count', 'high_count', 'medium_count', 'low_count'],
}
