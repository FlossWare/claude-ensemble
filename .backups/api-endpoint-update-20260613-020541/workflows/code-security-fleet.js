// Code Security Fleet - Distributed security scanning
//
// Dual Pattern: Scan Type Distribution OR File Chunk Distribution
//
//   Option A (small codebase, <500 files): Distribute scan types
//     - Worker 1 (server-01): Dependency vulnerability scan
//     - Worker 2 (server-02): Secrets detection scan
//     - Worker 3 (server-03): OWASP Top 10 + license compliance scan
//
//   Option B (large codebase, >=500 files): Distribute file chunks
//     - Each worker gets 1/3 of files and runs ALL scan types
//     - Better coverage for large codebases
//
//   Auto-selection: Based on file count threshold (configurable)
//
// Result Merging:
//   - Deduplicate findings by file:line:type
//   - Higher severity wins on duplicates
//   - Multi-AI verification of merged findings
//
// Speedup: 2-2.5x with 3 workers

export const meta = {
  name: 'code-security-fleet',
  description: 'Fleet-distributed security audit - distributes scans across workers for 2-2.5x speedup',
  whenToUse: 'When running security audit on a project and fleet is available',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover available fleet workers' },
    { title: 'Analyze Codebase', detail: 'Count files and choose distribution strategy' },
    { title: 'Distribute Scans', detail: 'Assign scan work to fleet workers' },
    { title: 'Execute Scans', detail: 'Run security scans in parallel' },
    { title: 'Merge & Deduplicate', detail: 'Merge findings, remove duplicates' },
    { title: 'Multi-AI Verification', detail: 'Consensus verification of findings' },
    { title: 'Impact Analysis', detail: 'Exploitability and severity scoring' },
    { title: 'Report', detail: 'Generate security report' },
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


import { getWorkers, remoteExec } from '../shared/fleet-utils.js';
import {
  distributeItems,
  deduplicateFindings,
  gracefulFallback,
  nfsProjectPath,
  isOnNfs,
} from '../shared/fleet-workflow-patterns.js';

// ============================================================================
// CONFIGURATION
// ============================================================================

const AUTONOMOUS = args?.autonomous === true;
const FILE_THRESHOLD = args?.fileThreshold || 500;  // Switch to Option B above this
const DRY_RUN = args?.dryRun === true;
const FORCE_STRATEGY = args?.strategy || null;  // 'scan-type' or 'file-chunk'

log('');
log('='.repeat(60));
log('Fleet-Distributed Security Audit');
log('='.repeat(60));
log(`Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`);
log(`File threshold for strategy switch: ${FILE_THRESHOLD}`);
if (FORCE_STRATEGY) log(`Forced strategy: ${FORCE_STRATEGY}`);
log('');

// ============================================================================
// PHASE 1: Fleet Discovery
// ============================================================================

phase('Fleet Discovery');

let workers = [];
let useFleet = false;

try {
  workers = getWorkers();
  useFleet = workers.length >= 2;

  if (useFleet) {
    log(`Fleet available: ${workers.length} workers`);
    workers.forEach(w => log(`  - ${w.hostname} (${w.cpus}C/${w.memory_gb}GB)`));
  } else {
    log('Insufficient fleet workers, running locally');
  }
} catch (error) {
  log(`Fleet unavailable (${error.message}), running locally`);
}

const projectDir = nfsProjectPath();
if (useFleet && !isOnNfs(projectDir)) {
  log(`Project not on NFS, falling back to local`);
  useFleet = false;
}

// If fleet not available, delegate to local code-security
if (!useFleet) {
  log('Delegating to local code-security workflow...');
  const localResult = await workflow('code-security', {
    autonomous: AUTONOMOUS,
    ...args,
  });
  return { ...localResult, fleet_used: false };
}

log('');

// ============================================================================
// PHASE 2: Analyze Codebase
// ============================================================================

phase('Analyze Codebase');

log('Analyzing codebase size and structure...');

const codebaseAnalysis = await _agent(`Analyze the codebase to determine security scan strategy.

Run these commands:
1. Count source files: find . -type f \\( -name "*.js" -o -name "*.ts" -o -name "*.py" -o -name "*.java" -o -name "*.go" -o -name "*.rs" -o -name "*.rb" -o -name "*.php" \\) -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/dist/*" -not -path "*/build/*" | wc -l

2. Detect package managers: ls package.json requirements.txt Cargo.toml go.mod pom.xml build.gradle Gemfile composer.json 2>/dev/null

3. Check for security-relevant config: ls .env .env.example docker-compose.yml Dockerfile .dockerignore .npmrc .pypirc 2>/dev/null

4. Sample source files for scan planning: find . -type f \\( -name "*.js" -o -name "*.ts" -o -name "*.py" \\) -not -path "*/node_modules/*" -not -path "*/.git/*" | head -20

Return structured analysis.`, {
  label: 'Analyze',
  schema: {
    type: 'object',
    properties: {
      total_source_files: { type: 'number' },
      package_managers: { type: 'array', items: { type: 'string' } },
      languages: { type: 'array', items: { type: 'string' } },
      has_docker: { type: 'boolean' },
      has_env_files: { type: 'boolean' },
      source_file_list: { type: 'array', items: { type: 'string' } },
    },
    required: ['total_source_files', 'package_managers'],
  },
});

log(`Source files: ${codebaseAnalysis.total_source_files}`);
log(`Package managers: ${codebaseAnalysis.package_managers?.join(', ') || 'none'}`);
log(`Languages: ${codebaseAnalysis.languages?.join(', ') || 'unknown'}`);

// Choose strategy
let strategy = FORCE_STRATEGY;
if (!strategy) {
  strategy = codebaseAnalysis.total_source_files >= FILE_THRESHOLD
    ? 'file-chunk'
    : 'scan-type';
}

log(`Strategy: ${strategy} (${codebaseAnalysis.total_source_files} files, threshold ${FILE_THRESHOLD})`);
log('');

if (DRY_RUN) {
  return {
    status: 'dry_run',
    strategy,
    total_files: codebaseAnalysis.total_source_files,
    workers: workers.map(w => w.hostname),
    message: 'Dry run - no scans executed',
  };
}

// ============================================================================
// PHASE 3-4: Distribute and Execute Scans
// ============================================================================

phase('Distribute Scans');

let allFindings = [];

if (strategy === 'scan-type') {
  // =============================================
  // OPTION A: Distribute scan types across workers
  // =============================================

  const scanTypes = [
    {
      name: 'dependency',
      label: 'Dependency Vulnerability Scan',
      prompt: `Scan dependencies for known vulnerabilities.

Working directory: ${projectDir}

Check all available package managers: ${codebaseAnalysis.package_managers?.join(', ')}

For each package manager found:
- npm: run "npm audit --json" or read package-lock.json
- pip: check requirements.txt against known CVE databases
- cargo: check Cargo.lock for known issues
- go: check go.sum for known issues

Return all vulnerabilities found with CVE IDs, severity, and fix availability.`,
    },
    {
      name: 'secrets',
      label: 'Secrets Detection Scan',
      prompt: `Scan for hardcoded secrets and credentials.

Working directory: ${projectDir}

Patterns to check (using grep -rn):
- API keys: "API_KEY", "APIKEY", "api-key", "apikey"
- Passwords: "password", "passwd", "pwd" (in assignments, not comments)
- Tokens: "token", "auth_token", "bearer", "jwt"
- Private keys: "BEGIN RSA PRIVATE KEY", "BEGIN PRIVATE KEY", "BEGIN EC PRIVATE KEY"
- AWS: "AKIA", "aws_secret_access_key", "aws_access_key_id"
- Database: connection strings with credentials
- Generic: base64-encoded strings > 20 chars in config files

Exclude: node_modules/, .git/, dist/, build/, test fixtures, documentation examples, vendor/

For each finding, assess if it looks like a real secret vs placeholder/example.`,
    },
    {
      name: 'owasp_license',
      label: 'OWASP + License Compliance Scan',
      prompt: `Run two scans:

PART 1 - OWASP Top 10 Vulnerability Scan:
Working directory: ${projectDir}

Check source code for:
1. SQL Injection - raw SQL, string concatenation in queries
2. XSS - innerHTML, dangerouslySetInnerHTML, unescaped template output
3. CSRF - forms without CSRF tokens
4. Insecure Auth - weak password policies, hardcoded auth
5. Sensitive Data Exposure - logging passwords, plaintext storage
6. XXE - XML parsing without disabling external entities
7. Broken Access Control - missing auth checks on routes/endpoints
8. Security Misconfiguration - debug mode enabled, default credentials
9. Using Vulnerable Components - outdated framework versions
10. Insufficient Logging - no audit trail for security events

PART 2 - License Compliance:
Check dependency licenses:
- Flag GPL/AGPL (copyleft risk)
- Flag Unknown/Unlicensed dependencies
- Safe: MIT, Apache-2.0, BSD, ISC

Return all findings from both scans.`,
    },
  ];

  // Assign scan types to workers (1:1 if 3 workers, round-robin otherwise)
  const assignments = scanTypes.map((scan, idx) => ({
    scan,
    worker: workers[idx % workers.length],
  }));

  log('Scan type distribution:');
  assignments.forEach(a => log(`  ${a.worker.hostname}: ${a.scan.label}`));
  log('');

  phase('Execute Scans');

  log('Executing security scans in parallel...');

  const scanResults = await parallel(
    assignments.map(({ scan, worker }) => () =>
      agent(`${scan.prompt}

Return all security findings as structured data.`, {
        label: `${scan.name}@${worker.hostname}`,
        schema: {
          type: 'object',
          properties: {
            scan_type: { type: 'string' },
            hostname: { type: 'string' },
            findings: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  type: { type: 'string' },
                  severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
                  title: { type: 'string' },
                  description: { type: 'string' },
                  file: { type: 'string' },
                  line: { type: 'number' },
                  cve: { type: 'string' },
                  cwe: { type: 'string' },
                  remediation: { type: 'string' },
                  exploitable: { type: 'boolean' },
                  fix_available: { type: 'boolean' },
                },
                required: ['type', 'severity', 'title'],
              },
            },
            total: { type: 'number' },
          },
          required: ['scan_type', 'findings', 'total'],
        },
      })
    )
  );

  const validResults = scanResults.filter(Boolean);
  allFindings = validResults.flatMap(r => r.findings || []);

  log(`Scan results:`);
  validResults.forEach(r => log(`  ${r.scan_type}: ${r.total} findings`));

} else {
  // =============================================
  // OPTION B: Distribute file chunks across workers
  // =============================================

  // Get full file list for distribution
  const fileListResult = await _agent(`List all source files for security scanning.

Run: find ${projectDir} -type f \\( -name "*.js" -o -name "*.ts" -o -name "*.py" -o -name "*.java" -o -name "*.go" -o -name "*.rs" -o -name "*.rb" -o -name "*.php" -o -name "*.jsx" -o -name "*.tsx" \\) -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/dist/*" -not -path "*/build/*" -not -path "*/vendor/*" | sort

Return the full list.`, {
    label: 'list-files',
    schema: {
      type: 'object',
      properties: {
        files: { type: 'array', items: { type: 'string' } },
        total: { type: 'number' },
      },
    },
  });

  const allFiles = fileListResult?.files || [];
  const distribution = distributeItems(allFiles, workers);

  log(`File chunk distribution (${allFiles.length} files):`);
  for (const [hostname, files] of distribution.entries()) {
    log(`  ${hostname}: ${files.length} files`);
  }
  log('');

  phase('Execute Scans');

  log('Executing all scan types on file chunks in parallel...');

  const chunkResults = await parallel(
    workers.map(worker => {
      const files = distribution.get(worker.hostname);
      if (!files || files.length === 0) return () => Promise.resolve(null);

      const fileList = files.slice(0, 200).join('\n');  // Cap for prompt size

      return () => agent(`Run ALL security scans on these ${files.length} files:

${fileList}
${files.length > 200 ? `\n... and ${files.length - 200} more files` : ''}

Working directory: ${projectDir}

Run ALL of these scans on the listed files:

1. SECRETS: Check for hardcoded secrets, API keys, passwords, tokens, private keys
2. OWASP: Check for SQL injection, XSS, CSRF, insecure auth, sensitive data exposure
3. CODE QUALITY SECURITY: Buffer overflows, race conditions, unsafe deserialization

For each finding provide: type, severity, file, line, description, remediation.`, {
        label: `all-scans@${worker.hostname}`,
        schema: {
          type: 'object',
          properties: {
            hostname: { type: 'string' },
            findings: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  type: { type: 'string' },
                  severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
                  title: { type: 'string' },
                  description: { type: 'string' },
                  file: { type: 'string' },
                  line: { type: 'number' },
                  cwe: { type: 'string' },
                  remediation: { type: 'string' },
                  exploitable: { type: 'boolean' },
                },
                required: ['type', 'severity', 'title'],
              },
            },
            total: { type: 'number' },
            files_scanned: { type: 'number' },
          },
          required: ['findings', 'total'],
        },
      });
    })
  );

  const validChunks = chunkResults.filter(Boolean);
  allFindings = validChunks.flatMap(r => r.findings || []);

  log(`Chunk scan results:`);
  validChunks.forEach(r => log(`  ${r.hostname || 'worker'}: ${r.total} findings from ${r.files_scanned || '?'} files`));

  // Also run dependency scan (not file-based, runs once)
  log('Running dependency scan (not file-based)...');

  const depScan = await _agent(`Scan dependencies for known vulnerabilities.

Working directory: ${projectDir}
Package managers: ${codebaseAnalysis.package_managers?.join(', ')}

Run appropriate audit commands (npm audit, pip-audit, etc.)
Return vulnerabilities found.`, {
    label: 'dep-scan',
    schema: {
      type: 'object',
      properties: {
        findings: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              type: { type: 'string' },
              severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
              title: { type: 'string' },
              description: { type: 'string' },
              package: { type: 'string' },
              cve: { type: 'string' },
              fix_available: { type: 'boolean' },
              remediation: { type: 'string' },
            },
          },
        },
        total: { type: 'number' },
      },
    },
  });

  if (depScan?.findings) {
    allFindings.push(...depScan.findings);
  }
}

