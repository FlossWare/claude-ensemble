/**
 * Context Prompt Builder
 *
 * Formats similar past workflows into context prompts for cross-session learning.
 * Helps workers learn from past successes and avoid past failures.
 *
 * Created: 2026-07-01
 */

/**
 * Build context prompt from similar past workflows
 *
 * @param {Array} similarWorkflows - Results from findSimilarWorkflows()
 * @returns {string} Formatted context prompt
 */
function buildContextPrompt(similarWorkflows) {
  if (!similarWorkflows || similarWorkflows.length === 0) {
    return null;
  }

  const lines = [
    '## Context from Similar Past Workflows',
    '',
    'The following workflows addressed similar tasks. Learn from their outcomes:',
    ''
  ];

  similarWorkflows.forEach((wf, idx) => {
    const distance = parseFloat(wf.distance || 0);
    const similarity = ((1 - distance) * 100).toFixed(1);
    const duration = (wf.total_duration_ms / 1000).toFixed(1);

    lines.push(`### ${idx + 1}. ${wf.workflow_name} (${similarity}% similar)`);
    lines.push(`- Task: "${wf.task_description}"`);
    lines.push(`- Outcome: ${wf.outcome}`);
    lines.push(`- Duration: ${duration}s`);
    lines.push(`- Workers: ${wf.total_workers}`);

    // Parse metadata if available
    if (wf.metadata) {
      const metadata = typeof wf.metadata === 'string'
        ? JSON.parse(wf.metadata)
        : wf.metadata;

      if (metadata.quality_score) {
        lines.push(`- Quality: ${(metadata.quality_score * 100).toFixed(1)}%`);
      }

      if (metadata.models_used && metadata.models_used.length > 0) {
        lines.push(`- Models: ${metadata.models_used.join(', ')}`);
      }

      if (metadata.key_learnings) {
        lines.push(`- Key Learning: ${metadata.key_learnings}`);
      }
    }

    lines.push('');
  });

  lines.push('**Recommendation:** Consider these patterns when approaching the current task.');
  lines.push('');

  return lines.join('\n');
}

/**
 * Extract models used across similar workflows for diversity analysis
 *
 * @param {Array} similarWorkflows - Results from findSimilarWorkflows()
 * @returns {Object} Model usage statistics
 */
function analyzeModelDistribution(similarWorkflows) {
  const modelCounts = {};
  let totalWorkflows = 0;

  for (const wf of similarWorkflows) {
    if (wf.metadata) {
      const metadata = typeof wf.metadata === 'string'
        ? JSON.parse(wf.metadata)
        : wf.metadata;

      if (metadata.models_used && Array.isArray(metadata.models_used)) {
        totalWorkflows++;
        metadata.models_used.forEach(model => {
          modelCounts[model] = (modelCounts[model] || 0) + 1;
        });
      }
    }
  }

  if (totalWorkflows === 0) {
    return { distribution: {}, dominantModel: null, dominancePercent: 0 };
  }

  // Calculate percentages
  const distribution = {};
  let dominantModel = null;
  let maxCount = 0;

  for (const [model, count] of Object.entries(modelCounts)) {
    const percent = (count / totalWorkflows) * 100;
    distribution[model] = {
      count,
      percent: percent.toFixed(1)
    };

    if (count > maxCount) {
      maxCount = count;
      dominantModel = model;
    }
  }

  const dominancePercent = (maxCount / totalWorkflows) * 100;

  return {
    distribution,
    dominantModel,
    dominancePercent: dominancePercent.toFixed(1),
    totalWorkflows
  };
}

/**
 * Build diversity warning if model echo chamber detected
 *
 * @param {Object} modelStats - From analyzeModelDistribution()
 * @returns {string|null} Warning message or null
 */
function buildDiversityWarning(modelStats) {
  if (!modelStats.dominantModel || modelStats.dominancePercent < 70) {
    return null;
  }

  return `
**⚠️ Diversity Warning:**
Past workflows show ${modelStats.dominancePercent}% usage of ${modelStats.dominantModel}.
Consider using alternative models to avoid echo chamber effects.
`;
}

module.exports = {
  buildContextPrompt,
  analyzeModelDistribution,
  buildDiversityWarning
};
