#!/usr/bin/env node
/**
 * Integration Example: Complexity Estimator in Workflow Orchestration
 *
 * Shows how to use the complexity estimator to make better routing decisions:
 * - Predict task difficulty before execution
 * - Select appropriate models based on complexity
 * - Allocate timeouts and retries based on predictions
 */

const { execSync } = require('child_process');
const path = require('path');

class ComplexityEstimatorClient {
  constructor() {
    this.pythonScript = path.join(__dirname, 'complexity_estimator.py');
    this.modelPath = path.join(process.env.HOME, '.claude/learning/complexity_estimator.pkl');
  }

  predict(taskDescription) {
    const predictScript = path.join(__dirname, 'predict_complexity.py');

    try {
      const result = execSync(`python3 "${predictScript}" "${taskDescription}"`, {
        encoding: 'utf-8',
        timeout: 10000
      });

      // Parse only the JSON line (skip loading message)
      const lines = result.trim().split('\n');
      const jsonLine = lines[lines.length - 1];
      return JSON.parse(jsonLine);
    } catch (error) {
      console.error('Complexity prediction failed:', error.message);
      return null;
    }
  }

  /**
   * Route task to appropriate model based on complexity
   */
  selectModel(taskDescription) {
    const prediction = this.predict(taskDescription);
    if (!prediction) {
      // Fallback to medium-tier model
      return { model: 'sonnet', timeout: 30000, maxRetries: 2 };
    }

    const { complexity_category, predicted_confidence } = prediction;

    // Select model based on complexity
    let model, timeout, maxRetries;

    switch (complexity_category) {
      case 'SIMPLE':
        model = 'haiku';  // Fast, cheap
        timeout = 10000;
        maxRetries = 1;
        break;

      case 'MEDIUM':
        model = predicted_confidence > 0.7 ? 'haiku' : 'sonnet';
        timeout = 30000;
        maxRetries = 2;
        break;

      case 'COMPLEX':
        model = predicted_confidence > 0.6 ? 'sonnet' : 'opus';
        timeout = 60000;
        maxRetries = 3;
        break;

      case 'VERY_COMPLEX':
        model = 'opus';  // Top-tier
        timeout = 120000;
        maxRetries = 3;
        break;

      default:
        model = 'sonnet';
        timeout = 30000;
        maxRetries = 2;
    }

    return {
      model,
      timeout,
      maxRetries,
      prediction
    };
  }

  /**
   * Estimate resource allocation
   */
  estimateResources(tasks) {
    const estimates = tasks.map(task => ({
      task: task.description || task,
      ...this.predict(task.description || task)
    }));

    const totalDuration = estimates.reduce((sum, e) => sum + e.predicted_duration_ms, 0);
    const avgConfidence = estimates.reduce((sum, e) => sum + e.predicted_confidence, 0) / estimates.length;

    const complexityDistribution = {
      SIMPLE: 0,
      MEDIUM: 0,
      COMPLEX: 0,
      VERY_COMPLEX: 0
    };

    estimates.forEach(e => {
      complexityDistribution[e.complexity_category]++;
    });

    return {
      totalDuration,
      avgConfidence,
      complexityDistribution,
      estimates
    };
  }
}

// Example usage
if (require.main === module) {
  const estimator = new ComplexityEstimatorClient();

  console.log('=' .repeat(70));
  console.log('COMPLEXITY ESTIMATOR - WORKFLOW INTEGRATION');
  console.log('=' .repeat(70));

  // Example tasks
  const tasks = [
    "Fix typo in README",
    "Implement JWT authentication",
    "Review security vulnerabilities in 10 files",
    "Create Java Spring Boot service",
    "Optimize database queries",
  ];

  console.log('\n📊 Task Routing Decisions:\n');

  tasks.forEach(task => {
    const routing = estimator.selectModel(task);
    console.log(`Task: ${task}`);
    console.log(`  → Model:      ${routing.model}`);
    console.log(`  → Timeout:    ${routing.timeout}ms`);
    console.log(`  → Max Retries: ${routing.maxRetries}`);
    if (routing.prediction) {
      console.log(`  → Category:   ${routing.prediction.complexity_category}`);
      console.log(`  → Confidence: ${routing.prediction.predicted_confidence.toFixed(2)}`);
    }
    console.log('');
  });

  // Resource estimation
  console.log('=' .repeat(70));
  console.log('📈 Resource Estimation:\n');

  const resources = estimator.estimateResources(tasks);
  console.log(`Total Duration: ${(resources.totalDuration / 1000).toFixed(1)}s`);
  console.log(`Avg Confidence: ${resources.avgConfidence.toFixed(2)}`);
  console.log('\nComplexity Distribution:');
  Object.entries(resources.complexityDistribution).forEach(([cat, count]) => {
    if (count > 0) {
      console.log(`  ${cat.padEnd(15)}: ${count} tasks`);
    }
  });

  console.log('\n' + '=' .repeat(70));
  console.log('✅ Integration Example Complete');
  console.log('=' .repeat(70));
}

module.exports = ComplexityEstimatorClient;
