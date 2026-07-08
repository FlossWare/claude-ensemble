/**
 * Multi-AI Consensus Review: Today's Features
 *
 * Reviews all code/features implemented today:
 * 1. Model filtering & Red Hat compliance
 * 2. Model usage tracking
 * 3. Dry-run mode
 * 4. API key management (in-progress)
 *
 * Uses 6 diverse models for independent review, then arbiter synthesis.
 */

const meta = {
  name: 'review-todays-work',
  description: 'Multi-AI consensus review of model filtering, tracking, dry-run, and API key management',
  phases: [
    { title: 'Gather Files', detail: 'Read all files to review' },
    { title: 'Parallel Review', detail: '6 workers review independently' },
    { title: 'Synthesis', detail: 'Arbiter synthesizes findings' },
  ],
};

export default async function({ phase, log, agent, parallel }) {

  // Files to review
  const FILES_TO_REVIEW = [
    // Model filtering
    'shared/anthropic-models.cjs',
    'shared/task-model-rules.cjs',
    'skills/misc/get-next-arbiter.js',
    // Tracking
    'shared/model-usage-tracker.cjs',
    'tools/view-model-usage.cjs',
    // Dry-run
    'shared/model-preview.cjs',
    'tools/dry-run-model-selection.cjs',
  ];

  // Review scope
  const REVIEW_SCOPE = `
Review dimensions:
1. SECURITY: API key handling, SQL injection, secret exposure, Red Hat compliance enforcement
2. CODE QUALITY: Error handling, edge cases, type safety, performance
3. CORRECTNESS: Red Hat filtering logic, Anthropic detection, dry-run accuracy
4. API DESIGN: Function signatures, return values, error propagation
5. DOCUMENTATION: Completeness, accuracy, examples
6. INTEGRATION: Works with existing workflows, database schema

CRITICAL: Red Hat compliance filtering MUST be 100% reliable - no loopholes!

Grade each dimension: A/B/C/D/F
Identify: Security issues, bugs, edge cases, improvements
`;

  // ===================================================================
  // PHASE 1: Gather files
  // ===================================================================
  phase('Gather Files');

  log('Reading files for review...');

  const fileContents = {};
  for (const file of FILES_TO_REVIEW) {
    try {
      const content = await read(`/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/${file}`);
      fileContents[file] = content;
      log(`✓ Read ${file} (${content.split('\n').length} lines)`);
    } catch (error) {
      log(`✗ Could not read ${file}: ${error.message}`);
    }
  }

  const reviewPackage = {
    scope: REVIEW_SCOPE,
    files: fileContents,
    context: {
      purpose: 'Red Hat work requires Anthropic-only models (compliance)',
      total_files: Object.keys(fileContents).length,
      total_lines: Object.values(fileContents).reduce((sum, content) => sum + content.split('\n').length, 0),
    },
  };

  log(`Prepared review package: ${reviewPackage.context.total_files} files, ${reviewPackage.context.total_lines} lines`);

  // ===================================================================
  // PHASE 2: Parallel independent reviews (6 workers)
  // ===================================================================
  phase('Parallel Review');

  log('Launching 6 independent reviewers...');

  const reviewPrompt = (perspective) => `
You are a ${perspective} reviewer.

Review the following code files for a Red Hat-compliant model filtering system:

${REVIEW_SCOPE}

FILES:
${Object.entries(reviewPackage.files).map(([name, content]) =>
  `\n=== ${name} ===\n${content}\n`
).join('\n')}

CONTEXT:
${JSON.stringify(reviewPackage.context, null, 2)}

Your review should:
1. Focus on your expertise (${perspective})
2. Grade each dimension (A/B/C/D/F)
3. List CRITICAL issues first, then improvements
4. Be specific with line numbers/functions
5. Consider Red Hat compliance as CRITICAL

Return JSON:
{
  "reviewer": "${perspective}",
  "overall_grade": "A/B/C/D/F",
  "dimensions": {
    "security": {"grade": "A/B/C/D/F", "notes": "..."},
    "code_quality": {"grade": "A/B/C/D/F", "notes": "..."},
    "correctness": {"grade": "A/B/C/D/F", "notes": "..."},
    "api_design": {"grade": "A/B/C/D/F", "notes": "..."},
    "documentation": {"grade": "A/B/C/D/F", "notes": "..."},
    "integration": {"grade": "A/B/C/D/F", "notes": "..."}
  },
  "critical_issues": [
    {"severity": "critical/high/medium/low", "file": "...", "line": N, "issue": "...", "fix": "..."}
  ],
  "improvements": [
    {"priority": "high/medium/low", "suggestion": "..."}
  ]
}
`;

  const REVIEW_SCHEMA = {
    type: 'object',
    required: ['reviewer', 'overall_grade', 'dimensions', 'critical_issues', 'improvements'],
    properties: {
      reviewer: { type: 'string' },
      overall_grade: { type: 'string', enum: ['A', 'B', 'C', 'D', 'F'] },
      dimensions: {
        type: 'object',
        required: ['security', 'code_quality', 'correctness', 'api_design', 'documentation', 'integration'],
        properties: {
          security: {
            type: 'object',
            required: ['grade', 'notes'],
            properties: {
              grade: { type: 'string', enum: ['A', 'B', 'C', 'D', 'F'] },
              notes: { type: 'string' }
            }
          },
          code_quality: {
            type: 'object',
            required: ['grade', 'notes'],
            properties: {
              grade: { type: 'string', enum: ['A', 'B', 'C', 'D', 'F'] },
              notes: { type: 'string' }
            }
          },
          correctness: {
            type: 'object',
            required: ['grade', 'notes'],
            properties: {
              grade: { type: 'string', enum: ['A', 'B', 'C', 'D', 'F'] },
              notes: { type: 'string' }
            }
          },
          api_design: {
            type: 'object',
            required: ['grade', 'notes'],
            properties: {
              grade: { type: 'string', enum: ['A', 'B', 'C', 'D', 'F'] },
              notes: { type: 'string' }
            }
          },
          documentation: {
            type: 'object',
            required: ['grade', 'notes'],
            properties: {
              grade: { type: 'string', enum: ['A', 'B', 'C', 'D', 'F'] },
              notes: { type: 'string' }
            }
          },
          integration: {
            type: 'object',
            required: ['grade', 'notes'],
            properties: {
              grade: { type: 'string', enum: ['A', 'B', 'C', 'D', 'F'] },
              notes: { type: 'string' }
            }
          }
        }
      },
      critical_issues: {
        type: 'array',
        items: {
          type: 'object',
          required: ['severity', 'issue'],
          properties: {
            severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
            file: { type: 'string' },
            line: { type: 'number' },
            issue: { type: 'string' },
            fix: { type: 'string' }
          }
        }
      },
      improvements: {
        type: 'array',
        items: {
          type: 'object',
          required: ['priority', 'suggestion'],
          properties: {
            priority: { type: 'string', enum: ['high', 'medium', 'low'] },
            suggestion: { type: 'string' }
          }
        }
      }
    }
  };

  const reviews = await parallel([
    () => agent(reviewPrompt('Security Expert (focus: vulnerabilities, encryption, SQL injection)'), {
      label: 'Security Expert',
      phase: 'Parallel Review',
      schema: REVIEW_SCHEMA,
    }),
    () => agent(reviewPrompt('Code Quality Specialist (focus: error handling, edge cases, performance)'), {
      label: 'Code Quality',
      phase: 'Parallel Review',
      schema: REVIEW_SCHEMA,
    }),
    () => agent(reviewPrompt('Correctness Auditor (focus: logic bugs, Red Hat compliance, filtering accuracy)'), {
      label: 'Correctness',
      phase: 'Parallel Review',
      schema: REVIEW_SCHEMA,
    }),
    () => agent(reviewPrompt('API Design Architect (focus: interfaces, contracts, backward compatibility)'), {
      label: 'API Design',
      phase: 'Parallel Review',
      schema: REVIEW_SCHEMA,
    }),
    () => agent(reviewPrompt('Integration Tester (focus: workflow compatibility, database, fallbacks)'), {
      label: 'Integration',
      phase: 'Parallel Review',
      schema: REVIEW_SCHEMA,
    }),
    () => agent(reviewPrompt('Documentation Reviewer (focus: completeness, accuracy, examples)'), {
      label: 'Documentation',
      phase: 'Parallel Review',
      schema: REVIEW_SCHEMA,
    }),
  ]);

  log(`Collected ${reviews.filter(Boolean).length} reviews`);

  // ===================================================================
  // PHASE 3: Arbiter synthesis
  // ===================================================================
  phase('Synthesis');

  log('Synthesizing findings from all reviewers...');

  const synthesisPrompt = `
You are the final arbiter synthesizing ${reviews.filter(Boolean).length} independent code reviews.

REVIEWS:
${JSON.stringify(reviews.filter(Boolean), null, 2)}

Your job:
1. Aggregate all critical issues (deduplicate similar findings)
2. Prioritize fixes by severity and consensus
3. Calculate overall grade (average of reviewer grades)
4. Identify false positives (issues mentioned by 1 reviewer but refuted by others)
5. Highlight consensus strengths
6. Create actionable fix list

Return JSON:
{
  "overall_grade": "A/B/C/D/F",
  "consensus_dimensions": {
    "security": {"avg_grade": "A/B/C/D/F", "range": "A-B", "consensus": "Strong/Weak"},
    "code_quality": {...},
    "correctness": {...},
    "api_design": {...},
    "documentation": {...},
    "integration": {...}
  },
  "critical_issues_consensus": [
    {
      "severity": "critical/high/medium/low",
      "file": "...",
      "issue": "...",
      "fix": "...",
      "mentioned_by": ["Security Expert", "Correctness Auditor"],
      "consensus_strength": "unanimous/majority/minority"
    }
  ],
  "strengths": ["...", "..."],
  "recommended_fixes": [
    {"priority": 1, "action": "...", "rationale": "..."}
  ],
  "ship_recommendation": "SHIP / FIX_THEN_SHIP / DO_NOT_SHIP",
  "ship_rationale": "..."
}
`;

  const SYNTHESIS_SCHEMA = {
    type: 'object',
    required: ['overall_grade', 'consensus_dimensions', 'critical_issues_consensus', 'strengths', 'recommended_fixes', 'ship_recommendation', 'ship_rationale'],
    properties: {
      overall_grade: { type: 'string', enum: ['A', 'B', 'C', 'D', 'F'] },
      consensus_dimensions: { type: 'object' },
      critical_issues_consensus: { type: 'array' },
      strengths: { type: 'array', items: { type: 'string' } },
      recommended_fixes: { type: 'array' },
      ship_recommendation: { type: 'string', enum: ['SHIP', 'FIX_THEN_SHIP', 'DO_NOT_SHIP'] },
      ship_rationale: { type: 'string' }
    }
  };

  const synthesis = await agent(synthesisPrompt, {
    label: 'Final Arbiter',
    phase: 'Synthesis',
    schema: SYNTHESIS_SCHEMA,
  });

  log(`Synthesis complete: ${synthesis.overall_grade} (${synthesis.ship_recommendation})`);

  // ===================================================================
  // RETURN RESULTS
  // ===================================================================

  return {
    summary: {
      files_reviewed: Object.keys(fileContents).length,
      total_lines: reviewPackage.context.total_lines,
      reviewers: reviews.filter(Boolean).length,
      overall_grade: synthesis.overall_grade,
      ship_recommendation: synthesis.ship_recommendation,
    },
    individual_reviews: reviews.filter(Boolean),
    synthesis: synthesis,
    timestamp: new Date().toISOString(),
  };
}
