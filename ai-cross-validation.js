#!/usr/bin/env node

/**
 * @meta
 * name: ai-cross-validation
 * description: Cross-validation framework for evaluating and comparing AI consensus strategies
 * usage: /ai-cross-validation [options]
 * options:
 *   --dataset <path>        Path to JSON dataset with tasks and ground truth
 *   --strategies <list>     Comma-separated list of strategies to test (weighted,filtered,debate,refinement,basic)
 *   --k-folds <n>          Number of folds for k-fold cross-validation (default: 5)
 *   --test-split <ratio>   Train/test split ratio (default: 0.2)
 *   --metrics <list>       Comma-separated metrics to compute (accuracy,precision,recall,f1,confidence)
 *   --ab-test              Run A/B test comparing all strategies
 *   --bootstrap <n>        Bootstrap resampling iterations for confidence intervals (default: 1000)
 *   --output <path>        Output path for results JSON (default: ./cv-results.json)
 *   --report               Generate human-readable report
 * @end
 */

const { spawn } = require('child_process');
const fs = require('fs').promises;
const path = require('path');

// Strategy mapping to their workflow scripts
const STRATEGY_MAP = {
  weighted: 'ai-consensus-weighted.js',
  filtered: 'ai-consensus-filtered.js',
  debate: 'ai-consensus-debate.js',
  refinement: 'ai-consensus-refinement.js',
  basic: 'ai-consensus.js'
};

