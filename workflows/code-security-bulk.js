/**
 * code-security-bulk.js
 *
 * Fleet-distributed security scanning for large codebases.
 * Use case: 500+ source files scanned in parallel.
 *
 * Multi-session orchestration:
 *   - Controller: Discovers all source files
 *   - Splits into 3 batches by language and size
 *   - Worker-01-03: Each processes batch via independent Claude Code session
 *   - Workers call code-security for their file batch
 *   - Workers output JSON findings
 *   - Controller deduplicates and severity-ranks findings
 *
 * Per-file timing:
 *   - AST parse + scan: 2s per file
 *   - Multi-model analysis: 2-3s per file
 *   - Total: ~5s per file
 *   - Sequential (500 files): 41 minutes
 *   - Fleet (3 workers): 14 minutes
 *
 * Deduplication:
 *   - By file:line:type key
 *   - Keep higher severity when duplicates found
 */

export const meta = {
  name: 'code-security-bulk',
  description: 'Fleet-distributed security scanning - audit 500+ files in parallel',
  whenToUse: 'When you need comprehensive security scan of a large codebase',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover available fleet workers' },
    { title: 'File Discovery', detail: 'Find all source files in codebase' },
    { title: 'Batch Distribution', detail: 'Split files by language and size' },
    { title: 'Parallel Scanning', detail: 'Each worker scans its batch via code-security' },
    { title: 'Finding Merge', detail: 'Deduplicate and rank security findings' },
    { title: 'Report Generation', detail: 'Create vulnerability summary report' },
  ],
};

// === FLEET DISPATCHER INTEGRATION (inline - no imports needed) ===
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true; // Set to false to disable fleet telemetry

async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) return null;
  try {
    const response = await fetch(`${FLEET_DISPATCHER}/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt: prompt.slice(0, 200),
        job_type: jobType,
        estimated_ram: model === 'opus' || model === 'fable' ? 2.0 : model === 'haiku' ? 0.5 : 1.5,
        estimated_duration: 60
      }),
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (e) {
    return null;
  }
}

async function _completeAgent(jobId, server, success, duration, jobType, model, error) {
  if (!FLEET_ENABLED) return;
  try {
    await fetch(`${FLEET_DISPATCHER}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, server, success, duration, job_type: jobType, model, error }),
    });
  } catch (e) {}
}

const _agent = async (prompt, opts = {}) => {
  const model = opts.model || 'sonnet';
  const jobType = 'agent'; // Can enhance with job type inference
  const dispatch = await _dispatchAgent(model, prompt, jobType);
  if (!dispatch) return agent(prompt, opts);
  
  const start = Date.now();
  try {
    const result = await _agent(prompt, opts);
    _completeAgent(dispatch.job_id, dispatch.server, true, (Date.now()-start)/1000, jobType, model).catch(()=>{});
    return result;
  } catch (error) {
    _completeAgent(dispatch.job_id, dispatch.server, false, (Date.now()-start)/1000, jobType, model, error.message).catch(()=>{});
    throw error;
  }
};
// === END FLEET DISPATCHER INTEGRATION ===


import { bulkOrchestrate, mergeAndDedupFindings } from '../shared/fleet-bulk-orchestration.js';
import fs from 'fs';
import path from 'path';

// ============================================================================
// CONFIGURATION
// ============================================================================

const AUTONOMOUS = args?.autonomous === true;
const DRY_RUN = args?.dryRun === true;
const SCAN_TYPE = args?.scanType || 'all'; // 'injection', 'auth', 'crypto', 'all'
const FOCUS_ON_HIGH = args?.focusOnHigh === true; // Only report high/critical

log('');
log('='.repeat(70));
log('Bulk Code Security - Fleet Distribution');
log('='.repeat(70));
log(`Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`);
log(`Scan type: ${SCAN_TYPE}`);
log(`Focus on high/critical: ${FOCUS_ON_HIGH}`);
if (DRY_RUN) log('DRY RUN MODE');
log('');

// ============================================================================
// PHASE 1: File Discovery
// ============================================================================

phase('File Discovery');

