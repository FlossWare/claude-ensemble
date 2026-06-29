#!/usr/bin/env node

/**
 * Structural Test: Hardcoded Model Version Detection
 *
 * Issue #96 Regression Test - Detects hardcoded model version strings
 * that will become stale over time.
 *
 * Scans:
 * 1. All .js files for hardcoded model version patterns
 * 2. Canonical model lists across key files for consistency
 */

import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ============================================================================
// Configuration
// ============================================================================

const PROJECT_ROOT = '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills';

// Patterns for hardcoded model versions
const HARDCODED_MODEL_PATTERNS = [
  /claude-[a-z]+-\d+-\d+@[a-z0-9]+/gi,  // claude-opus-4-1@latest
  /claude-[a-z]+-\d+@[a-z0-9]+/gi,       // claude-sonnet-4@latest
  /claude-[a-z]+-\d+-\d+-\d+@[a-z0-9]+/gi  // claude-haiku-4-5@latest
];

// Canonical files to check for model list consistency
const CANONICAL_FILES = {
  'ai-consensus-hierarchical.js': {
    path: path.join(PROJECT_ROOT, 'ai-consensus-hierarchical.js'),
    modelListName: 'MODEL_SPECIALIZATIONS',
    linePattern: /const MODEL_SPECIALIZATIONS = {/
  },
  'consensus-engine.js': {
    path: path.join(PROJECT_ROOT, 'shared/consensus-engine.js'),
    modelListName: 'workers default',
    linePattern: /workers = \[/
  },
  'load-multi-ai-config.js': {
    path: path.join(PROJECT_ROOT, 'load-multi-ai-config.js'),
    modelListName: 'workers.models',
    linePattern: /models: \[/
  }
};

// ============================================================================
// Test Functions
// ============================================================================

/**
 * Find all .js files in the project
 */
function findJavaScriptFiles() {
  const files = [];

  function walk(dir) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);

      if (entry.isDirectory()) {
        // Skip node_modules
        if (entry.name !== 'node_modules' && entry.name !== '.git') {
          walk(fullPath);
        }
      } else if (entry.isFile() && entry.name.endsWith('.js')) {
        files.push(fullPath);
      }
    }
  }

  walk(PROJECT_ROOT);
  return files;
}

/**
 * Scan a file for hardcoded model version strings
 */
function scanFileForHardcodedModels(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const findings = [];
  const lines = content.split('\n');
  const relativePath = path.relative(PROJECT_ROOT, filePath);

  // Skip the test file itself
  if (relativePath === 'test-hardcoded-models.js') {
    return findings;
  }

  lines.forEach((line, index) => {
    // Skip comment lines (both single-line and multi-line comments)
    const trimmedLine = line.trim();
    if (trimmedLine.startsWith('//') || trimmedLine.startsWith('*')) {
      return;
    }

    for (const pattern of HARDCODED_MODEL_PATTERNS) {
      const matches = line.match(pattern);
      if (matches) {
        findings.push({
          file: relativePath,
          line: index + 1,
          content: line.trim(),
          matches: matches
        });
      }
    }
  });

  return findings;
}

/**
 * Extract model list from a canonical file
 */
