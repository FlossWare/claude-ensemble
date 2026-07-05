/**
 * Merge Conflict Predictor Adapter (JavaScript/Node.js)
 * Wrapper for Python-based merge conflict predictor
 *
 * Usage:
 *   const { predictConflicts, trainPredictor } = require('./shared/merge-conflict-predictor-adapter.js');
 *
 *   // Train model
 *   await trainPredictor();
 *
 *   // Predict conflicts
 *   const results = await predictConflicts('main', 'feature-branch');
 *   console.log(`Found ${results.highRisk.length} high-risk conflicts`);
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const PREDICTOR_SCRIPT = path.join(__dirname, '..', 'tools', 'merge_conflict_predictor.py');
const PREDICTIONS_FILE = path.join(os.homedir(), '.claude', 'learning', 'merge_conflict_predictions.json');
const MODEL_FILE = path.join(os.homedir(), '.claude', 'learning', 'merge_conflict_predictor.pkl');

/**
 * Train merge conflict prediction model
 * @param {string} repoPath - Path to git repository (default: current directory)
 * @returns {Promise<Object>} Training statistics
 */
async function trainPredictor(repoPath = '.') {
  console.log('Training merge conflict predictor...');

  try {
    const output = execSync(
      `python3 "${PREDICTOR_SCRIPT}" --train --repo "${repoPath}"`,
      { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 }
    );

    console.log(output);

    // Load stats
    const statsFile = path.join(os.homedir(), '.claude', 'learning', 'merge_conflict_stats.json');
    if (fs.existsSync(statsFile)) {
      const stats = JSON.parse(fs.readFileSync(statsFile, 'utf8'));
      return {
        success: true,
        totalMerges: stats.total_merges || 0,
        conflictMerges: stats.conflict_merges || 0,
        filesTracked: Object.keys(stats.comod_matrix || {}).length,
        trainedAt: stats.trained_at
      };
    }

    return { success: true };
  } catch (error) {
    console.error('Training failed:', error.message);
    return { success: false, error: error.message };
  }
}

/**
 * Predict merge conflicts between two branches
 * @param {string} branch1 - Target branch (base)
 * @param {string} branch2 - Source branch (to be merged)
 * @param {string} repoPath - Path to git repository (default: current directory)
 * @returns {Promise<Object>} Conflict predictions
 */
