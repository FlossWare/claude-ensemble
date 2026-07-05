/**
 * Dependency Risk Analyzer Integration
 *
 * JavaScript wrapper for the Python-based dependency risk analyzer.
 * Analyzes package dependencies and returns risk levels.
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

/**
 * Analyze a single dependency
 * @param {Object} dependencyInfo - Dependency metadata
 * @returns {Object} Risk analysis result
 */
function analyzeDependency(dependencyInfo) {
  const tmpFile = `/tmp/dep_${Date.now()}.json`;

  try {
    // Write dependency info to temp file
    fs.writeFileSync(tmpFile, JSON.stringify(dependencyInfo, null, 2));

    // Run prediction
    const result = execSync(
      `python3 tools/predict_dependency_risk.py --json ${tmpFile}`,
      { encoding: 'utf-8', cwd: path.join(__dirname, '..') }
    );

    // Parse output
    const lines = result.split('\n');
    const riskLevel = lines.find(l => l.includes('Risk Level:'))?.split(':')[1]?.trim();

    // Extract probabilities
    const probabilities = {};
    lines.forEach(line => {
      const match = line.match(/^\s*(\w+)\s*:\s*(\d+\.\d+)%/);
      if (match) {
        probabilities[match[1]] = parseFloat(match[2]) / 100;
      }
    });

    return {
      dependency: dependencyInfo.name,
      risk_level: riskLevel || 'UNKNOWN',
      probabilities,
      raw_output: result
    };
  } finally {
    // Cleanup temp file
    if (fs.existsSync(tmpFile)) {
      fs.unlinkSync(tmpFile);
    }
  }
}

/**
 * Scan package.json and analyze all dependencies
 * @param {string} packageJsonPath - Path to package.json
 * @returns {Array<Object>} Array of risk analysis results
 */
function scanPackageJson(packageJsonPath) {
  const result = execSync(
    `python3 tools/predict_dependency_risk.py --scan ${packageJsonPath}`,
    { encoding: 'utf-8', cwd: path.join(__dirname, '..') }
  );

  // Parse output
  const lines = result.split('\n');
  const dependencies = [];

  // Find the table section
  let inTable = false;
  for (const line of lines) {
    if (line.includes('Package') && line.includes('Risk Level')) {
      inTable = true;
      continue;
    }

    if (inTable && line.includes('------')) {
      continue;
    }

    if (inTable && line.trim()) {
      // Parse table row: "package-name    🔴 CRITICAL    95.0%"
      const match = line.match(/^(.+?)\s+[🔴🟠🟡🟢⚪]\s+(\w+)\s+(\d+\.\d+)%/);
      if (match) {
        dependencies.push({
          name: match[1].trim(),
          risk_level: match[2],
          confidence: parseFloat(match[3]) / 100
        });
      }
    }

    if (inTable && line.includes('===')) {
      break;
    }
  }

  return {
    total: dependencies.length,
    dependencies,
    summary: {
      critical: dependencies.filter(d => d.risk_level === 'CRITICAL').length,
      high: dependencies.filter(d => d.risk_level === 'HIGH').length,
      medium: dependencies.filter(d => d.risk_level === 'MEDIUM').length,
      low: dependencies.filter(d => d.risk_level === 'LOW').length
    },
    raw_output: result
  };
}

/**
 * Check if any dependencies have critical or high risk
 * @param {Array<Object>} results - Analysis results
 * @returns {boolean} True if critical/high risks found
 */
function hasHighRiskDependencies(results) {
  if (Array.isArray(results)) {
    return results.some(r => ['CRITICAL', 'HIGH'].includes(r.risk_level));
  }
  return results.summary.critical > 0 || results.summary.high > 0;
}

/**
 * Format risk analysis for console output
 * @param {Object} analysis - Analysis results
 * @returns {string} Formatted output
 */
function formatRiskReport(analysis) {
  const emoji = {
    CRITICAL: '🔴',
    HIGH: '🟠',
    MEDIUM: '🟡',
    LOW: '🟢'
  };

  if (analysis.dependencies) {
    // Package scan result
    let report = `\n📦 Dependency Risk Analysis\n`;
    report += `${'='.repeat(60)}\n\n`;

    if (analysis.summary.critical > 0 || analysis.summary.high > 0) {
      report += `⚠️  HIGH RISK DEPENDENCIES DETECTED\n\n`;
    }

    report += `Summary:\n`;
    report += `  🔴 Critical: ${analysis.summary.critical}\n`;
    report += `  🟠 High:     ${analysis.summary.high}\n`;
    report += `  🟡 Medium:   ${analysis.summary.medium}\n`;
    report += `  🟢 Low:      ${analysis.summary.low}\n`;
    report += `  Total:      ${analysis.total}\n\n`;

    // List high-risk packages
    const highRisk = analysis.dependencies.filter(d =>
      ['CRITICAL', 'HIGH'].includes(d.risk_level)
    );

    if (highRisk.length > 0) {
      report += `High-Risk Packages:\n`;
      highRisk.forEach(dep => {
        report += `  ${emoji[dep.risk_level]} ${dep.name} - ${dep.risk_level} (${(dep.confidence * 100).toFixed(1)}%)\n`;
      });
    }

    return report;
  } else {
    // Single dependency result
    const icon = emoji[analysis.risk_level] || '⚪';
    return `${icon} ${analysis.dependency}: ${analysis.risk_level}`;
  }
}

module.exports = {
  analyzeDependency,
  scanPackageJson,
  hasHighRiskDependencies,
  formatRiskReport
};

// CLI usage
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args[0] === '--scan' && args[1]) {
    const results = scanPackageJson(args[1]);
    console.log(formatRiskReport(results));

    // Exit with error if high-risk dependencies found
    if (hasHighRiskDependencies(results)) {
      process.exit(1);
    }
  } else if (args[0] === '--help') {
    console.log(`
Usage:
  node shared/dependency-risk-analyzer.js --scan package.json

Returns exit code 1 if CRITICAL or HIGH risk dependencies found.
    `);
  } else {
    console.error('Usage: --scan <package.json>');
    process.exit(1);
  }
}
