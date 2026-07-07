import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const meta = {
  name: 'enable-local-models',
  description: 'Enable local Ollama models in workflow files based on config',
  whenToUse: 'When you want to activate local models across all workflows after detection',
  phases: [
    { title: 'Read Config', detail: 'Load local-models-config.json' },
    { title: 'Validate', detail: 'Check if enabled and models exist' },
    { title: 'Find Workflows', detail: 'Locate files with commented ollama lines' },
    { title: 'Update Files', detail: 'Uncomment ollama model lines' },
    { title: 'Report', detail: 'Summary of changes' },
  ],
}

// ============================================================================
// CONFIGURATION
// ============================================================================

const SKILLS_DIR = __dirname
const CONFIG_PATH = path.join(SKILLS_DIR, 'local-models-config.json')

// Files that have commented ollama lines
const WORKFLOW_FILES = [
  'ai-prompt.js',
  'code-review.js',
  'code-review-auto.js',
  'code-pr-review.js',
  'code-pr-review-auto.js',
  'code-solve.js',
  'code-solve-auto.js',
  'code-security.js',
  'code-security-auto.js',
  'code-test.js',
  'code-test-auto.js',
  'code-doc.js',
  'code-doc-auto.js',
  'code-release-notes.js',
  'code-release-notes-auto.js',
]

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