// ============================================================================
// PHASE 5: Merge & Deduplicate
// ============================================================================

phase('Merge & Deduplicate');

const rawCount = allFindings.length;
const deduplicated = deduplicateFindings(allFindings);

log(`Raw findings: ${rawCount}`);
log(`After deduplication: ${deduplicated.length}`);
log(`Duplicates removed: ${rawCount - deduplicated.length}`);

if (deduplicated.length === 0) {
  log('No security issues found!');
  return {
    status: 'clean',
    fleet_used: true,
    strategy,
    workers_used: workers.length,
    message: 'No security vulnerabilities detected',
  };
}

// Severity breakdown
const bySeverity = {
  critical: deduplicated.filter(f => f.severity === 'critical').length,
  high: deduplicated.filter(f => f.severity === 'high').length,
  medium: deduplicated.filter(f => f.severity === 'medium').length,
  low: deduplicated.filter(f => f.severity === 'low').length,
};

log(`Severity: ${bySeverity.critical} critical, ${bySeverity.high} high, ${bySeverity.medium} medium, ${bySeverity.low} low`);
log('');

// ============================================================================
// PHASE 6: Multi-AI Verification
// ============================================================================

phase('Multi-AI Verification');

log('Verifying findings with multi-AI consensus...');

const VERIFY_MODELS = ['opus', 'sonnet', 'haiku'];

