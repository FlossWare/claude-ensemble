/**
 * code-doc-bulk.js
 *
 * Fleet-distributed documentation generation for large codebases.
 * Use case: Generate docs for 500+ source files in parallel.
 *
 * Multi-session orchestration:
 *   - Controller: Discovers all source files
 *   - Splits files into 3 batches
 *   - Worker-01-03: Generate docs for files via independent session
 *   - Workers call code-doc for their file batch
 *   - Workers output markdown documentation files
 *   - Controller collects docs and generates index
 *
 * Per-file timing:
 *   - AST parse: 1s
 *   - Multi-model doc generation: 5-10s
 *   - Write markdown file: 1s
 *   - Total: ~20s per file
 *   - Sequential (500 files): 166 minutes
 *   - Fleet (3 workers): 55 minutes
 *
 * Output structure:
 *   - Original: src/utils/helpers.js
 *   - Docs: docs/src/utils/helpers.md
 *   - Index: docs/INDEX.md (auto-generated TOC)
 *
 * Integration:
 *   - Generate comprehensive API docs
 *   - Create function/class reference
 *   - Auto-update with each deployment
 */

export const meta = {
  name: 'code-doc-bulk',
  description: 'Fleet-distributed documentation - generate docs for 500+ files in parallel',
  whenToUse: 'When you need to generate or update API documentation for a large codebase',
  phases: [
    { title: 'Fleet Discovery', detail: 'Discover available fleet workers' },
    { title: 'File Discovery', detail: 'Find all source files needing documentation' },
    { title: 'Batch Distribution', detail: 'Split files across workers' },
    { title: 'Parallel Doc Generation', detail: 'Each worker generates docs for its files' },
    { title: 'Index Generation', detail: 'Create table of contents and cross-links' },
    { title: 'Doc Validation', detail: 'Verify markdown quality and completeness' },
  ],
};

import { bulkOrchestrate } from '../shared/fleet-bulk-orchestration.js';
import fs from 'fs';
import path from 'path';

// ============================================================================
// CONFIGURATION
// ============================================================================

const AUTONOMOUS = args?.autonomous === true;
const DRY_RUN = args?.dryRun === true;
const DOC_STYLE = args?.style || 'jsdoc'; // 'jsdoc', 'sphinx', 'doxygen', 'markdown'
const OUTPUT_DIR = args?.outputDir || 'docs';
const GENERATE_README = args?.generateReadme !== false; // Default: true
const GENERATE_INDEX = args?.generateIndex !== false; // Default: true

log('');
log('='.repeat(70));
log('Bulk Code Documentation - Fleet Distribution');
log('='.repeat(70));
log(`Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`);
log(`Style: ${DOC_STYLE}`);
log(`Output: ${OUTPUT_DIR}`);
if (DRY_RUN) log('DRY RUN MODE');
log('');

// ============================================================================
// PHASE 1: File Discovery
// ============================================================================

phase('File Discovery');

const projectDir = process.cwd();
log(`Project: ${projectDir}`);

const discoveryResult = await _agent(`Discover all source files that need documentation.

Project: ${projectDir}

Find source files:
- **/*.js, **/*.ts, **/*.tsx, **/*.jsx (JavaScript/TypeScript)
- **/*.py (Python)
- **/*.java (Java)
- **/*.go (Go)
- **/*.rs (Rust)
- **/*.c, **/*.cpp, **/*.h (C/C++)

Exclude:
- node_modules, .git, dist, build, __pycache__, target
- *.test.*, *.spec.* (test files)
- *.min.js (minified)
- Internal/private modules

For each file, return: { path, language, has_comments, lines_of_code }`, {
  label: 'Discover Source Files',
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
            has_comments: { type: 'boolean' },
            lines_of_code: { type: 'number' },
          },
          required: ['path', 'language'],
        }
      },
      total_files: { type: 'number' },
      total_loc: { type: 'number' },
    },
    required: ['files', 'total_files']
  }
});

const sourceFiles = discoveryResult.files || [];
log(`Total files: ${sourceFiles.length}`);
log(`Total lines of code: ${discoveryResult.total_loc || 0}`);

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
    message: 'No source files found',
  };
}

// ============================================================================
// PHASE 2: Bulk Orchestration
// ============================================================================

