#!/usr/bin/env node

/**
 * Workflow Template Suggester
 *
 * Analyzes task descriptions and suggests appropriate workflow templates
 * based on historical patterns from PostgreSQL workflow storage.
 *
 * Usage:
 *   const { suggestWorkflowTemplate } = require('./workflow-template-suggester.js');
 *   const template = await suggestWorkflowTemplate('Validate ML model performance');
 *
 * Features:
 *   - Loads 16 extracted workflow templates
 *   - Keyword-based pattern matching
 *   - Cost and duration predictions
 *   - Parallelism recommendations
 */

const fs = require('fs');
const path = require('path');

const TEMPLATES_PATH = path.join(process.env.HOME, '.claude/learning/workflow_templates.json');

/**
 * Load workflow templates from disk
 */
function loadTemplates() {
  if (!fs.existsSync(TEMPLATES_PATH)) {
    throw new Error(`Templates file not found: ${TEMPLATES_PATH}`);
  }

  const data = fs.readFileSync(TEMPLATES_PATH, 'utf8');
  return JSON.parse(data);
}

/**
 * Extract keywords from task description
 */
function extractKeywords(taskDescription) {
  const text = taskDescription.toLowerCase();
  return {
    isResearch: /research|investigate|analyze|study|explore/i.test(text),
    isValidation: /test|validate|verify|check|integration/i.test(text),
    isTraining: /train|ml|model|learning|optimize/i.test(text),
    isChunking: /chunk|split|process|parse|embed/i.test(text),
    isFeedback: /feedback|review|quality|evaluate/i.test(text),
    isDistributed: /fleet|distributed|parallel|multi|consensus/i.test(text),
    isSimple: /simple|quick|single|basic/i.test(text),
    needsConsensus: /consensus|vote|multi-ai|arbiter/i.test(text)
  };
}

/**
 * Score template match against task keywords
 */
function scoreTemplate(template, keywords) {
  let score = 0;

  // Research workflows
  if (keywords.isResearch && template.workflow_name === 'deep-research') {
    score += 10;
  }

  // Validation workflows
  if (keywords.isValidation && template.workflow_name.includes('test')) {
    score += 8;
  }

  // Training workflows
  if (keywords.isTraining && template.workflow_name === 'ml-systems-training') {
    score += 10;
  }

  // Chunking workflows
  if (keywords.isChunking && template.workflow_name.includes('chunking')) {
    score += 10;
  }

  // Feedback workflows
  if (keywords.isFeedback && template.workflow_name === 'feedback-test') {
    score += 8;
  }

  // Distributed workflows
  if (keywords.isDistributed && template.configuration.recommended_workers >= 3) {
    score += 5;
  }

  // Simple workflows
  if (keywords.isSimple && template.configuration.recommended_workers <= 1) {
    score += 5;
  }

  // Consensus workflows
  if (keywords.needsConsensus && template.configuration.parallel_strategy === 'high_parallelism') {
    score += 7;
  }

  return score;
}

/**
 * Suggest workflow template based on task description
 *
 * @param {string} taskDescription - Natural language task description
 * @param {object} options - Optional constraints (maxCost, maxDuration, minWorkers, maxWorkers)
 * @returns {object} Recommended template with configuration
 */
function suggestWorkflowTemplate(taskDescription, options = {}) {
  const templates = loadTemplates();
  const keywords = extractKeywords(taskDescription);

  // Score all templates
  const scored = templates.templates.map(template => {
    let score = scoreTemplate(template, keywords);

    // Apply constraint penalties
    if (options.maxCost && parseFloat(template.configuration.avg_cost_usd) > options.maxCost) {
      score -= 5;
    }

    if (options.maxDuration && template.configuration.avg_duration_ms > options.maxDuration) {
      score -= 3;
    }

    if (options.minWorkers && template.configuration.recommended_workers < options.minWorkers) {
      score -= 2;
    }

    if (options.maxWorkers && template.configuration.recommended_workers > options.maxWorkers) {
      score -= 2;
    }

    return { template, score };
  });

  // Sort by score descending
  scored.sort((a, b) => b.score - a.score);

  // Return top match
  const best = scored[0];

  return {
    recommended_template: best.template.workflow_name,
    confidence: best.score > 10 ? 'high' : (best.score > 5 ? 'medium' : 'low'),
    configuration: best.template.configuration,
    use_case: best.template.use_case,
    best_practices: best.template.best_practices,
    predicted_cost_usd: best.template.configuration.avg_cost_usd,
    predicted_duration_ms: best.template.configuration.avg_duration_ms,
    alternatives: scored.slice(1, 4).map(s => ({
      template: s.template.workflow_name,
      score: s.score
    })),
    reasoning: {
      keywords_detected: Object.entries(keywords).filter(([k, v]) => v).map(([k]) => k),
      match_score: best.score
    }
  };
}

/**
 * Generate workflow code from template
 */