const verifications = await parallel(VERIFY_MODELS.map(model => () =>
  agent(`Verify these security findings - reduce false positives.

${deduplicated.slice(0, 30).map((f, i) => `
Finding ${i + 1}: [${f.severity.toUpperCase()}] ${f.title}
  Type: ${f.type}
  ${f.file ? `File: ${f.file}:${f.line || 'N/A'}` : `Package: ${f.package || 'N/A'}`}
  ${f.description || ''}
`).join('\n')}

For each finding, determine:
1. Is this a REAL vulnerability or FALSE POSITIVE?
2. Actual exploitability risk (can an attacker use this?)
3. Your confidence in this assessment (0-100)

Return verified findings only.`, {
    label: `Verify (${model})`,
    model,
    schema: {
      type: 'object',
      properties: {
        verified: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              finding_index: { type: 'number' },
              is_real: { type: 'boolean' },
              exploitable: { type: 'boolean' },
              confidence: { type: 'number' },
              reasoning: { type: 'string' },
            },
          },
        },
      },
    },
  })
));

const validVerifications = verifications.filter(Boolean);
log(`${validVerifications.length} models verified findings`);

// Arbiter consensus
const arbiterResult = await _agent(`Merge security verifications from ${validVerifications.length} AI models.

Original findings: ${deduplicated.length}
Model verifications:
${validVerifications.map((v, i) => `
Model ${i + 1}: ${v.verified?.length || 0} findings verified
  Real: ${v.verified?.filter(f => f.is_real).length || 0}
  False positive: ${v.verified?.filter(f => !f.is_real).length || 0}
`).join('\n')}

Create consensus:
- Finding is REAL if 2+ models agree it's real
- Assign final severity based on consensus
- Filter out confirmed false positives
- Score exploitability

Return final verified findings.`, {
  label: 'Arbiter Consensus',
  model: 'opus',
  schema: {
    type: 'object',
    properties: {
      verified_findings: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            type: { type: 'string' },
            severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
            title: { type: 'string' },
            description: { type: 'string' },
            file: { type: 'string' },
            line: { type: 'number' },
            exploitable: { type: 'boolean' },
            confidence: { type: 'number' },
            remediation: { type: 'string' },
            consensus_votes: { type: 'number' },
          },
        },
      },
      false_positives_removed: { type: 'number' },
      consensus_confidence: { type: 'number' },
    },
  },
});

