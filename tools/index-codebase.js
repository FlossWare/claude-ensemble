#!/usr/bin/env node
/**
 * Index entire codebase for semantic search
 *
 * Usage:
 *   ./tools/index-codebase.js /path/to/repo
 *   ./tools/index-codebase.js ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
 */

const fs = require('fs');
const path = require('path');
const { addToIndex } = require('../shared/universal-semantic-search.js');
const { execSync } = require('child_process');

const EXTENSIONS = {
  '.js': 'javascript',
  '.mjs': 'javascript',
  '.cjs': 'javascript',
  '.ts': 'typescript',
  '.py': 'python',
  '.sh': 'bash',
  '.java': 'java',
  '.go': 'go',
  '.rs': 'rust',
  '.c': 'c',
  '.cpp': 'cpp',
  '.md': 'markdown',
  '.json': 'json',
  '.yaml': 'yaml',
  '.yml': 'yaml'
};

const IGNORE_DIRS = [
  'node_modules',
  '.git',
  'dist',
  'build',
  '.claude',
  '__pycache__',
  'venv',
  '.venv'
];

async function indexCodebase(rootDir) {
  console.log(`📂 Indexing codebase: ${rootDir}\n`);

  const files = findCodeFiles(rootDir);
  console.log(`Found ${files.length} code files\n`);

  let indexed = 0;
  let skipped = 0;
  let errors = 0;

  for (const file of files) {
    try {
      const ext = path.extname(file);
      const language = EXTENSIONS[ext] || 'unknown';

      const content = fs.readFileSync(file, 'utf8');

      // Skip empty or very small files
      if (content.length < 50) {
        skipped++;
        continue;
      }

      // Skip binary-looking content
      if (content.includes('\0')) {
        skipped++;
        continue;
      }

      await addToIndex('code', {
        path: file,
        language: language,
        text: content
      });

      indexed++;

      if (indexed % 100 === 0) {
        console.log(`  Progress: ${indexed}/${files.length}`);
      }

    } catch (err) {
      errors++;
      if (errors < 10) {
        console.error(`  Error indexing ${file}: ${err.message}`);
      }
    }
  }

  console.log(`\n✅ Complete!`);
  console.log(`   Indexed: ${indexed}`);
  console.log(`   Skipped: ${skipped}`);
  console.log(`   Errors: ${errors}`);
}

/**
 * Find all code files in directory
 */
function findCodeFiles(dir) {
  const files = [];

  function walk(currentDir) {
    const entries = fs.readdirSync(currentDir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);

      if (entry.isDirectory()) {
        // Skip ignored directories
        if (IGNORE_DIRS.includes(entry.name)) {
          continue;
        }
        walk(fullPath);
      } else if (entry.isFile()) {
        const ext = path.extname(entry.name);
        if (EXTENSIONS[ext]) {
          files.push(fullPath);
        }
      }
    }
  }

  walk(dir);
  return files;
}

// Main
if (require.main === module) {
  const dir = process.argv[2] || process.cwd();

  if (!fs.existsSync(dir)) {
    console.error(`Error: Directory not found: ${dir}`);
    process.exit(1);
  }

  indexCodebase(dir).then(() => {
    console.log('\nCodebase indexed! Try searching:');
    console.log('  node -e "require(\'./shared/universal-semantic-search.js\').universalSearch(\'authentication\').then(r => console.log(r))"');
    process.exit(0);
  }).catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
  });
}

module.exports = { indexCodebase };
