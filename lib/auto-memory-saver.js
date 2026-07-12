#!/usr/bin/env node
/**
 * Auto Memory Saver - Extracts learnings from sessions and saves to:
 * 1. Memory files (feedback_*.md, reference_*.md, project_*.md)
 * 2. PostgreSQL learning.experiences table
 * 3. Updates MEMORY_INDEX.md
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const MEMORY_DIR = path.join(
  process.env.HOME,
  'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/memory'
);

/**
 * Save a memory to file
 * @param {string} type - 'feedback' | 'reference' | 'project'
 * @param {string} name - Kebab-case name (e.g., 'always-use-fleet')
 * @param {string} description - One-line summary
 * @param {string} content - Full memory content
 */
function saveMemory(type, name, description, content) {
  try {
    if (!type || !name || !description || !content) {
      throw new Error('Missing required parameters: type, name, description, content');
    }

    const fileName = `${type}_${name}.md`;
    const filePath = path.join(MEMORY_DIR, fileName);

    // Ensure memory directory exists
    if (!fs.existsSync(MEMORY_DIR)) {
      fs.mkdirSync(MEMORY_DIR, { recursive: true });
    }

    // Check if memory already exists
    const exists = fs.existsSync(filePath);

    const frontmatter = `---
name: ${name}
description: ${description}
metadata:
  type: ${type}
  created: ${new Date().toISOString()}
  updated: ${new Date().toISOString()}
---

`;

    const fullContent = frontmatter + content;

    fs.writeFileSync(filePath, fullContent, 'utf8');

    console.log(`${exists ? 'Updated' : 'Created'} ${fileName}`);

    return filePath;
  } catch (err) {
    console.error(`Failed to save memory ${name}: ${err.message}`);
    throw err;
  }
}

/**
 * Save to PostgreSQL learning.experiences
 * @param {string} type - Memory type
 * @param {string} content - Memory content
 */
function saveToPostgres(type, content) {
  try {
    // Use orchestrator API to save learning
    const payload = JSON.stringify({
      experience_type: `memory_${type}`,
      content: content,
      metadata: {
        source: 'auto-memory-saver',
        timestamp: new Date().toISOString()
      }
    });

    execSync(
      `curl -s -X POST http://aio-01:5000/learning/experiences \\
        -H "Content-Type: application/json" \\
        -d '${payload.replace(/'/g, "'\\''")}'`,
      { encoding: 'utf8' }
    );

    console.log(`Saved to PostgreSQL: ${type}`);
  } catch (err) {
    console.error(`Failed to save to PostgreSQL: ${err.message}`);
  }
}

/**
 * Update MEMORY_INDEX.md with new memory
 * @param {string} fileName - Memory file name
 * @param {string} description - One-line description
 */
function updateIndex(fileName, description) {
  try {
    if (!fileName || !description) {
      throw new Error('Missing required parameters: fileName, description');
    }

    const indexPath = path.join(process.env.HOME, '.claude/MEMORY_INDEX.md');

    if (!fs.existsSync(indexPath)) {
      console.warn('MEMORY_INDEX.md not found, skipping index update');
      return;
    }

    const index = fs.readFileSync(indexPath, 'utf8');
    const lines = index.split('\n');

    // Find the appropriate section
    const type = fileName.split('_')[0]; // feedback, reference, project
    const entry = `- [${fileName}](${path.join(MEMORY_DIR, fileName)}) — ${description}`;

    // TODO: Insert into appropriate section
    // For now, just log
    console.log(`Index entry: ${entry}`);
  } catch (err) {
    console.error(`Failed to update index for ${fileName}: ${err.message}`);
    // Non-fatal error, don't throw
  }
}

/**
 * Extract and save memories from session
 * @param {Object} learnings - Extracted learnings object
 */
function saveAllMemories(learnings) {
  try {
    if (!learnings || typeof learnings !== 'object') {
      throw new Error('Invalid learnings object');
    }

    const saved = [];
    const errors = [];

    // Save feedback memories
    if (learnings.feedback && Array.isArray(learnings.feedback) && learnings.feedback.length > 0) {
      learnings.feedback.forEach(item => {
        try {
          if (!item.description || !item.content) {
            throw new Error('Missing description or content in feedback item');
          }
          const name = item.name || item.title?.toLowerCase().replace(/\s+/g, '-') || `feedback-${Date.now()}`;
          const filePath = saveMemory('feedback', name, item.description, item.content);
          saveToPostgres('feedback', item.content);
          saved.push(filePath);
        } catch (err) {
          errors.push({ type: 'feedback', error: err.message });
          console.error(`Failed to save feedback item: ${err.message}`);
        }
      });
    }

    // Save reference memories
    if (learnings.reference && Array.isArray(learnings.reference) && learnings.reference.length > 0) {
      learnings.reference.forEach(item => {
        try {
          if (!item.description || !item.content) {
            throw new Error('Missing description or content in reference item');
          }
          const name = item.name || item.title?.toLowerCase().replace(/\s+/g, '-') || `reference-${Date.now()}`;
          const filePath = saveMemory('reference', name, item.description, item.content);
          saveToPostgres('reference', item.content);
          saved.push(filePath);
        } catch (err) {
          errors.push({ type: 'reference', error: err.message });
          console.error(`Failed to save reference item: ${err.message}`);
        }
      });
    }

    // Save project memories
    if (learnings.project && Array.isArray(learnings.project) && learnings.project.length > 0) {
      learnings.project.forEach(item => {
        try {
          if (!item.description || !item.content) {
            throw new Error('Missing description or content in project item');
          }
          const name = item.name || item.title?.toLowerCase().replace(/\s+/g, '-') || `project-${Date.now()}`;
          const filePath = saveMemory('project', name, item.description, item.content);
          saveToPostgres('project', item.content);
          saved.push(filePath);
        } catch (err) {
          errors.push({ type: 'project', error: err.message });
          console.error(`Failed to save project item: ${err.message}`);
        }
      });
    }

    if (errors.length > 0) {
      console.warn(`Completed with ${errors.length} errors:`, errors);
    }

    return saved;
  } catch (err) {
    console.error(`Failed to save memories: ${err.message}`);
    throw err;
  }
}

module.exports = {
  saveMemory,
  saveToPostgres,
  updateIndex,
  saveAllMemories
};

// CLI usage
if (require.main === module) {
  try {
    const args = process.argv.slice(2);

    if (args.length === 0) {
      console.log('Usage: auto-memory-saver.js <learnings.json>');
      console.log('');
      console.log('Example learnings.json:');
      console.log(JSON.stringify({
        feedback: [{
          name: 'always-use-fleet',
          description: 'User prefers fleet for all multi-AI work',
          content: 'User consistently requests fleet-based execution for parallel tasks.'
        }],
        reference: [{
          name: 'orchestrator-api',
          description: 'How to use the orchestrator REST API',
          content: 'Orchestrator at aio-01:5000 provides /secrets, /health, /workflows endpoints.'
        }]
      }, null, 2));
      process.exit(1);
    }

    const learningsFile = args[0];

    if (!fs.existsSync(learningsFile)) {
      throw new Error(`Learnings file not found: ${learningsFile}`);
    }

    const learnings = JSON.parse(fs.readFileSync(learningsFile, 'utf8'));

    const saved = saveAllMemories(learnings);

    console.log(`\n✅ Saved ${saved.length} memories`);
    saved.forEach(f => console.log(`   - ${f}`));
  } catch (err) {
    console.error(`\n❌ Error: ${err.message}`);
    process.exit(1);
  }
}