const logInfo = (msg) => console.log(\`ℹ️  \${msg}\`)
const logSuccess = (msg) => console.log(\`✅ \${msg}\`)
const logWarning = (msg) => console.log(\`⚠️  \${msg}\`)
const logError = (msg) => console.log(\`❌ \${msg}\`)

function readConfig() {
  try {
    if (!fs.existsSync(CONFIG_PATH)) {
      logError(\`Config file not found: \${CONFIG_PATH}\`)
      return null
    }

    const content = fs.readFileSync(CONFIG_PATH, 'utf8')
    return JSON.parse(content)
  } catch (error) {
    logError(\`Failed to read config: \${error.message}\`)
    return null
  }
}

function findOllamaCommentPattern(content) {
  // Look for patterns like:
  // // Ollama (local models) - uncomment when running locally
  // // models.push('ollama/llama3', 'ollama/codestral', 'ollama/deepseek-coder')

  const patterns = [
    {
      // Pattern for ai-prompt.js and similar
      regex: /(\s*)(\/\/ Ollama \(local models\) - uncomment when running locally\n\s*)(\/\/ models\.push\([^)]+\))/g,
      type: 'models.push'
    },
    {
      // Pattern for WORKERS array
      regex: /(\s*)(\/\/ Ollama models.*\n\s*)(\/\/ 'ollama\/[^']+',?\s*(?:\/\/ '[^']+',?\s*)*)/g,
      type: 'workers_array'
    },
    {
      // Generic pattern for any commented ollama line
      regex: /^(\s*)(\/\/ .*ollama.*$)/gm,
      type: 'generic'
    }
  ]

  for (const pattern of patterns) {
    if (pattern.regex.test(content)) {
      return pattern
    }
  }

  return null
}

function uncommentOllamaLines(content, modelNames) {
  let modified = content
  let changesMade = false

  // Pattern 1: models.push() style
  const pushPattern = /(\s*)(\/\/ Ollama \(local models\) - uncomment when running locally\n\s*)(\/\/ models\.push\()([^)]+)(\))/g

  if (pushPattern.test(content)) {
    // Build the models array from config
    const modelsArray = modelNames.map(m => \`'\${m}'\`).join(', ')

    modified = content.replace(
      pushPattern,
      (match, indent, comment, pushStart, oldModels, pushEnd) => {
        changesMade = true
        return \`\${indent}// Ollama (local models) - enabled via enable-local-models\n\${indent}models.push(\${modelsArray})\`
      }
    )
  }

  // Pattern 2: WORKERS array style (for code-review.js, etc.)
  const workersPattern = /(const WORKERS = \[\n\s*'[^']+',\s*'[^']+',\s*'[^']+'[^\]]*)(\/\/ Ollama models[^\n]*\n\s*)(\/\/ '[^']+',?\s*(?:\/\/ '[^']+',?\s*)*)/g

  if (workersPattern.test(content)) {
    const modelsStr = modelNames.map(m => \`  '\${m}',\`).join('\n')

    modified = modified.replace(
      workersPattern,
      (match, arrayStart, comment, commentedModels) => {
        changesMade = true
        return \`\${arrayStart.trimEnd()},\n  // Ollama models - enabled via enable-local-models\n\${modelsStr}\`
      }
    )
  }

  // Pattern 3: Generic commented ollama lines
  const genericPattern = /^(\s*)(\/\/ )(.*ollama\/[^\/\n]+.*)$/gm

  if (genericPattern.test(content) && !changesMade) {
    modified = modified.replace(
      genericPattern,
      (match, indent, commentPrefix, rest) => {
        // Only uncomment if it's a model reference
        if (rest.includes('ollama/')) {
          changesMade = true
          return \`\${indent}\${rest}\`
        }
        return match
      }
    )
  }

  return { content: modified, changed: changesMade }
}

function updateWorkflowFile(filePath, modelNames) {
  try {
    if (!fs.existsSync(filePath)) {
      return { success: false, error: 'File not found', changed: false }
    }

    const content = fs.readFileSync(filePath, 'utf8')

    // Check if file has commented ollama lines
    const hasCommentedOllama = content.includes('// ollama/') ||
                                content.includes('// Ollama') ||
                                content.includes('//ollama/')

    if (!hasCommentedOllama) {
      return { success: true, skipped: true, reason: 'No commented ollama lines found', changed: false }
    }

    // Uncomment the lines
    const { content: newContent, changed } = uncommentOllamaLines(content, modelNames)

    if (!changed) {
      return { success: true, skipped: true, reason: 'No changes needed', changed: false }
    }

    // Write back
    fs.writeFileSync(filePath, newContent, 'utf8')

    return { success: true, changed: true }
  } catch (error) {
    return { success: false, error: error.message, changed: false }
  }
}

// ============================================================================
// PHASE 1: Read Config
// ============================================================================

phase('Read Config')
logInfo('Reading local-models-config.json...')

const config = readConfig()
if (!config) {
  logError('Failed to read configuration')
  return {
    success: false,
    error: 'Configuration read failed',
    config_path: CONFIG_PATH
  }
}

logSuccess(\`Config loaded: \${Object.keys(config.models || {}).length} model roles defined\`)

// ============================================================================
// PHASE 2: Validate
// ============================================================================

phase('Validate')
logInfo('Validating configuration...')

if (!config.enabled) {
  logWarning('Local models are disabled in config')
  logInfo('Set "enabled": true in local-models-config.json to enable')
  return {
    success: false,
    error: 'Local models not enabled in config',
    config_enabled: config.enabled,
    suggestion: 'Run: detect-local-models --enable or manually edit config'
  }
}

if (!config.models || Object.keys(config.models).length === 0) {
  logError('No models defined in config')
  return {
    success: false,
    error: 'No models in configuration',
    suggestion: 'Run: detect-local-models --auto to detect and configure models'
  }
}

logSuccess(\`Enabled: \${config.enabled}\`)
logSuccess(\`Provider: \${config.provider}\`)
logSuccess(\`Base URL: \${config.baseUrl}\`)

// Extract model names with ollama/ prefix
const modelNames = Object.values(config.models)
  .filter(Boolean)
  .map(m => m.startsWith('ollama/') ? m : \`ollama/\${m}\`)

logInfo(\`Models to enable: \${modelNames.join(', ')}\`)

// ============================================================================
// PHASE 3: Find Workflows
// ============================================================================

phase('Find Workflows')
logInfo(\`Scanning \${WORKFLOW_FILES.length} workflow files...\`)

const existingFiles = WORKFLOW_FILES.filter(file => {
  const fullPath = path.join(SKILLS_DIR, file)
  return fs.existsSync(fullPath)
})

logSuccess(\`Found \${existingFiles.length}/\${WORKFLOW_FILES.length} workflow files\`)

// ============================================================================
// PHASE 4: Update Files
// ============================================================================

phase('Update Files')
logInfo('Uncommenting ollama model lines...')

const results = {
  updated: [],
  skipped: [],
  failed: [],
}

for (const file of existingFiles) {
  const fullPath = path.join(SKILLS_DIR, file)
  logInfo(\`Processing: \${file}\`)

  const result = updateWorkflowFile(fullPath, modelNames)

  if (result.success) {
    if (result.changed) {
      results.updated.push(file)
      logSuccess(\`  Updated: \${file}\`)
    } else if (result.skipped) {
      results.skipped.push({ file, reason: result.reason })
      logWarning(\`  Skipped: \${file} (\${result.reason})\`)
    }
  } else {
    results.failed.push({ file, error: result.error })
    logError(\`  Failed: \${file} - \${result.error}\`)
  }
}

// ============================================================================
// PHASE 5: Report
// ============================================================================

phase('Report')

const totalFiles = existingFiles.length
const updatedCount = results.updated.length
const skippedCount = results.skipped.length
const failedCount = results.failed.length

log('')
log('═'.repeat(70))
log('📊 ENABLE LOCAL MODELS REPORT')
log('═'.repeat(70))
log('')
log(\`Total workflow files scanned: \${totalFiles}\`)
log(\`  ✅ Updated: \${updatedCount}\`)
log(\`  ⏭️  Skipped: \${skippedCount}\`)
log(\`  ❌ Failed: \${failedCount}\`)
log('')
log(\`Models enabled: \${modelNames.join(', ')}\`)
log('')

if (results.updated.length > 0) {
  log('📝 Updated Files:')
  results.updated.forEach(file => log(\`  - \${file}\`))
  log('')
}

if (results.skipped.length > 0) {
  log('⏭️  Skipped Files:')
  results.skipped.forEach(({ file, reason }) => log(\`  - \${file}: \${reason}\`))
  log('')
}

if (results.failed.length > 0) {
  log('❌ Failed Files:')
  results.failed.forEach(({ file, error }) => log(\`  - \${file}: \${error}\`))
  log('')
}

log('═'.repeat(70))

if (updatedCount > 0) {
  log('')
  logSuccess(\`Local models have been enabled in \${updatedCount} workflow file(s)!\`)
  log('')
  logInfo('These workflows will now use your local Ollama models:')
  modelNames.forEach(model => log(\`  - \${model}\`))
  log('')
  logInfo('To disable, set "enabled": false in local-models-config.json')
  log('and run this workflow again, or manually re-comment the lines.')
}

const report = {
  success: updatedCount > 0 || failedCount === 0,
  timestamp: args?._timestamp || 'runtime-timestamp',
  config: {
    enabled: config.enabled,
    provider: config.provider,
    base_url: config.baseUrl,
    models: modelNames,
  },
  files: {
    scanned: totalFiles,
    updated: updatedCount,
    skipped: skippedCount,
    failed: failedCount,
  },
  updated_files: results.updated,
  skipped_files: results.skipped,
  failed_files: results.failed,
  message: updatedCount > 0
    ? \`Successfully enabled local models in \${updatedCount} workflow file(s)\`
    : 'No files were updated',
}

return report
