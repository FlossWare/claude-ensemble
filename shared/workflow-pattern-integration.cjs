#!/usr/bin/env node

/**
 * Workflow Pattern Integration
 *
 * Integration layer that connects workflow pattern mining to the
 * orchestration framework. Provides runtime template suggestion
 * and auto-generation capabilities.
 *
 * Location: claude-global-skills/shared/
 * Purpose: Production integration for pattern-based workflow generation
 */

const path = require('path');
const fs = require('fs');

// Load components
const templateSuggesterPath = path.join(process.env.HOME, '.claude/learning/workflow-template-suggester.js');
const autoGeneratorPath = path.join(process.env.HOME, '.claude/learning/auto-workflow-generator.js');
const workflowStoragePath = path.join(process.env.HOME, '.claude/learning/workflow-storage-adapter.js');

const { suggestWorkflowTemplate, generateWorkflowCode } = require(templateSuggesterPath);
const { generateWorkflow, generateBatch } = require(autoGeneratorPath);
const { getWorkflowStorage } = require(workflowStoragePath);

/**
 * Suggest optimal workflow structure for a task
 *
 * @param {string} taskDescription - Natural language task
 * @param {object} constraints - Optional constraints (maxCost, maxDuration, etc.)
 * @returns {object} Template suggestion with confidence score
 */
function suggestWorkflow(taskDescription, constraints = {}) {
  return suggestWorkflowTemplate(taskDescription, constraints);
}

/**
 * Generate workflow file from task description
 *
 * @param {string} taskDescription - Natural language task
 * @param {string} outputPath - Output file path (absolute)
 * @param {object} options - Optional constraints
 * @returns {Promise<object>} Workflow metadata
 */
async function createWorkflow(taskDescription, outputPath, options = {}) {
  return await generateWorkflow(taskDescription, outputPath, options);
}

/**
 * Get inline workflow code (no file creation)
 *
 * @param {string} taskDescription - Task description
 * @param {string} templateName - Template to use (or auto-select)
 * @returns {string} Executable workflow code
 */
function getWorkflowCode(taskDescription, templateName = null) {
  if (!templateName) {
    const suggestion = suggestWorkflowTemplate(taskDescription);
    templateName = suggestion.recommended_template;
  }

  return generateWorkflowCode(templateName, taskDescription);
}

/**
 * Query historical patterns for similar workflows
 *
 * @param {string} taskDescription - Task to match
 * @param {number} limit - Number of results
 * @returns {Promise<Array>} Similar workflows from database
 */
async function findSimilarPatterns(taskDescription, limit = 10) {
  const db = getWorkflowStorage();
  return await db.findSimilarWorkflows(taskDescription, limit);
}

/**
 * Get workflow statistics and recommendations
 *
 * @param {string} workflowName - Template name
 * @returns {Promise<object>} Statistics from PostgreSQL
 */
async function getWorkflowStats(workflowName) {
  const db = getWorkflowStorage();

  const result = await db.pool.query(`
    SELECT
      workflow_name,
      COUNT(*) as total_executions,
      AVG(total_duration_ms) as avg_duration_ms,
      SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END)::float / COUNT(*) * 100 as success_rate,
      AVG((
        SELECT SUM(cost_usd)
        FROM workflow.worker_results wr
        WHERE wr.workflow_execution_id = e.id
      )) as avg_cost_usd
    FROM workflow.executions e
    WHERE workflow_name = $1
    GROUP BY workflow_name
  `, [workflowName]);

  return result.rows[0] || null;
}

/**
 * Generate workflow from template with runtime parameters
 *
 * @param {string} templateName - Template to use
 * @param {object} params - Runtime parameters
 * @returns {Function} Executable workflow function
 */
function instantiateTemplate(templateName, params) {
  const code = generateWorkflowCode(templateName, params.taskDescription || 'Task', params);

  // Create executable function (eval in sandboxed context)
  const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
  const workflowFn = new AsyncFunction('require', 'process', code + '\nreturn arguments[2];');

  return async (context) => {
    const exported = workflowFn(require, process);
    return await exported(context);
  };
}

/**
 * Batch workflow generation from task list
 */
async function generateWorkflows(tasks, outputDir) {
  return await generateBatch(tasks, outputDir);
}

/**
 * Integration status check
 */
function getIntegrationStatus() {
  const templatesPath = path.join(process.env.HOME, '.claude/learning/workflow_templates.json');
  const templates = JSON.parse(fs.readFileSync(templatesPath, 'utf8'));

  return {
    templates_loaded: templates.templates.length,
    templates_available: templates.templates.map(t => t.workflow_name),
    workflows_analyzed: templates.metadata.workflows_analyzed,
    data_source: templates.metadata.data_source,
    components: {
      template_suggester: fs.existsSync(templateSuggesterPath),
      auto_generator: fs.existsSync(autoGeneratorPath),
      workflow_storage: fs.existsSync(workflowStoragePath)
    }
  };
}

/**
 * CLI interface
 */
if (require.main === module) {
  const command = process.argv[2];

  if (command === 'status') {
    console.log(JSON.stringify(getIntegrationStatus(), null, 2));
  } else if (command === 'suggest') {
    const task = process.argv.slice(3).join(' ');
    const suggestion = suggestWorkflow(task);
    console.log(JSON.stringify(suggestion, null, 2));
  } else if (command === 'generate') {
    const task = process.argv[3];
    const output = process.argv[4];
    createWorkflow(task, output).then(result => {
      console.log(JSON.stringify(result, null, 2));
    });
  } else if (command === 'stats') {
    const workflowName = process.argv[3];
    getWorkflowStats(workflowName).then(stats => {
      console.log(JSON.stringify(stats, null, 2));
    });
  } else {
    console.log('Workflow Pattern Integration');
    console.log('\nCommands:');
    console.log('  status              - Show integration status');
    console.log('  suggest <task>      - Suggest template for task');
    console.log('  generate <task> <output> - Generate workflow file');
    console.log('  stats <workflow>    - Get workflow statistics');
    console.log('\nExamples:');
    console.log('  node workflow-pattern-integration.js status');
    console.log('  node workflow-pattern-integration.js suggest "Validate ML models"');
    console.log('  node workflow-pattern-integration.js stats deep-research');
  }
}

module.exports = {
  suggestWorkflow,
  createWorkflow,
  getWorkflowCode,
  findSimilarPatterns,
  getWorkflowStats,
  instantiateTemplate,
  generateWorkflows,
  getIntegrationStatus
};