phase('Fleet Orchestration');

// Custom merge for documentation
const mergeDocumentation = (results) => {
  const docFilesByPath = new Map();

  for (const result of results) {
    const docs = result.documentation || [];
    for (const doc of docs) {
      docFilesByPath.set(doc.source_file, doc);
    }
  }

  return {
    documentation: Array.from(docFilesByPath.values()),
    total_files: docFilesByPath.size,
  };
};

const orchestrationResult = await bulkOrchestrate({
  skill: 'code-doc-bulk',
  items: sourceFiles,
  workerScript: 'workflows/code-doc.js',
  mergeStrategy: mergeDocumentation,
  itemSerializer: (files) => JSON.stringify({
    files,
    style: DOC_STYLE,
  }),
  resultDeserializer: (stdout) => {
    try {
      return JSON.parse(stdout);
    } catch {
      return { documentation: [] };
    }
  },
  log,
  fleetOptions: { capabilities: ['doc-generation'] },
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
    filesDocumented: orchestrationResult.itemsProcessed,
    totalFiles: orchestrationResult.totalItems,
    errors: orchestrationResult.errors,
  };
}

// ============================================================================
// PHASE 3: Write Documentation Files
// ============================================================================

phase('Write Documentation Files');

const docData = orchestrationResult.result || { documentation: [], total_files: 0 };
const docsToWrite = docData.documentation || [];

log(`Writing ${docsToWrite.length} documentation files to ${OUTPUT_DIR}...`);

// Create output directory
const outputPath = path.join(projectDir, OUTPUT_DIR);
if (!fs.existsSync(outputPath)) {
  fs.mkdirSync(outputPath, { recursive: true });
}

const writtenFiles = [];
let writeFailed = 0;

for (const doc of docsToWrite) {
  try {
    const sourceFile = doc.source_file;
    const content = doc.markdown || doc.content || '';

    // Map source path to doc path
    // src/utils/helpers.js -> docs/src/utils/helpers.md
    const relativeSourcePath = sourceFile.startsWith(projectDir)
      ? path.relative(projectDir, sourceFile)
      : sourceFile;

    const docPath = path.join(
      outputPath,
      relativeSourcePath.replace(/\.[^.]+$/, '.md')
    );

    // Ensure directory exists
    const docDir = path.dirname(docPath);
    if (!fs.existsSync(docDir)) {
      fs.mkdirSync(docDir, { recursive: true });
    }

    // Write file
    fs.writeFileSync(docPath, content);
    writtenFiles.push({ source: sourceFile, doc: docPath });

  } catch (error) {
    log(`  Failed to write ${doc.source_file}: ${error.message}`);
    writeFailed++;
  }
}

log(`Wrote ${writtenFiles.length} documentation files`);
if (writeFailed > 0) {
  log(`Failed: ${writeFailed}`);
}
log('');

// ============================================================================
// PHASE 4: Generate Index
// ============================================================================

phase('Generate Index');

if (GENERATE_INDEX) {
  log('Generating documentation index...');

  // Organize files by language and path
  const filesByLanguage = {};
  for (const { source } of writtenFiles) {
    const language = source.split('.').pop();
    if (!filesByLanguage[language]) {
      filesByLanguage[language] = [];
    }
    filesByLanguage[language].push(source);
  }

  const indexContent = await _agent(`Generate a markdown table of contents for API documentation.

Total files: ${writtenFiles.length}
Files by language:
${Object.entries(filesByLanguage).map(([lang, files]) => `- ${lang}: ${files.length}`).join('\n')}

Sample file structure:
${writtenFiles.slice(0, 10).map(w => `- ${w.source}`).join('\n')}

Create a professional index with:
1. Table of contents organized by language/module
2. Quick links to major APIs
3. Usage guide for documentation structure
4. Cross-reference examples

Return as markdown.`, {
    label: 'Generate Index',
    schema: {
      type: 'object',
      properties: {
        index: { type: 'string' },
      }
    }
  });

  const indexFile = path.join(outputPath, 'INDEX.md');
  fs.writeFileSync(indexFile, indexContent.index || '');
  log(`Index generated: ${indexFile}`);
} else {
  log('Skipping index generation');
}

log('');