function generateWorkflowCode(templateName, taskDescription, options = {}) {
  const templates = loadTemplates();
  const template = templates.templates.find(t => t.workflow_name === templateName);

  if (!template) {
    throw new Error(`Template not found: ${templateName}`);
  }

  const config = template.configuration;
  const workflowId = `wf-${Date.now()}`;

  // Generate code based on parallelism strategy
  let code = `// Auto-generated workflow from template: ${templateName}\n`;
  code += `// Task: ${taskDescription}\n\n`;
  code += `const { getWorkflowStorage } = require('${process.env.HOME}/.claude/learning/workflow-storage-adapter.js');\n\n`;
  code += `export default async function({ phase, parallel, agent, log }) {\n`;
  code += `  const db = getWorkflowStorage();\n`;
  code += `  const workflowId = '${workflowId}';\n`;
  code += `  const startTime = Date.now();\n\n`;

  // Store execution metadata
  code += `  const execId = await db.storeExecution({\n`;
  code += `    workflow_id: workflowId,\n`;
  code += `    workflow_name: '${templateName}',\n`;
  code += `    task_description: '${taskDescription.replace(/'/g, "\\'")}',\n`;
  code += `    total_workers: ${config.recommended_workers},\n`;
  code += `    total_duration_ms: 0,\n`;
  code += `    outcome: 'pending'\n`;
  code += `  });\n\n`;

  code += `  try {\n`;

  if (config.parallel_strategy === 'high_parallelism' && config.recommended_workers >= 3) {
    // High parallelism pattern
    code += `    // High parallelism pattern (${config.recommended_workers} workers)\n`;
    code += `    const workers = await parallel([\n`;
    for (let i = 0; i < config.recommended_workers; i++) {
      code += `      agent({\n`;
      code += `        model: 'auto',\n`;
      code += `        prompt: 'Worker ${i + 1}: ${taskDescription}',\n`;
      code += `        metadata: { worker_id: 'worker-${i + 1}', workflow_execution_id: execId }\n`;
      code += `      })${i < config.recommended_workers - 1 ? ',' : ''}\n`;
    }
    code += `    ]);\n\n`;

    code += `    // Store worker results\n`;
    code += `    for (let i = 0; i < workers.length; i++) {\n`;
    code += `      await db.storeWorkerResult({\n`;
    code += `        workflow_execution_id: execId,\n`;
    code += `        worker_id: \`worker-\${i + 1}\`,\n`;
    code += `        model: workers[i].model || 'auto',\n`;
    code += `        task_assigned: '${taskDescription.replace(/'/g, "\\'")}',\n`;
    code += `        result: workers[i].output,\n`;
    code += `        confidence: workers[i].confidence || 0.8,\n`;
    code += `        duration_ms: workers[i].duration || 0,\n`;
    code += `        input_tokens: workers[i].inputTokens || 0,\n`;
    code += `        output_tokens: workers[i].outputTokens || 0,\n`;
    code += `        cost_usd: workers[i].cost || 0,\n`;
    code += `        outcome: 'success'\n`;
    code += `      });\n`;
    code += `    }\n\n`;

    code += `    // Arbiter synthesis\n`;
    code += `    const arbiter = await agent({\n`;
    code += `      model: 'auto',\n`;
    code += `      prompt: 'Synthesize results from ' + workers.length + ' workers',\n`;
    code += `      context: workers.map(w => w.output)\n`;
    code += `    });\n\n`;

    code += `    await db.storeArbiterDecision({\n`;
    code += `      workflow_execution_id: execId,\n`;
    code += `      model: arbiter.model,\n`;
    code += `      synthesis: arbiter.output,\n`;
    code += `      consensus_level: 0.85,\n`;
    code += `      workers_considered: workers.length\n`;
    code += `    });\n\n`;

    code += `    log('Workflow completed with ' + workers.length + ' workers');\n`;
    code += `    return arbiter.output;\n`;
  } else {
    // Sequential pattern
    code += `    // Sequential pattern\n`;
    code += `    const result = await agent({\n`;
    code += `      model: 'auto',\n`;
    code += `      prompt: '${taskDescription.replace(/'/g, "\\'")}'\n`;
    code += `    });\n\n`;

    code += `    await db.storeWorkerResult({\n`;
    code += `      workflow_execution_id: execId,\n`;
    code += `      worker_id: 'worker-1',\n`;
    code += `      model: result.model || 'auto',\n`;
    code += `      task_assigned: '${taskDescription.replace(/'/g, "\\'")}',\n`;
    code += `      result: result.output,\n`;
    code += `      confidence: result.confidence || 0.8,\n`;
    code += `      duration_ms: result.duration || 0,\n`;
    code += `      input_tokens: result.inputTokens || 0,\n`;
    code += `      output_tokens: result.outputTokens || 0,\n`;
    code += `      cost_usd: result.cost || 0,\n`;
    code += `      outcome: 'success'\n`;
    code += `    });\n\n`;

    code += `    log('Workflow completed sequentially');\n`;
    code += `    return result.output;\n`;
  }

  code += `  } catch (error) {\n`;
  code += `    await db.pool.query(\n`;
  code += `      'UPDATE workflow.executions SET outcome = $1 WHERE id = $2',\n`;
  code += `      ['error', execId]\n`;
  code += `    );\n`;
  code += `    throw error;\n`;
  code += `  } finally {\n`;
  code += `    const totalDuration = Date.now() - startTime;\n`;
  code += `    await db.pool.query(\n`;
  code += `      'UPDATE workflow.executions SET total_duration_ms = $1, outcome = $2 WHERE id = $3',\n`;
  code += `      [totalDuration, 'success', execId]\n`;
  code += `    );\n`;
  code += `  }\n`;
  code += `}\n`;

  return code;
}

/**
 * CLI interface
 */
if (require.main === module) {
  const taskDescription = process.argv.slice(2).join(' ');

  if (!taskDescription) {
    console.log('Usage: node workflow-template-suggester.js <task description>');
    console.log('\nExample:');
    console.log('  node workflow-template-suggester.js "Validate ML model performance across 5 datasets"');
    process.exit(1);
  }

  const suggestion = suggestWorkflowTemplate(taskDescription);
  console.log(JSON.stringify(suggestion, null, 2));
}

module.exports = {
  loadTemplates,
  suggestWorkflowTemplate,
  generateWorkflowCode,
  extractKeywords,
  scoreTemplate
};