// Utility: Run agent with given strategy
async function runAgent(agentPath, task, options = {}) {
  return new Promise((resolve, reject) => {
    const args = ['--cwd', process.cwd(), '--task', JSON.stringify(task)];

    if (options.timeout) {
      args.push('--timeout', options.timeout);
    }

    const proc = spawn('claude', ['agent', agentPath, ...args], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Agent failed with code ${code}: ${stderr}`));
      } else {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch (e) {
          resolve({ response: stdout, raw: true });
        }
      }
    });
  });
}

// Split dataset into k folds
function createKFolds(dataset, k) {
  const folds = Array.from({ length: k }, () => []);
  const shuffled = [...dataset].sort(() => Math.random() - 0.5);

  shuffled.forEach((item, idx) => {
    folds[idx % k].push(item);
  });

  return folds;
}

// Split dataset into train/test
function trainTestSplit(dataset, testRatio) {
  const shuffled = [...dataset].sort(() => Math.random() - 0.5);
  const testSize = Math.floor(dataset.length * testRatio);

  return {
    train: shuffled.slice(testSize),
    test: shuffled.slice(0, testSize)
  };
}

// Compute metrics
function computeMetrics(predictions, groundTruth, options = {}) {
  const metrics = {};

  // Binary classification metrics
  let tp = 0, fp = 0, tn = 0, fn = 0;
  let totalError = 0;
  let totalConfidence = 0;
  let calibrationError = 0;

  predictions.forEach((pred, idx) => {
    const truth = groundTruth[idx];

    if (options.classification) {
      // Binary or multi-class classification
      if (pred.label === truth.label) {
        if (truth.label === 'positive' || truth.label === 1) {
          tp++;
        } else {
          tn++;
        }
      } else {
        if (pred.label === 'positive' || pred.label === 1) {
          fp++;
        } else {
          fn++;
        }
      }
    }

    // Regression metrics
    if (typeof pred.value === 'number' && typeof truth.value === 'number') {
      totalError += Math.abs(pred.value - truth.value);
    }

    // Confidence tracking
    if (pred.confidence !== undefined) {
      totalConfidence += pred.confidence;

      // Calibration: does confidence match correctness?
      const correct = (pred.label === truth.label) ? 1 : 0;
      calibrationError += Math.abs(pred.confidence - correct);
    }
  });

  const total = predictions.length;

  // Accuracy
  if (options.classification) {
    metrics.accuracy = (tp + tn) / total;

    // Precision
    metrics.precision = tp / (tp + fp) || 0;

    // Recall
    metrics.recall = tp / (tp + fn) || 0;

    // F1 Score
    metrics.f1 = (2 * metrics.precision * metrics.recall) /
                 (metrics.precision + metrics.recall) || 0;
  }

  // Mean Absolute Error (for regression)
  if (totalError > 0) {
    metrics.mae = totalError / total;
  }

  // Average Confidence
  if (totalConfidence > 0) {
    metrics.avgConfidence = totalConfidence / total;
  }

  // Calibration Error (Expected Calibration Error)
  if (calibrationError > 0) {
    metrics.calibrationError = calibrationError / total;
  }

  return metrics;
}

// Bootstrap resampling for confidence intervals
function bootstrap(data, metric, iterations = 1000) {
  const scores = [];

  for (let i = 0; i < iterations; i++) {
    const sample = [];
    for (let j = 0; j < data.length; j++) {
      const idx = Math.floor(Math.random() * data.length);
      sample.push(data[idx]);
    }
    scores.push(metric(sample));
  }

  scores.sort((a, b) => a - b);

  return {
    mean: scores.reduce((a, b) => a + b, 0) / scores.length,
    ci95: [
      scores[Math.floor(iterations * 0.025)],
      scores[Math.floor(iterations * 0.975)]
    ]
  };
}

// K-fold cross-validation
async function kFoldCrossValidation(dataset, strategy, k, options) {
  const folds = createKFolds(dataset, k);
  const results = [];

  console.error(`Running ${k}-fold CV for strategy: ${strategy}`);

  for (let i = 0; i < k; i++) {
    console.error(`  Fold ${i + 1}/${k}...`);

    // Create train/test sets
    const testFold = folds[i];
    const trainFolds = folds.filter((_, idx) => idx !== i).flat();

    // Run strategy on test fold
    const predictions = [];

    for (const testItem of testFold) {
      try {
        const result = await runAgent(
          path.join(__dirname, STRATEGY_MAP[strategy]),
          testItem.task,
          { timeout: options.timeout }
        );

        predictions.push({
          label: result.label || result.response,
          value: result.value,
          confidence: result.confidence
        });
      } catch (error) {
        console.error(`    Error on task: ${error.message}`);
        predictions.push({
          label: null,
          error: error.message
        });
      }
    }

    // Compute metrics for this fold
    const groundTruth = testFold.map(item => ({
      label: item.label,
      value: item.value
    }));

    const metrics = computeMetrics(predictions, groundTruth, {
      classification: options.classification
    });

    results.push({
      fold: i + 1,
      metrics,
      predictions,
      groundTruth
    });
  }

  // Aggregate results across folds
  const aggregated = {};
  const metricKeys = Object.keys(results[0].metrics);

  metricKeys.forEach(key => {
    const values = results.map(r => r.metrics[key]);
    aggregated[key] = {
      mean: values.reduce((a, b) => a + b, 0) / values.length,
      std: Math.sqrt(
        values.reduce((sum, val) => sum + Math.pow(val - aggregated[key]?.mean || 0, 2), 0) / values.length
      ),
      values
    };
  });

  return {
    strategy,
    kFolds: k,
    foldResults: results,
    aggregated
  };
}

// A/B test comparing strategies
async function abTest(dataset, strategies, options) {
  console.error('Running A/B test...');

  const { train, test } = trainTestSplit(dataset, options.testSplit);

  console.error(`Train set: ${train.length} samples`);
  console.error(`Test set: ${test.length} samples`);

  const results = {};

  for (const strategy of strategies) {
    console.error(`\nTesting strategy: ${strategy}`);

    const predictions = [];

    for (const testItem of test) {
      try {
        const result = await runAgent(
          path.join(__dirname, STRATEGY_MAP[strategy]),
          testItem.task,
          { timeout: options.timeout }
        );

        predictions.push({
          label: result.label || result.response,
          value: result.value,
          confidence: result.confidence,
          cost: result.cost,
          latency: result.latency
        });
      } catch (error) {
        console.error(`  Error on task: ${error.message}`);
        predictions.push({
          label: null,
          error: error.message
        });
      }
    }

    const groundTruth = test.map(item => ({
      label: item.label,
      value: item.value
    }));

    const metrics = computeMetrics(predictions, groundTruth, {
      classification: options.classification
    });

    // Bootstrap confidence intervals
    const bootstrapResults = {};
    if (options.bootstrap) {
      const paired = predictions.map((pred, idx) => ({
        pred,
        truth: groundTruth[idx]
      }));

      Object.keys(metrics).forEach(metricKey => {
        bootstrapResults[metricKey] = bootstrap(
          paired,
          (sample) => {
            const preds = sample.map(s => s.pred);
            const truths = sample.map(s => s.truth);
            return computeMetrics(preds, truths, {
              classification: options.classification
            })[metricKey];
          },
          options.bootstrap
        );
      });
    }

    results[strategy] = {
      metrics,
      bootstrap: bootstrapResults,
      predictions,
      groundTruth
    };
  }

  // Compare strategies
  const comparison = {
    winner: null,
    maxMetric: -Infinity
  };

  const primaryMetric = options.primaryMetric || 'accuracy';

  Object.entries(results).forEach(([strategy, result]) => {
    const score = result.metrics[primaryMetric];
    if (score > comparison.maxMetric) {
      comparison.maxMetric = score;
      comparison.winner = strategy;
    }
  });

  return {
    results,
    comparison,
    testSize: test.length,
    trainSize: train.length
  };
}

// Generate human-readable report
function generateReport(cvResults, abResults) {
  let report = '# AI Consensus Strategy Cross-Validation Report\n\n';
  report += `Generated: ${new Date().toISOString()}\n\n`;

  if (cvResults) {
    report += '## K-Fold Cross-Validation Results\n\n';

    Object.entries(cvResults).forEach(([strategy, result]) => {
      report += `### Strategy: ${strategy}\n\n`;
      report += `K-Folds: ${result.kFolds}\n\n`;
      report += '| Metric | Mean | Std Dev |\n';
      report += '|--------|------|----------|\n';

      Object.entries(result.aggregated).forEach(([metric, stats]) => {
        report += `| ${metric} | ${stats.mean.toFixed(4)} | ${stats.std.toFixed(4)} |\n`;
      });

      report += '\n';
    });
  }

  if (abResults) {
    report += '## A/B Test Results\n\n';
    report += `Train Size: ${abResults.trainSize}\n`;
    report += `Test Size: ${abResults.testSize}\n`;
    report += `Winner: **${abResults.comparison.winner}**\n\n`;

    report += '### Strategy Comparison\n\n';
    report += '| Strategy | Accuracy | Precision | Recall | F1 | Avg Confidence |\n';
    report += '|----------|----------|-----------|--------|----|-----------------|\n';

    Object.entries(abResults.results).forEach(([strategy, result]) => {
      const m = result.metrics;
      report += `| ${strategy} | ${(m.accuracy || 0).toFixed(4)} | ${(m.precision || 0).toFixed(4)} | ${(m.recall || 0).toFixed(4)} | ${(m.f1 || 0).toFixed(4)} | ${(m.avgConfidence || 0).toFixed(4)} |\n`;
    });

    report += '\n### Bootstrap Confidence Intervals (95%)\n\n';

    Object.entries(abResults.results).forEach(([strategy, result]) => {
      if (result.bootstrap && Object.keys(result.bootstrap).length > 0) {
        report += `**${strategy}**\n\n`;
        Object.entries(result.bootstrap).forEach(([metric, stats]) => {
          report += `- ${metric}: ${stats.mean.toFixed(4)} [${stats.ci95[0].toFixed(4)}, ${stats.ci95[1].toFixed(4)}]\n`;
        });
        report += '\n';
      }
    });
  }

  return report;
}