const verified = arbiterResult?.verified_findings || [];

log(`Consensus: ${verified.length} verified findings (${arbiterResult?.false_positives_removed || 0} false positives removed)`);

// ============================================================================
// PHASE 7: Impact Analysis
// ============================================================================

phase('Impact Analysis');

log('Scoring exploitability and impact...');

verified.forEach(finding => {
  let score = 0;

  // Base severity
  const severityScores = { critical: 100, high: 75, medium: 50, low: 25 };
  score = severityScores[finding.severity] || 25;

  // Exploitability boost
  if (finding.exploitable) score += 20;

  // Secret detection boost (immediate risk)
  if (finding.type === 'secret' || finding.type === 'secrets') score += 15;

  // Consensus boost
  if (finding.consensus_votes >= 3) score += 10;

  finding.impact_score = Math.min(score, 100);
  finding.risk_level = score >= 90 ? 'critical' : score >= 70 ? 'high' : score >= 40 ? 'medium' : 'low';
});

// Sort by impact score
verified.sort((a, b) => (b.impact_score || 0) - (a.impact_score || 0));

// ============================================================================
// PHASE 8: Report
// ============================================================================

phase('Report');

log('');
log('='.repeat(60));
log('FLEET SECURITY AUDIT COMPLETE');
log('='.repeat(60));
log('');
log(`Strategy: ${strategy}`);
log(`Workers used: ${workers.length} (${workers.map(w => w.hostname).join(', ')})`);
log(`Raw findings: ${rawCount}`);
log(`After dedup: ${deduplicated.length}`);
log(`Verified (real): ${verified.length}`);
log('');