function extractModelList(filePath, modelListName) {
  if (!fs.existsSync(filePath)) {
    return { error: 'File not found', models: [] };
  }

  const content = fs.readFileSync(filePath, 'utf-8');
  const models = [];

  // Extract model names based on file-specific patterns
  if (modelListName === 'MODEL_SPECIALIZATIONS') {
    // Extract from MODEL_SPECIALIZATIONS object - need to handle nested braces
    const startIdx = content.indexOf('const MODEL_SPECIALIZATIONS = {');
    if (startIdx !== -1) {
      // Find matching closing brace by counting braces
      let braceCount = 0;
      let inBlock = false;
      let endIdx = startIdx;

      for (let i = startIdx; i < content.length; i++) {
        if (content[i] === '{') {
          braceCount++;
          inBlock = true;
        } else if (content[i] === '}') {
          braceCount--;
          if (inBlock && braceCount === 0) {
            endIdx = i;
            break;
          }
        }
      }

      const blockContent = content.substring(startIdx, endIdx + 1);
      // Extract keys (model names) - handle both unquoted and quoted keys
      const keyPattern = /^\s+['"]?(fable|opus|sonnet|haiku|gpt-4o|gemini)['"]?:\s*\{/gm;
      let match;
      while ((match = keyPattern.exec(blockContent)) !== null) {
        models.push(match[1]);
      }
    }
  } else if (modelListName === 'workers default') {
    // Extract from workers array
    const arrayPattern = /workers = \[([^\]]+)\]/;
    const match = content.match(arrayPattern);
    if (match) {
      const modelsStr = match[1];
      const modelMatches = modelsStr.match(/'([^']+)'/g);
      if (modelMatches) {
        models.push(...modelMatches.map(m => m.replace(/'/g, '')));
      }
    }
  } else if (modelListName === 'workers.models') {
    // Extract from models array in config
    const arrayPattern = /models:\s*\[([^\]]+)\]/;
    const match = content.match(arrayPattern);
    if (match) {
      const modelsStr = match[1];
      const modelMatches = modelsStr.match(/'([^']+)'/g);
      if (modelMatches) {
        models.push(...modelMatches.map(m => m.replace(/'/g, '')));
      }
    }
  }

  return { models: [...new Set(models)], error: null };
}

/**
 * Compare model lists for consistency
 */
function compareModelLists(lists) {
  const allModels = new Set();
  const mismatches = [];

  // Collect all unique models
  Object.values(lists).forEach(list => {
    if (list.models) {
      list.models.forEach(model => allModels.add(model));
    }
  });

  // Check each file against the complete set
  Object.entries(lists).forEach(([fileName, listData]) => {
    if (listData.error) {
      mismatches.push({
        file: fileName,
        issue: listData.error
      });
      return;
    }

    const missing = [...allModels].filter(model => !listData.models.includes(model));
    const extra = listData.models.filter(model => !allModels.has(model));

    if (missing.length > 0 || extra.length > 0) {
      mismatches.push({
        file: fileName,
        models: listData.models,
        missing: missing,
        extra: extra
      });
    }
  });

  return {
    allModels: [...allModels].sort(),
    mismatches: mismatches
  };
}

/**
 * Run all tests
 */
function runTests() {
  console.log('='.repeat(70));
  console.log('HARDCODED MODEL VERSION DETECTION TEST');
  console.log('='.repeat(70));
  console.log('');

  const results = {
    hardcodedFindings: [],
    modelListConsistency: null,
    pass: true,
    errors: []
  };

  // Test 1: Scan for hardcoded model versions
  console.log('Test 1: Scanning for hardcoded model version strings...');
  const jsFiles = findJavaScriptFiles();
  console.log(`  Found ${jsFiles.length} JavaScript files`);

  jsFiles.forEach(file => {
    const findings = scanFileForHardcodedModels(file);
    if (findings.length > 0) {
      results.hardcodedFindings.push(...findings);
    }
  });

  if (results.hardcodedFindings.length > 0) {
    console.log(`  FAIL: Found ${results.hardcodedFindings.length} hardcoded model version(s)`);
    results.pass = false;

    results.hardcodedFindings.forEach(finding => {
      console.log(`    ${finding.file}:${finding.line}`);
      console.log(`      ${finding.content}`);
      console.log(`      Matches: ${finding.matches.join(', ')}`);
    });
  } else {
    console.log('  PASS: No hardcoded model versions found');
  }
  console.log('');

  // Test 2: Verify model list consistency
  console.log('Test 2: Verifying model list consistency across canonical files...');
  const modelLists = {};

  Object.entries(CANONICAL_FILES).forEach(([name, config]) => {
    const result = extractModelList(config.path, config.modelListName);
    modelLists[name] = result;

    if (result.error) {
      console.log(`  WARNING: ${name} - ${result.error}`);
    } else {
      console.log(`  ${name}: ${result.models.join(', ')}`);
    }
  });

  const comparison = compareModelLists(modelLists);
  results.modelListConsistency = comparison;

  console.log('');
  console.log(`  Complete model set: ${comparison.allModels.join(', ')}`);

  if (comparison.mismatches.length > 0) {
    console.log(`  FAIL: Found ${comparison.mismatches.length} consistency issue(s)`);
    results.pass = false;

    comparison.mismatches.forEach(mismatch => {
      console.log(`    ${mismatch.file}:`);
      if (mismatch.issue) {
        console.log(`      Issue: ${mismatch.issue}`);
      } else {
        if (mismatch.missing && mismatch.missing.length > 0) {
          console.log(`      Missing: ${mismatch.missing.join(', ')}`);
        }
        if (mismatch.extra && mismatch.extra.length > 0) {
          console.log(`      Extra: ${mismatch.extra.join(', ')}`);
        }
      }
    });
  } else {
    console.log('  PASS: All canonical model lists are consistent');
  }
  console.log('');

  // Summary
  console.log('='.repeat(70));
  console.log('TEST SUMMARY');
  console.log('='.repeat(70));
  console.log(`Status: ${results.pass ? 'PASS' : 'FAIL'}`);
  console.log(`Hardcoded model versions found: ${results.hardcodedFindings.length}`);
  console.log(`Model list consistency issues: ${comparison.mismatches.length}`);
  console.log('');

  return results;
}

// ============================================================================
// Main
// ============================================================================

// Run tests if executed directly
const results = runTests();
process.exit(results.pass ? 0 : 1);

export { runTests, scanFileForHardcodedModels, extractModelList, compareModelLists };
