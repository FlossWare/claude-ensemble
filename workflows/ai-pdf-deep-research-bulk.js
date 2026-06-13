/**
 * ai-pdf-deep-research-bulk.js
 *
 * Fleet-distributed PDF ingestion and adversarial verification.
 * Primary use case: 600 PDFs in 33 hours (3x speedup vs 100 hours sequential).
 *
 * Multi-session orchestration:
 *   - Controller: Splits 600 PDFs into 3 batches (200 each)
 *   - Worker-01: Processes PDFs 1-200 via independent Claude Code session
 *   - Worker-02: Processes PDFs 201-400 via independent Claude Code session
 *   - Worker-03: Processes PDFs 401-600 via independent Claude Code session
 *   - Controller: Merges 3 markdown reports into unified output
 *
 * Per-PDF timing:
 *   - Read PDF (chunked into 20-page ranges): 1 min
 *   - Extract claims (6 models): 4 min
 *   - Adversarial verify (3-vote): 4 min
 *   - Synthesize: 1 min
 *   - Total: ~10 min per PDF
 *   - Sequential (600 PDFs): 100 hours
 *   - Fleet (3 workers): 33 hours
 *
 * Implementation: Multi-session via bulk-orchestration framework
 */

export const meta = {
  name: 'ai-pdf-deep-research-bulk',
  description: 'Fleet-distributed PDF ingestion - 600 PDFs in ~33 hours (3x speedup)',
  whenToUse: 'When you need to ingest and verify claims from 50+ PDFs across fleet workers',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover and validate 3 fleet workers' },
    { title: 'Batch Distribution', detail: 'Split PDFs into 3 batches (200 each)' },
    { title: 'Worker Sessions', detail: 'Launch independent Claude Code sessions on each worker' },
    { title: 'PDF Processing', detail: 'Each worker processes its batch via ai-pdf-deep-research' },
    { title: 'Report Merge', detail: 'Concatenate markdown reports from all workers' },
    { title: 'Memory Integration', detail: 'Save merged findings to memory system' },
  ],
};

import { bulkOrchestrate, mergeMarkdownResults } from '../shared/fleet-bulk-orchestration.js';
import fs from 'fs';
import path from 'path';

// ============================================================================
// CONFIGURATION
// ============================================================================

const AUTONOMOUS = args?.autonomous === true;
const DRY_RUN = args?.dryRun === true;
const PDF_BATCH_SIZE = args?.batchSize || 10; // Process 10 PDFs per worker batch
const TIMEOUT_PER_BATCH = args?.timeout || 600000; // 10 min per PDF batch

log('');
log('='.repeat(70));
log('Bulk PDF Deep Research - Fleet Distribution');
log('='.repeat(70));
log(`Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`);
if (DRY_RUN) log('DRY RUN MODE');
log('');

// ============================================================================
// PHASE 1: Input Validation and PDF Discovery
// ============================================================================

phase('Input Validation');

// PDFs can come from:
// 1. args.pdfs - JSON array of paths
// 2. args.pdfDir - Directory containing PDFs
// 3. args.pdfPattern - Glob pattern to find PDFs

let pdfPaths = [];

if (args?.pdfs && Array.isArray(args.pdfs)) {
  pdfPaths = args.pdfs;
  log(`Using ${pdfPaths.length} PDFs from args.pdfs`);
} else if (args?.pdfDir) {
  pdfPaths = await _agent(`Discover all PDF files in directory.

Directory: ${args.pdfDir}

Execute: find '${args.pdfDir}' -type f -name '*.pdf' | sort

Return array of full paths.`, {
    label: 'Discover PDFs',
    schema: {
      type: 'object',
      properties: {
        pdf_paths: { type: 'array', items: { type: 'string' } },
      },
      required: ['pdf_paths']
    }
  }).then(r => r.pdf_paths);
  log(`Discovered ${pdfPaths.length} PDFs in ${args.pdfDir}`);
} else if (args?.pdfPattern) {
  // User provides glob pattern (e.g., "~/Documents/*.pdf")
  const globResult = await _agent(`Expand glob pattern to PDF paths.

Pattern: ${args.pdfPattern}

Execute: cd ~ && find . -name '${args.pdfPattern.split('/').pop()}' -type f | sort

Return array of full paths.`, {
    label: 'Expand Pattern',
    schema: {
      type: 'object',
      properties: {
        pdf_paths: { type: 'array', items: { type: 'string' } },
      },
      required: ['pdf_paths']
    }
  }).then(r => r.pdf_paths);
  pdfPaths = globResult;
  log(`Pattern matched ${pdfPaths.length} PDFs`);
} else {
  return {
    status: 'error',
    message: 'No PDFs specified. Provide args.pdfs, args.pdfDir, or args.pdfPattern',
    examples: {
      'Array of paths': { pdfs: ['/path/to/doc1.pdf', '/path/to/doc2.pdf'] },
      'Directory': { pdfDir: '/home/user/Documents/research' },
      'Glob pattern': { pdfPattern: '**/*.pdf' },
    }
  };
}

if (pdfPaths.length === 0) {
  return {
    status: 'error',
    message: 'No PDFs found matching the specified criteria',
    pdfsSpecified: pdfPaths.length,
  };
}

