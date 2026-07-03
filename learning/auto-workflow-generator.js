#!/usr/bin/env node

/**
 * Auto Workflow Generator
 *
 * Generates complete workflow files from task descriptions using
 * historical pattern matching and template-based code generation.
 *
 * Usage:
 *   const { generateWorkflow } = require('./auto-workflow-generator.js');
 *   await generateWorkflow('Validate ML model performance', './workflows/validate-ml.mjs');
 *
 * CLI:
 *   node auto-workflow-generator.js "Task description" output-file.mjs
 */

const fs = require('fs');
const path = require('path');
const { suggestWorkflowTemplate, generateWorkflowCode } = require('./workflow-template-suggester.js');

/**
 * Generate complete workflow file from task description
 *
 * @param {string} taskDescription - Natural language task
 * @param {string} outputPath - Output file path (absolute)
 * @param {object} options - Optional constraints
 * @returns {object} Metadata about generated workflow
 */
async function generateWorkflow(taskDescription, outputPath, options = {}) {
  // Get template suggestion
  const suggestion = suggestWorkflowTemplate(taskDescription, options);

  // Generate code
  const code = generateWorkflowCode(
    suggestion.recommended_template,
    taskDescription,
    options
  );

  // Write to file
  fs.writeFileSync(outputPath, code);
  fs.chmodSync(outputPath, 0o755);

  return {
    workflow_file: outputPath,
    template_used: suggestion.recommended_template,
    confidence: suggestion.confidence,
    predicted_cost: suggestion.predicted_cost_usd,
    predicted_duration_ms: suggestion.predicted_duration_ms,
    workers: suggestion.configuration.recommended_workers,
    parallel_strategy: suggestion.configuration.parallel_strategy,
    best_practices: suggestion.best_practices,
    reasoning: suggestion.reasoning
  };
}

/**
 * Generate multiple workflows in batch
 */
async function generateBatch(tasks, outputDir) {
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const results = [];

  for (const task of tasks) {
    const fileName = task.taskDescription
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
      .substring(0, 50) + '.mjs';

    const outputPath = path.join(outputDir, fileName);

    const result = await generateWorkflow(
      task.taskDescription,
      outputPath,
      task.options || {}
    );

    results.push(result);
  }

  return results;
}

/**
 * CLI interface
 */
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length < 2) {
    console.log('Usage: node auto-workflow-generator.js <task description> <output-file.mjs>');
    console.log('\nExample:');
    console.log('  node auto-workflow-generator.js "Validate ML models" ./workflows/validate.mjs');
    process.exit(1);
  }

  const taskDescription = args[0];
  const outputPath = path.resolve(args[1]);

  generateWorkflow(taskDescription, outputPath).then(result => {
    console.log(JSON.stringify(result, null, 2));
    console.log(`\nWorkflow generated: ${result.workflow_file}`);
    console.log(`Template: ${result.template_used} (${result.confidence} confidence)`);
    console.log(`Predicted cost: $${result.predicted_cost}`);
    console.log(`Predicted duration: ${result.predicted_duration_ms}ms`);
  }).catch(err => {
    console.error('Error generating workflow:', err.message);
    process.exit(1);
  });
}

module.exports = {
  generateWorkflow,
  generateBatch
};