// ============================================================================
// PHASE 5: Generate README
// ============================================================================

if (GENERATE_README) {
  phase('Generate README');

  log('Generating documentation README...');

  const readmeContent = await _agent(`Generate a README for the API documentation.

Documentation generated for ${writtenFiles.length} files.
Language distribution:
${Object.entries(byLanguage).map(([lang, count]) => `- ${lang}: ${count}`).join('\n')}

Create a README that explains:
1. What documentation is available
2. How to navigate the docs
3. How to contribute/update docs
4. Build process (if auto-generated)
5. Links to main docs

Return as markdown.`, {
    label: 'Generate README',
    schema: {
      type: 'object',
      properties: {
        readme: { type: 'string' },
      }
    }
  });

  const readmeFile = path.join(outputPath, 'README.md');
  fs.writeFileSync(readmeFile, readmeContent.readme || '');
  log(`README generated: ${readmeFile}`);
} else {
  log('Skipping README generation');
}

log('');

// ============================================================================
// PHASE 6: Validation
// ============================================================================

phase('Validation');

log('Validating documentation quality...');

const validationResult = await _agent(`Validate the generated documentation.

Check:
1. All markdown files are valid (proper syntax)
2. No empty documentation files
3. Links and cross-references work
4. Metadata completeness

Total files: ${writtenFiles.length}

Return: { valid_files: number, issues: [...], coverage_percentage: number }`, {
  label: 'Validate Docs',
  schema: {
    type: 'object',
    properties: {
      valid_files: { type: 'number' },
      issues: { type: 'array' },
      coverage_percentage: { type: 'number' },
    }
  }
});

log(`Validation: ${validationResult.valid_files}/${writtenFiles.length} files valid`);
log(`Coverage: ${validationResult.coverage_percentage || 0}%`);
if (validationResult.issues?.length > 0) {
  log(`Issues: ${validationResult.issues.length}`);
  validationResult.issues.slice(0, 3).forEach(issue => {
    log(`  - ${issue}`);
  });
}

log('');

// ============================================================================
// PHASE 7: Save Metadata
// ============================================================================

phase('Save Metadata');

const reportDir = path.join(projectDir, '.claude', 'bulk-reports');
if (!fs.existsSync(reportDir)) {
  fs.mkdirSync(reportDir, { recursive: true });
}

const metadataFile = path.join(reportDir, `code-doc-${Date.now()}.json`);
const metadata = {
  timestamp: new Date().toISOString(),
  totalFiles: orchestrationResult.totalItems,
  filesDocumented: orchestrationResult.itemsProcessed,
  docsWritten: writtenFiles.length,
  outputDirectory: OUTPUT_DIR,
  validationStatus: {
    validFiles: validationResult.valid_files,
    coveragePercentage: validationResult.coverage_percentage,
    issues: validationResult.issues?.length || 0,
  },
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  status: orchestrationResult.status,
  errors: orchestrationResult.errors,
};

fs.writeFileSync(metadataFile, JSON.stringify(metadata, null, 2));
log(`Metadata saved: ${metadataFile}`);
log('');

log('='.repeat(70));
log('BULK CODE DOCUMENTATION COMPLETE');
log('='.repeat(70));
log(`Files processed: ${orchestrationResult.itemsProcessed}/${orchestrationResult.totalItems}`);
log(`Documentation written: ${writtenFiles.length}`);
log(`Output directory: ${OUTPUT_DIR}`);
log(`Valid files: ${validationResult.valid_files}/${writtenFiles.length}`);
log(`Fleet used: ${orchestrationResult.fleetUsed ? 'YES' : 'NO'}`);
log(`Workers: ${orchestrationResult.workersUsed}`);
log('='.repeat(70));

return {
  status: orchestrationResult.status,
  totalFiles: orchestrationResult.totalItems,
  filesProcessed: orchestrationResult.itemsProcessed,
  docsWritten: writtenFiles.length,
  outputDirectory: OUTPUT_DIR,
  validFiles: validationResult.valid_files,
  coveragePercentage: validationResult.coverage_percentage,
  fleetUsed: orchestrationResult.fleetUsed,
  workersUsed: orchestrationResult.workersUsed,
  metadataFile,
  errors: orchestrationResult.errors,
};