log(`Total PDFs to process: ${pdfPaths.length}`);
log('');

// ============================================================================
// PHASE 2: Validate PDFs exist and are readable
// ============================================================================

phase('PDF Validation');

const validationResult = await _agent(`Validate that PDF files exist and are readable.

PDFs to check: ${pdfPaths.slice(0, 5).join(', ')}${pdfPaths.length > 5 ? ` ... (${pdfPaths.length - 5} more)` : ''}

Execute: for f in ${pdfPaths.map(p => `'${p}'`).join(' ')}; do [ -f "$f" ] && [ -r "$f" ] && echo "OK: $f" || echo "FAIL: $f"; done 2>&1

Return validation status for each PDF.`, {
  label: 'Validate PDFs',
  schema: {
    type: 'object',
    properties: {
      valid_pdfs: { type: 'array', items: { type: 'string' } },
      invalid_pdfs: { type: 'array', items: { type: 'string' } },
    }
  }
});

const validPdfs = validationResult.valid_pdfs || pdfPaths;
const invalidPdfs = validationResult.invalid_pdfs || [];

if (invalidPdfs.length > 0) {
  log(`Warning: ${invalidPdfs.length} PDFs are not readable`);
  invalidPdfs.slice(0, 5).forEach(p => log(`  - ${p}`));
  pdfPaths = validPdfs;
}

log(`Valid PDFs: ${pdfPaths.length}`);
log('');

// ============================================================================
// PHASE 3: Bulk Orchestration
// ============================================================================

phase('Fleet Orchestration');

const orchestrationResult = await bulkOrchestrate({
  skill: 'ai-pdf-deep-research-bulk',
  items: pdfPaths,
  workerScript: 'workflows/ai-pdf-deep-research.js',
  mergeStrategy: mergeMarkdownResults,
  itemSerializer: (pdfs) => JSON.stringify(pdfs),
  resultDeserializer: (stdout) => {
    try {
      return JSON.parse(stdout);
    } catch {
      // If not JSON, assume it's markdown output
      return { markdown: stdout };
    }
  },
  log,
  fleetOptions: { capabilities: ['pdf-processing'] },
  minWorkers: 2,
  timeout: TIMEOUT_PER_BATCH,
  dryRun: DRY_RUN,
  useWeightedDistribution: true, // Distribute by worker memory
});

log('');

if (orchestrationResult.status === 'failed') {
  return {
    status: 'failed',
    message: 'All workers failed',
    pdfsProcessed: orchestrationResult.itemsProcessed,
    totalPdfs: orchestrationResult.totalItems,
    errors: orchestrationResult.errors,
  };
}

// ============================================================================
// PHASE 4: Save Results
// ============================================================================

phase('Save Results');

// Save merged report
const reportDir = path.join(process.cwd(), '.claude', 'bulk-reports');
if (!fs.existsSync(reportDir)) {
  fs.mkdirSync(reportDir, { recursive: true });
}

const reportFile = path.join(reportDir, `pdf-research-${Date.now()}.md`);
const report = orchestrationResult.result || '';

fs.writeFileSync(reportFile, report);
log(`Report saved: ${reportFile}`);

// Save worker results index
const indexFile = path.join(reportDir, `pdf-research-${Date.now()}.json`);
const index = {
  timestamp: new Date().toISOString(),
  totalPdfs: orchestrationResult.totalItems,
  processedPdfs: orchestrationResult.itemsProcessed,
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  status: orchestrationResult.status,
  reportFile,
  errors: orchestrationResult.errors,
};

fs.writeFileSync(indexFile, JSON.stringify(index, null, 2));
log(`Index saved: ${indexFile}`);
log('');

// ============================================================================
// PHASE 5: Memory Integration (if applicable)
// ============================================================================

if (args?.saveToMemory) {
  phase('Memory Integration');

  log('Saving findings to memory system...');

  const memoryResult = await _agent(`Extract key findings from the PDF research report and save to memory.

Report:
${report.slice(0, 5000)}${report.length > 5000 ? '\n...\n(truncated)' : ''}

Categories to extract:
- Key facts and statistics
- Novel insights
- Notable claims and supporting evidence
- Recommendations

Save as structured knowledge in the memory system.`, {
    label: 'Memory Integration',
    schema: {
      type: 'object',
      properties: {
        findings_saved: { type: 'number' },
        categories: { type: 'array', items: { type: 'string' } },
      }
    }
  });

  log(`Saved ${memoryResult.findings_saved} findings to memory`);
}

log('');
log('='.repeat(70));
log('BULK PDF RESEARCH COMPLETE');
log('='.repeat(70));
log(`PDFs processed: ${orchestrationResult.itemsProcessed}/${orchestrationResult.totalItems}`);
log(`Report: ${reportFile}`);
log(`Fleet used: ${orchestrationResult.fleetUsed ? 'YES' : 'NO'}`);
log(`Workers: ${orchestrationResult.workersUsed}`);
log('='.repeat(70));

return {
  status: orchestrationResult.status,
  totalPdfs: orchestrationResult.totalItems,
  processedPdfs: orchestrationResult.itemsProcessed,
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  reportFile,
  indexFile,
  errors: orchestrationResult.errors,
};