const projectDir = process.cwd();
log(`Scanning: ${projectDir}`);

const discoveryResult = await _agent(`Discover all source files for security scanning.

Project: ${projectDir}

Find files matching these patterns:
- **/*.js, **/*.ts, **/*.tsx, **/*.jsx (JavaScript/TypeScript)
- **/*.py (Python)
- **/*.java (Java)
- **/*.go (Go)
- **/*.rs (Rust)
- **/*.php (PHP)
- **/*.c, **/*.cpp, **/*.h (C/C++)

Exclude:
- node_modules, .git, dist, build, __pycache__, target, .venv
- *.min.js, *.bundle.js (minified)
- Test fixtures and mock data

Return: { files: [{ path, language, size_bytes }], total_files, total_size_mb }`, {
  label: 'Discover Files',
  schema: {
    type: 'object',
    properties: {
      files: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            path: { type: 'string' },
            language: { type: 'string' },
            size_bytes: { type: 'number' },
          },
          required: ['path', 'language'],
        }
      },
      total_files: { type: 'number' },
      total_size_mb: { type: 'number' },
    },
    required: ['files', 'total_files']
  }
});

const sourceFiles = discoveryResult.files || [];
log(`Total files: ${sourceFiles.length}`);
log(`Total size: ${discoveryResult.total_size_mb?.toFixed(1)} MB`);

// Summarize by language
const byLanguage = {};
for (const file of sourceFiles) {
  byLanguage[file.language] = (byLanguage[file.language] || 0) + 1;
}

log('Files by language:');
Object.entries(byLanguage)
  .sort((a, b) => b[1] - a[1])
  .forEach(([lang, count]) => {
    log(`  ${lang}: ${count} files`);
  });

log('');

if (sourceFiles.length === 0) {
  return {
    status: 'error',
    message: 'No source files found to scan',
  };
}

// ============================================================================
// PHASE 2: Batch Distribution (by language + size)
// ============================================================================

phase('Batch Distribution');

// Group files by language for balanced distribution
const filesByLanguage = {};
for (const file of sourceFiles) {
  const lang = file.language || 'other';
  if (!filesByLanguage[lang]) {
    filesByLanguage[lang] = [];
  }
  filesByLanguage[lang].push(file);
}

// Sort each language group by size (largest first) for better load balancing
for (const lang in filesByLanguage) {
  filesByLanguage[lang].sort((a, b) => (b.size_bytes || 0) - (a.size_bytes || 0));
}

log(`Languages: ${Object.keys(filesByLanguage).join(', ')}`);
log('');

// ============================================================================
// PHASE 3: Bulk Orchestration
// ============================================================================

phase('Fleet Orchestration');

// Custom merge strategy for security findings
const mergeSecurityFindings = (results) => {
  const allFindings = results.flatMap(r => r.findings || []);

  // Deduplicate by file:line:type
  const deduped = mergeAndDedupFindings(
    results.map(r => ({ findings: r.findings || [] })),
    (f) => `${f.file}:${f.line || 0}:${f.type}`
  );

  // Filter by severity if configured
  const filtered = FOCUS_ON_HIGH
    ? deduped.filter(f => ['critical', 'high'].includes(f.severity))
    : deduped;

  // Sort by severity
  const severityRank = { critical: 4, high: 3, medium: 2, low: 1 };
  filtered.sort((a, b) => (severityRank[b.severity] || 0) - (severityRank[a.severity] || 0));

  return {
    findings: filtered,
    total: filtered.length,
    by_severity: {
      critical: filtered.filter(f => f.severity === 'critical').length,
      high: filtered.filter(f => f.severity === 'high').length,
      medium: filtered.filter(f => f.severity === 'medium').length,
      low: filtered.filter(f => f.severity === 'low').length,
    }
  };
};

