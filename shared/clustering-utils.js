// Clustering Utilities
// AI-powered clustering for pattern recognition and insights
// Used by learning system, code-review, and analytics

/**
 * Clusters rejection reasons to identify common patterns
 *
 * @param {Function} agent - The agent function
 * @param {Array<Object>} rejections - Array of {model, reason, count}
 * @returns {Promise<Object>} Clustered rejection patterns
 */
export async function clusterRejectionReasons(agent, rejections) {
  if (!rejections || rejections.length === 0) {
    return { clusters: [], total: 0 }
  }

  const reasonList = rejections.map(r =>
    `- "${r.reason}" (${r.model}, ${r.count} times)`
  ).join('\n')

  const result = await agent(`Cluster these rejection reasons into semantic groups.

Rejection reasons:
${reasonList}

Group similar reasons together and identify common themes.
Examples of similar reasons:
- "Missing UI validation" and "No UI tests" → cluster: "UI_TESTING_MISSING"
- "Low confidence" and "Uncertain results" → cluster: "CONFIDENCE_ISSUES"

Return:
- clusters: array of {name, theme, reasons[], total_count}
- insights: key patterns discovered`, {
    label: 'Cluster Rejections',
    schema: {
      type: 'object',
      properties: {
        clusters: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              theme: { type: 'string' },
              reasons: { type: 'array', items: { type: 'string' } },
              total_count: { type: 'number' },
              affected_models: { type: 'array', items: { type: 'string' } }
            }
          }
        },
        insights: { type: 'array', items: { type: 'string' } }
      }
    }
  })

  return result
}

/**
 * Clusters proposal approaches to identify strategy patterns
 *
 * @param {Function} agent - The agent function
 * @param {Array<Object>} proposals - Array of {approach, model, selected, confidence}
 * @returns {Promise<Object>} Clustered approach patterns
 */
export async function clusterProposalApproaches(agent, proposals) {
  if (!proposals || proposals.length === 0) {
    return { clusters: [], total: 0 }
  }

  const approachList = proposals.map((p, idx) =>
    `${idx + 1}. "${p.approach}" (${p.model}, confidence: ${p.confidence}%, ${p.selected ? 'SELECTED' : 'rejected'})`
  ).join('\n')

  const result = await agent(`Cluster these proposal approaches into strategy groups.

Proposals:
${approachList}

Group similar strategies and identify which clusters have highest selection rates.

Return:
- clusters: array of {strategy_name, approaches[], selection_rate, avg_confidence}
- recommendations: which strategy clusters work best`, {
    label: 'Cluster Approaches',
    schema: {
      type: 'object',
      properties: {
        clusters: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              strategy_name: { type: 'string' },
              description: { type: 'string' },
              approaches: { type: 'array', items: { type: 'string' } },
              selection_count: { type: 'number' },
              total_count: { type: 'number' },
              selection_rate: { type: 'number' },
              avg_confidence: { type: 'number' }
            }
          }
        },
        recommendations: { type: 'array', items: { type: 'string' } }
      }
    }
  })

  return result
}

/**
 * Clusters user feedback to identify common themes
 *
 * @param {Function} agent - The agent function
 * @param {Array<string>} feedbackItems - Array of user feedback strings
 * @returns {Promise<Object>} Clustered feedback themes
 */
export async function clusterUserFeedback(agent, feedbackItems) {
  if (!feedbackItems || feedbackItems.length === 0) {
    return { clusters: [], total: 0 }
  }

  const feedbackList = feedbackItems.map((f, idx) =>
    `${idx + 1}. ${f}`
  ).join('\n')

  const result = await agent(`Cluster user feedback into thematic groups.

Feedback:
${feedbackList}

Group by theme (e.g., "testing preferences", "code style", "performance concerns").

Return:
- clusters: array of {theme, feedback_items[], actionable_insight}
- priority_themes: which themes appear most frequently`, {
    label: 'Cluster Feedback',
    schema: {
      type: 'object',
      properties: {
        clusters: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              theme: { type: 'string' },
              feedback_items: { type: 'array', items: { type: 'string' } },
              count: { type: 'number' },
              actionable_insight: { type: 'string' }
            }
          }
        },
        priority_themes: { type: 'array', items: { type: 'string' } }
      }
    }
  })

  return result
}

/**
 * Clusters tasks by model strengths (which models excel at which tasks)
 *
 * @param {Function} agent - The agent function
 * @param {Array<Object>} decisions - Array of decision records
 * @returns {Promise<Object>} Model strength clusters
 */