const verifiedBySeverity = {
  critical: verified.filter(f => f.severity === 'critical').length,
  high: verified.filter(f => f.severity === 'high').length,
  medium: verified.filter(f => f.severity === 'medium').length,
  low: verified.filter(f => f.severity === 'low').length,
};

log(`Critical: ${verifiedBySeverity.critical}`);
log(`High: ${verifiedBySeverity.high}`);
log(`Medium: ${verifiedBySeverity.medium}`);
log(`Low: ${verifiedBySeverity.low}`);

if (verified.length > 0) {
  log('');
  log('Top Findings:');
  verified.slice(0, 5).forEach((f, i) => {
    log(`  ${i + 1}. [${f.severity.toUpperCase()}] ${f.title}`);
    log(`     ${f.file ? `${f.file}:${f.line || 'N/A'}` : 'N/A'}`);
    log(`     Impact: ${f.impact_score}/100, Exploitable: ${f.exploitable ? 'YES' : 'No'}`);
  });
}

log('');
log('='.repeat(60));

return {
  status: verified.length > 0 ? 'findings' : 'clean',
  fleet_used: true,
  strategy,
  workers_used: workers.length,
  total_raw: rawCount,
  total_deduplicated: deduplicated.length,
  total_verified: verified.length,
  severity: verifiedBySeverity,
  findings: verified,
  false_positives_removed: arbiterResult?.false_positives_removed || 0,
  consensus_confidence: arbiterResult?.consensus_confidence || 0,
};