const orchestrationResult = await bulkOrchestrate({
  skill: 'code-security-bulk',
  items: sourceFiles,
  workerScript: 'workflows/code-security.js',
  mergeStrategy: mergeSecurityFindings,
  itemSerializer: (files) => JSON.stringify({
    files,
    scanType: SCAN_TYPE,
  }),
  resultDeserializer: (stdout) => {
    try {
      return JSON.parse(stdout);
    } catch {
      return { findings: [] };
    }
  },
  log,
  fleetOptions: { capabilities: ['security-scan'] },
  minWorkers: 2,
  timeout: 600000,
  dryRun: DRY_RUN,
  useWeightedDistribution: true,
});

log('');

if (orchestrationResult.status === 'failed') {
  return {
    status: 'failed',
    message: 'All workers failed',
    filesScanned: orchestrationResult.itemsProcessed,
    totalFiles: orchestrationResult.totalItems,
    errors: orchestrationResult.errors,
  };
}

// ============================================================================
// PHASE 4: Generate Report
// ============================================================================

phase('Report Generation');

const findings = orchestrationResult.result || { findings: [], total: 0, by_severity: {} };
const totalFindings = findings.total || 0;

log(`Total findings: ${totalFindings}`);
log('By severity:');
log(`  Critical: ${findings.by_severity?.critical || 0}`);
log(`  High:     ${findings.by_severity?.high || 0}`);
log(`  Medium:   ${findings.by_severity?.medium || 0}`);
log(`  Low:      ${findings.by_severity?.low || 0}`);

// Generate human-readable report
const reportGenResult = await _agent(`Generate a security audit report from findings.

Total findings: ${totalFindings}
Critical: ${findings.by_severity?.critical || 0}
High: ${findings.by_severity?.high || 0}
Medium: ${findings.by_severity?.medium || 0}
Low: ${findings.by_severity?.low || 0}

Top findings:
${JSON.stringify(findings.findings?.slice(0, 20) || [], null, 2)}

Create a professional report with:
1. Executive summary
2. Severity breakdown
3. Top 10 findings (with file:line:details)
4. Remediation recommendations
5. Next steps

Return as markdown.`, {
  label: 'Generate Report',
  schema: {
    type: 'object',
    properties: {
      report: { type: 'string' },
    }
  }
});

log('Report generated');
log('');

// ============================================================================
// PHASE 5: Save Results
// ============================================================================

phase('Save Results');

const reportDir = path.join(projectDir, '.claude', 'bulk-reports');
if (!fs.existsSync(reportDir)) {
  fs.mkdirSync(reportDir, { recursive: true });
}

// Save markdown report
const reportFile = path.join(reportDir, `security-${Date.now()}.md`);
fs.writeFileSync(reportFile, reportGenResult.report || '');
log(`Report saved: ${reportFile}`);

// Save detailed findings JSON
const findingsFile = path.join(reportDir, `security-findings-${Date.now()}.json`);
const findingsData = {
  timestamp: new Date().toISOString(),
  totalFiles: orchestrationResult.totalItems,
  filesScanned: orchestrationResult.itemsProcessed,
  totalFindings,
  bySeverity: findings.by_severity,
  findings: findings.findings || [],
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  errors: orchestrationResult.errors,
};

fs.writeFileSync(findingsFile, JSON.stringify(findingsData, null, 2));
log(`Findings saved: ${findingsFile}`);
log('');

log('='.repeat(70));
log('BULK SECURITY SCAN COMPLETE');
log('='.repeat(70));
log(`Files scanned: ${orchestrationResult.itemsProcessed}/${orchestrationResult.totalItems}`);
log(`Findings: ${totalFindings}`);
log(`  Critical: ${findings.by_severity?.critical || 0}`);
log(`  High: ${findings.by_severity?.high || 0}`);
log(`Fleet used: ${orchestrationResult.fleetUsed ? 'YES' : 'NO'}`);
log(`Workers: ${orchestrationResult.workersUsed}`);
log('='.repeat(70));

return {
  status: orchestrationResult.status,
  totalFiles: orchestrationResult.totalItems,
  filesScanned: orchestrationResult.itemsProcessed,
  totalFindings,
  bySeverity: findings.by_severity,
  topFindings: findings.findings?.slice(0, 10) || [],
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  reportFile,
  findingsFile,
  errors: orchestrationResult.errors,
};