export async function clusterModelStrengths(agent, decisions) {
  if (!decisions || decisions.length === 0) {
    return { clusters: [], insights: [] }
  }

  // Organize by model
  const byModel = {}
  decisions.forEach(d => {
    if (!byModel[d.selected_model]) {
      byModel[d.selected_model] = []
    }
    byModel[d.selected_model].push(d.task_type)
  })

  const modelSummary = Object.entries(byModel).map(([model, tasks]) => {
    const taskCounts = {}
    tasks.forEach(t => {
      taskCounts[t] = (taskCounts[t] || 0) + 1
    })
    return `${model}: ${JSON.stringify(taskCounts)}`
  }).join('\n')

  const result = await agent(`Cluster tasks by model strengths.

Model task selections:
${modelSummary}

Identify which models excel at which types of tasks.

Return:
- clusters: array of {model, task_types[], selection_rate, strengths[]}
- routing_recommendations: how to route tasks to optimal models`, {
    label: 'Cluster Model Strengths',
    schema: {
      type: 'object',
      properties: {
        clusters: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              model: { type: 'string' },
              task_types: { type: 'array', items: { type: 'string' } },
              selection_count: { type: 'number' },
              strengths: { type: 'array', items: { type: 'string' } }
            }
          }
        },
        routing_recommendations: { type: 'array', items: { type: 'string' } }
      }
    }
  })

  return result
}

/**
 * Clusters similar issues to identify duplicate or related problems
 *
 * @param {Function} agent - The agent function
 * @param {Array<Object>} issues - Array of {number, title, body}
 * @returns {Promise<Object>} Issue clusters
 */
export async function clusterSimilarIssues(agent, issues) {
  if (!issues || issues.length === 0) {
    return { clusters: [], duplicates: [] }
  }

  const issueList = issues.map(i =>
    `#${i.number}: ${i.title}`
  ).join('\n')

  const result = await agent(`Cluster similar issues to identify duplicates and themes.

Issues:
${issueList}

Group similar or duplicate issues together.

Return:
- clusters: array of {theme, issue_numbers[], is_duplicate_group}
- duplicates: pairs of likely duplicate issues`, {
    label: 'Cluster Issues',
    schema: {
      type: 'object',
      properties: {
        clusters: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              theme: { type: 'string' },
              issue_numbers: { type: 'array', items: { type: 'number' } },
              is_duplicate_group: { type: 'boolean' }
            }
          }
        },
        duplicates: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              issue_a: { type: 'number' },
              issue_b: { type: 'number' },
              similarity: { type: 'number' }
            }
          }
        }
      }
    }
  })

  return result
}

/**
 * Simple text-based clustering (fallback when agent clustering not needed)
 *
 * @param {Array<string>} texts - Texts to cluster
 * @param {number} threshold - Similarity threshold (0-1)
 * @returns {Array<Array<string>>} Clusters of similar texts
 */
export function simpleTextClustering(texts, threshold = 0.7) {
  const clusters = []
  const used = new Set()

  for (let i = 0; i < texts.length; i++) {
    if (used.has(i)) continue

    const cluster = [texts[i]]
    used.add(i)

    for (let j = i + 1; j < texts.length; j++) {
      if (used.has(j)) continue

      const similarity = calculateTextSimilarity(texts[i], texts[j])
      if (similarity >= threshold) {
        cluster.push(texts[j])
        used.add(j)
      }
    }

    clusters.push(cluster)
  }

  return clusters
}

/**
 * Simple Jaccard similarity for text comparison
 */
function calculateTextSimilarity(text1, text2) {
  const words1 = new Set(text1.toLowerCase().split(/\s+/))
  const words2 = new Set(text2.toLowerCase().split(/\s+/))

  const intersection = new Set([...words1].filter(w => words2.has(w)))
  const union = new Set([...words1, ...words2])

  return intersection.size / union.size
}

// ============================================================================
// INLINE VERSION (for workflows that can't use imports)
// ============================================================================

export const INLINE_CLUSTERING = `
// Inline clustering utilities (copy into workflows)

async function clusterRejectionReasons(agent, rejections) {
  if (!rejections || rejections.length === 0) return { clusters: [], total: 0 }

  const reasonList = rejections.map(r => \`- "\${r.reason}" (\${r.model}, \${r.count} times)\`).join('\\n')

  return await agent(\`Cluster these rejection reasons:
\${reasonList}

Group similar reasons and identify themes.\`, {
    label: 'Cluster Rejections',
    schema: {
      type: 'object',
      properties: {
        clusters: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              reasons: { type: 'array' },
              total_count: { type: 'number' }
            }
          }
        }
      }
    }
  })
}
`