// Main execution
async function main() {
  const args = process.argv.slice(2);

  // Parse arguments
  const options = {
    dataset: null,
    strategies: ['weighted', 'filtered', 'debate', 'refinement', 'basic'],
    kFolds: 5,
    testSplit: 0.2,
    metrics: ['accuracy', 'precision', 'recall', 'f1', 'confidence'],
    abTest: false,
    bootstrap: 1000,
    output: './cv-results.json',
    report: false,
    classification: true,
    timeout: 300000,
    primaryMetric: 'accuracy'
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--dataset':
        options.dataset = args[++i];
        break;
      case '--strategies':
        options.strategies = args[++i].split(',');
        break;
      case '--k-folds':
        options.kFolds = parseInt(args[++i]);
        break;
      case '--test-split':
        options.testSplit = parseFloat(args[++i]);
        break;
      case '--metrics':
        options.metrics = args[++i].split(',');
        break;
      case '--ab-test':
        options.abTest = true;
        break;
      case '--bootstrap':
        options.bootstrap = parseInt(args[++i]);
        break;
      case '--output':
        options.output = args[++i];
        break;
      case '--report':
        options.report = true;
        break;
      case '--primary-metric':
        options.primaryMetric = args[++i];
        break;
      case '--timeout':
        options.timeout = parseInt(args[++i]);
        break;
      case '--help':
        console.log('AI Cross-Validation Framework');
        console.log('Usage: /ai-cross-validation [options]');
        console.log('Options:');
        console.log('  --dataset <path>        Path to JSON dataset');
        console.log('  --strategies <list>     Strategies to test (weighted,filtered,debate,refinement,basic)');
        console.log('  --k-folds <n>          Number of folds (default: 5)');
        console.log('  --test-split <ratio>   Train/test split (default: 0.2)');
        console.log('  --ab-test              Run A/B test');
        console.log('  --bootstrap <n>        Bootstrap iterations (default: 1000)');
        console.log('  --output <path>        Output JSON path');
        console.log('  --report               Generate markdown report');
        console.log('  --primary-metric <m>   Primary metric for comparison (default: accuracy)');
        process.exit(0);
    }
  }

  // Validate dataset
  if (!options.dataset) {
    console.error('Error: --dataset required');
    console.error('Dataset format: [{"task": "...", "label": "...", "value": ...}, ...]');
    process.exit(1);
  }

  // Load dataset
  let dataset;
  try {
    const data = await fs.readFile(options.dataset, 'utf8');
    dataset = JSON.parse(data);
  } catch (error) {
    console.error(`Error loading dataset: ${error.message}`);
    process.exit(1);
  }

  if (!Array.isArray(dataset) || dataset.length === 0) {
    console.error('Error: Dataset must be a non-empty array');
    process.exit(1);
  }

  console.error(`Loaded ${dataset.length} samples from ${options.dataset}`);

  // Run cross-validation
  const cvResults = {};

  if (!options.abTest) {
    for (const strategy of options.strategies) {
      if (!STRATEGY_MAP[strategy]) {
        console.error(`Warning: Unknown strategy ${strategy}, skipping`);
        continue;
      }

      cvResults[strategy] = await kFoldCrossValidation(
        dataset,
        strategy,
        options.kFolds,
        options
      );
    }
  }

  // Run A/B test
  let abResults = null;
  if (options.abTest) {
    const validStrategies = options.strategies.filter(s => STRATEGY_MAP[s]);
    abResults = await abTest(dataset, validStrategies, options);
  }

  // Save results
  const results = {
    timestamp: new Date().toISOString(),
    options,
    crossValidation: cvResults,
    abTest: abResults
  };

  await fs.writeFile(options.output, JSON.stringify(results, null, 2));
  console.error(`\nResults saved to ${options.output}`);

  // Generate report
  if (options.report) {
    const reportPath = options.output.replace('.json', '.md');
    const report = generateReport(cvResults, abResults);
    await fs.writeFile(reportPath, report);
    console.error(`Report saved to ${reportPath}`);
  }

  // Output summary to stdout
  console.log(JSON.stringify({
    summary: {
      datasetSize: dataset.length,
      strategiesTested: Object.keys(cvResults).length || options.strategies.length,
      winner: abResults?.comparison.winner,
      resultsPath: options.output
    },
    cvResults,
    abResults
  }, null, 2));
}

if (require.main === module) {
  main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = {
  runAgent,
  createKFolds,
  trainTestSplit,
  computeMetrics,
  bootstrap,
  kFoldCrossValidation,
  abTest,
  generateReport
};
