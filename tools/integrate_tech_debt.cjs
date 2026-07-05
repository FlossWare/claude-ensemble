#!/usr/bin/env node
/**
 * Integration script for Tech Debt Quantifier
 * Analyzes directory and stores results in PostgreSQL workflow storage
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

/**
 * Analyze tech debt for a directory
 */
function analyzeTechDebt(dirPath, options = {}) {
  const {
    threshold = 60.0,
    topN = 10,
  } = options;

  console.log(`\n🔍 Analyzing tech debt in: ${dirPath}`);

  try {
    // Run Python analyzer
    const cmd = `python3 ${__dirname}/analyze_tech_debt.py "${dirPath}" --threshold ${threshold} --top ${topN} --json`;
    const output = execSync(cmd, { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024 });

    // Parse output (skip the "Models loaded" line)
    const lines = output.split('\n');
    const jsonStartIdx = lines.findIndex(line => line.trim().startsWith('{'));
    const jsonOutput = lines.slice(jsonStartIdx).join('\n');
    const result = JSON.parse(jsonOutput);

    console.log(`\n✅ Analysis complete`);
    console.log(`   Total files: ${result.total_files}`);
    console.log(`   Avg debt:    ${result.avg_debt_score.toFixed(1)}/100`);
    console.log(`   Critical:    ${result.critical_files} files`);
    console.log(`   Fix time:    ${result.total_estimated_fix_hours.toFixed(1)} hours`);

    return result;

  } catch (error) {
    console.error('❌ Error analyzing tech debt:', error.message);
    throw error;
  }
}

/**
 * Analyze single file
 */
function analyzeFile(filePath) {
  console.log(`\n📄 Analyzing file: ${filePath}`);

  try {
    const cmd = `python3 ${__dirname}/analyze_tech_debt.py "${filePath}" --json`;
    const output = execSync(cmd, { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024 });

    // Parse output
    const lines = output.split('\n');
    const jsonStartIdx = lines.findIndex(line => line.trim().startsWith('{'));
    const jsonOutput = lines.slice(jsonStartIdx).join('\n');
    const result = JSON.parse(jsonOutput);

    console.log(`\n✅ Analysis complete`);
    console.log(`   Debt score:  ${result.debt_score.toFixed(1)}/100 (${result.debt_level})`);
    console.log(`   Priority:    ${result.priority_score.toFixed(1)}/100`);
    console.log(`   Fix time:    ${result.estimated_fix_hours.toFixed(1)} hours`);
    console.log(`   ${result.recommendation}`);

    return result;

  } catch (error) {
    console.error('❌ Error analyzing file:', error.message);
    throw error;
  }
}

/**
 * Store results in workflow storage (if available)
 */
async function storeResults(results, metadata = {}) {
  try {
    // Try to load workflow storage adapter
    const adapterPath = path.join(__dirname, '..', 'shared', 'workflow-storage-adapter.js');
    if (!fs.existsSync(adapterPath)) {
      console.log('⚠ Workflow storage not available - skipping storage');
      return null;
    }

    const { getWorkflowStorage } = require(adapterPath);
    const db = getWorkflowStorage();

    const execId = await db.storeExecution({
      workflow_id: `tech-debt-${Date.now()}`,
      workflow_name: 'tech-debt-analysis',
      task_description: metadata.description || 'Tech debt quantification',
      total_workers: 1,
      total_duration_ms: metadata.duration_ms || 0,
      outcome: 'success',
    });

    // Store as learning
    if (results.total_files) {
      await db.storeLearnings({
        workflow_execution_id: execId,
        description: 'Tech debt analysis results',
        actionable_insight: `${results.critical_files} critical files found, ${results.total_estimated_fix_hours.toFixed(1)}h fix estimate`,
        importance: Math.min(1.0, results.avg_debt_score / 100),
        evidence: JSON.stringify(results.top_priority_files?.slice(0, 5) || []),
      });
    }

    console.log(`\n✅ Results stored in workflow database (execution_id: ${execId})`);
    return execId;

  } catch (error) {
    console.log(`⚠ Could not store results: ${error.message}`);
    return null;
  }
}