async function predictConflicts(branch1, branch2, repoPath = '.') {
  // Check if model exists
  if (!fs.existsSync(MODEL_FILE)) {
    console.warn('Model not trained. Training now...');
    await trainPredictor(repoPath);
  }

  console.log(`Predicting conflicts: ${branch2} → ${branch1}...`);

  try {
    const output = execSync(
      `python3 "${PREDICTOR_SCRIPT}" --predict "${branch1}" "${branch2}" --repo "${repoPath}"`,
      { encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 }
    );

    console.log(output);

    // Load predictions
    if (!fs.existsSync(PREDICTIONS_FILE)) {
      return {
        success: false,
        error: 'Predictions file not created'
      };
    }

    const predictions = JSON.parse(fs.readFileSync(PREDICTIONS_FILE, 'utf8'));

    // Categorize by risk
    const highRisk = predictions.predictions.filter(p => p.risk === 'HIGH');
    const mediumRisk = predictions.predictions.filter(p => p.risk === 'MEDIUM');
    const lowRisk = predictions.predictions.filter(p => p.risk === 'LOW');

    return {
      success: true,
      branch1: predictions.branch1,
      branch2: predictions.branch2,
      timestamp: predictions.timestamp,
      totalPredictions: predictions.predictions.length,
      highRisk: highRisk,
      mediumRisk: mediumRisk,
      lowRisk: lowRisk,
      predictions: predictions.predictions,
      summary: {
        hasHighRisk: highRisk.length > 0,
        hasMediumRisk: mediumRisk.length > 0,
        riskScore: calculateRiskScore(predictions.predictions)
      }
    };
  } catch (error) {
    console.error('Prediction failed:', error.message);
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Calculate overall risk score (0-100)
 * @param {Array} predictions - List of predictions
 * @returns {number} Risk score
 */
function calculateRiskScore(predictions) {
  if (predictions.length === 0) return 0;

  // Weighted average: HIGH=1.0, MEDIUM=0.5, LOW=0.2
  const weights = { HIGH: 1.0, MEDIUM: 0.5, LOW: 0.2 };

  const totalWeight = predictions.reduce((sum, p) =>
    sum + (weights[p.risk] || 0) * p.conflict_probability, 0
  );

  return Math.round((totalWeight / predictions.length) * 100);
}

/**
 * Format predictions for display
 * @param {Object} results - Results from predictConflicts()
 * @returns {string} Formatted report
 */
function formatReport(results) {
  if (!results.success) {
    return `❌ Prediction failed: ${results.error}`;
  }

  const lines = [];
  lines.push('═'.repeat(60));
  lines.push(`Merge Conflict Risk Report`);
  lines.push(`${results.branch2} → ${results.branch1}`);
  lines.push('═'.repeat(60));
  lines.push('');

  if (results.totalPredictions === 0) {
    lines.push('✅ No conflicts predicted!');
    lines.push('');
    return lines.join('\n');
  }

  lines.push(`Total predictions: ${results.totalPredictions}`);
  lines.push(`  HIGH risk:   ${results.highRisk.length}`);
  lines.push(`  MEDIUM risk: ${results.mediumRisk.length}`);
  lines.push(`  LOW risk:    ${results.lowRisk.length}`);
  lines.push(`  Risk score:  ${results.summary.riskScore}/100`);
  lines.push('');

  if (results.highRisk.length > 0) {
    lines.push('─'.repeat(60));
    lines.push('🚨 HIGH RISK Conflicts:');
    lines.push('─'.repeat(60));

    for (const p of results.highRisk.slice(0, 10)) {
      lines.push('');
      lines.push(`  File 1: ${p.file1}`);
      lines.push(`  File 2: ${p.file2}`);
      lines.push(`  Type:   ${p.type}`);
      lines.push(`  Probability: ${(p.conflict_probability * 100).toFixed(1)}%`);
    }

    lines.push('');
  }

  if (results.mediumRisk.length > 0) {
    lines.push('─'.repeat(60));
    lines.push('⚠️  MEDIUM RISK Conflicts:');
    lines.push('─'.repeat(60));

    for (const p of results.mediumRisk.slice(0, 5)) {
      lines.push(`  ${p.file1} ↔ ${p.file2} (${(p.conflict_probability * 100).toFixed(1)}%)`);
    }

    lines.push('');
  }

  lines.push('═'.repeat(60));
  lines.push(`Full report: ${PREDICTIONS_FILE}`);
  lines.push('═'.repeat(60));

  return lines.join('\n');
}

/**
 * Check if merge is safe (no high-risk conflicts)
 * @param {string} branch1 - Target branch
 * @param {string} branch2 - Source branch
 * @param {Object} options - Options
 * @param {number} options.maxHighRisk - Max allowed high-risk conflicts (default: 0)
 * @param {number} options.maxRiskScore - Max allowed risk score (default: 50)
 * @returns {Promise<Object>} Safety check result
 */
async function isMergeSafe(branch1, branch2, options = {}) {
  const maxHighRisk = options.maxHighRisk ?? 0;
  const maxRiskScore = options.maxRiskScore ?? 50;

  const results = await predictConflicts(branch1, branch2);

  if (!results.success) {
    return {
      safe: false,
      reason: 'Prediction failed',
      error: results.error
    };
  }

  if (results.highRisk.length > maxHighRisk) {
    return {
      safe: false,
      reason: `Too many high-risk conflicts (${results.highRisk.length} > ${maxHighRisk})`,
      results
    };
  }

  if (results.summary.riskScore > maxRiskScore) {
    return {
      safe: false,
      reason: `Risk score too high (${results.summary.riskScore} > ${maxRiskScore})`,
      results
    };
  }

  return {
    safe: true,
    reason: 'No significant conflict risk detected',
    results
  };
}

/**
 * Get model information
 * @returns {Object} Model info
 */
function getModelInfo() {
  const modelExists = fs.existsSync(MODEL_FILE);
  const statsFile = path.join(os.homedir(), '.claude', 'learning', 'merge_conflict_stats.json');
  const statsExist = fs.existsSync(statsFile);

  if (!modelExists) {
    return {
      trained: false,
      message: 'Model not trained. Run trainPredictor() first.'
    };
  }

  const modelStats = fs.statSync(MODEL_FILE);

  const info = {
    trained: true,
    modelPath: MODEL_FILE,
    modelSize: `${(modelStats.size / 1024).toFixed(1)} KB`,
    lastModified: modelStats.mtime.toISOString()
  };

  if (statsExist) {
    const stats = JSON.parse(fs.readFileSync(statsFile, 'utf8'));
    info.stats = {
      totalMerges: stats.total_merges || 0,
      conflictMerges: stats.conflict_merges || 0,
      filesTracked: Object.keys(stats.comod_matrix || {}).length,
      trainedAt: stats.trained_at
    };
  }

  return info;
}

module.exports = {
  trainPredictor,
  predictConflicts,
  isMergeSafe,
  formatReport,
  getModelInfo,
  calculateRiskScore
};

// CLI usage
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args[0] === 'train') {
    trainPredictor().then(result => {
      console.log('\nTraining result:', result);
    });
  } else if (args[0] === 'predict' && args.length >= 3) {
    predictConflicts(args[1], args[2]).then(results => {
      console.log(formatReport(results));
    });
  } else if (args[0] === 'check' && args.length >= 3) {
    isMergeSafe(args[1], args[2]).then(result => {
      console.log('\n' + (result.safe ? '✅' : '❌'), result.reason);
      if (result.results) {
        console.log(formatReport(result.results));
      }
      process.exit(result.safe ? 0 : 1);
    });
  } else if (args[0] === 'info') {
    const info = getModelInfo();
    console.log(JSON.stringify(info, null, 2));
  } else {
    console.log('Usage:');
    console.log('  node merge-conflict-predictor-adapter.js train');
    console.log('  node merge-conflict-predictor-adapter.js predict <branch1> <branch2>');
    console.log('  node merge-conflict-predictor-adapter.js check <branch1> <branch2>');
    console.log('  node merge-conflict-predictor-adapter.js info');
  }
}