/**
 * Generate tech debt report
 */
function generateReport(results, outputPath) {
  const lines = [
    '# Tech Debt Analysis Report',
    '',
    `**Generated:** ${new Date().toISOString()}`,
    '',
    '## Summary',
    '',
    `- **Total Files:** ${results.total_files}`,
    `- **Average Debt Score:** ${results.avg_debt_score.toFixed(1)}/100`,
    `- **Critical Files:** ${results.critical_files}`,
    `- **Estimated Fix Time:** ${results.total_estimated_fix_hours.toFixed(1)} hours`,
    '',
    '## Top Priority Files',
    '',
  ];

  if (results.top_priority_files && results.top_priority_files.length > 0) {
    results.top_priority_files.forEach((file, idx) => {
      const fileName = path.basename(file.file_path);
      lines.push(`### ${idx + 1}. ${fileName}`);
      lines.push('');
      lines.push(`- **Debt Score:** ${file.debt_score.toFixed(1)}/100 (${file.debt_level})`);
      lines.push(`- **Priority:** ${file.priority_score.toFixed(1)}/100`);
      lines.push(`- **Fix Estimate:** ${file.estimated_fix_hours.toFixed(1)} hours`);
      lines.push(`- **Recommendation:** ${file.recommendation}`);
      lines.push('');
      lines.push('**Metrics:**');
      lines.push(`- Maintainability Index: ${file.maintainability_index.toFixed(1)}`);
      lines.push(`- Code Smell Score: ${file.smell_score.toFixed(1)}`);
      lines.push(`- Debt Indicators: ${file.debt_indicators}`);
      lines.push('');
    });
  }

  const report = lines.join('\n');
  fs.writeFileSync(outputPath, report);
  console.log(`\n✅ Report saved to: ${outputPath}`);

  return report;
}

// CLI interface
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log(`
Usage:
  node integrate_tech_debt.cjs <directory> [options]
  node integrate_tech_debt.cjs --file <file_path>

Options:
  --threshold <score>  Debt score threshold (default: 60)
  --top <n>            Show top N files (default: 10)
  --report <path>      Generate markdown report
  --store              Store results in workflow database

Examples:
  node integrate_tech_debt.cjs ./tools
  node integrate_tech_debt.cjs ./tools --threshold 70 --top 20 --report report.md
  node integrate_tech_debt.cjs --file ./tools/complexity_estimator.py
    `);
    process.exit(0);
  }

  (async () => {
    try {
      const options = {};
      let targetPath = args[0];
      let isFile = false;

      // Parse args
      for (let i = 0; i < args.length; i++) {
        if (args[i] === '--threshold') options.threshold = parseFloat(args[++i]);
        if (args[i] === '--top') options.topN = parseInt(args[++i]);
        if (args[i] === '--report') options.reportPath = args[++i];
        if (args[i] === '--store') options.store = true;
        if (args[i] === '--file') {
          isFile = true;
          targetPath = args[++i];
        }
      }

      const startTime = Date.now();

      // Analyze
      let results;
      if (isFile) {
        results = analyzeFile(targetPath);
      } else {
        results = analyzeTechDebt(targetPath, options);
      }

      const duration_ms = Date.now() - startTime;

      // Generate report if requested
      if (options.reportPath && !isFile) {
        generateReport(results, options.reportPath);
      }

      // Store if requested
      if (options.store && !isFile) {
        await storeResults(results, {
          description: `Tech debt analysis of ${targetPath}`,
          duration_ms,
        });
      }

      console.log(`\n✅ Complete (${(duration_ms / 1000).toFixed(1)}s)`);

    } catch (error) {
      console.error('\n❌ Error:', error.message);
      process.exit(1);
    }
  })();
}

module.exports = {
  analyzeTechDebt,
  analyzeFile,
  storeResults,
  generateReport,
};
