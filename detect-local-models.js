export const meta = {
  name: 'detect-local-models',
  description: 'Auto-detect locally available Ollama models and update configuration',
  phases: [
    { title: 'Check Ollama', detail: 'Verify Ollama installation and service' },
    { title: 'Check Service', detail: 'Verify Ollama service status' },
    { title: 'List Models', detail: 'Retrieve available models' },
    { title: 'Test Models', detail: 'Verify each model functionality' },
    { title: 'Update Config', detail: 'Write detected models to config' },
    { title: 'Report', detail: 'Generate status report' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

const fs = require('fs')
const path = require('path')
const { execSync, spawnSync } = require('child_process')
const os = require('os')

// Parse args - 'args' is provided by the harness as a string
const parsedArgs = (args || '').split(/\s+/).filter(Boolean)
const skipTest = parsedArgs.includes('--skip-test')
const autoUpdate = parsedArgs.includes('--auto')
const enableFlag = parsedArgs.includes('--enable')
const verbose = parsedArgs.includes('--verbose')
const configPath = path.join(
  path.dirname(require.main.filename),
  'local-models-config.json'
)

const EXEC_TIMEOUT_MS = 30000 // 30 second timeout for shell commands
const MODEL_TEST_TIMEOUT_MS = 60000 // 60 second timeout for model tests

const logMsg = (msg, level = 'info') => {
  const icons = {
    info: '✓',
    warn: '⚠️',
    error: '❌',
    debug: '🔍',
    success: '✅'
  }
  console.log(`${icons[level]} ${msg}`)
}

const execCmd = (cmd, description, silent = false, timeout = EXEC_TIMEOUT_MS) => {
  try {
    if (!silent && verbose) log(`Executing: ${cmd}`, 'debug')
    const result = execSync(cmd, { encoding: 'utf8', stdio: silent ? 'pipe' : 'inherit', timeout })
    return { success: true, output: result.trim(), error: null }
  } catch (err) {
    const error = err.stderr?.trim() || err.message || err.toString()
    if (!silent && verbose) log(`Command failed: ${error}`, 'debug')
    return { success: false, output: '', error }
  }
}

const readConfig = () => {
  try {
    if (fs.existsSync(configPath)) {
      return JSON.parse(fs.readFileSync(configPath, 'utf8'))
    }
  } catch (err) {
    log(`Warning: Failed to read config: ${err.message}`, 'warn')
  }
  return {
    enabled: false,
    provider: 'ollama',
    baseUrl: 'http://localhost:11434',
    models: {},
    fallback_to_claude: true,
  }
}

const writeConfig = (config) => {
  try {
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2) + '\n')
    return true
  } catch (err) {
    log(`Failed to write config: ${err.message}`, 'error')
    return false
  }
}

// ============= PHASE 1: Check Ollama Installation =============
phase('Check Ollama')
log('Checking Ollama installation...')

const ollamaCheck = execCmd('which ollama', 'Check ollama binary', true)
if (!ollamaCheck.success) {
  log('Ollama not found in PATH', 'error')
  log('Install Ollama from https://ollama.ai', 'warn')
  return {
    success: false,
    phase: 'Check Ollama',
    error: 'Ollama not installed',
    installation_url: 'https://ollama.ai',
  }
}

const ollamaPath = ollamaCheck.output
log(`Found Ollama at: ${ollamaPath}`)

// Get Ollama version
const versionResult = execCmd(`${ollamaPath} --version`, 'Get version', true)
const ollamaVersion = versionResult.success
  ? versionResult.output.replace(/^ollama version /, '').split('\n')[0]
  : 'unknown'
log(`Ollama version: ${ollamaVersion}`)

// ============= PHASE 2: Check Service Status =============
phase('Check Service')
log('Checking Ollama service...')

const curlResult = execCmd(
  'curl -s -m 2 http://localhost:11434/api/version',
  'Check service',
  true
)

let serviceRunning = false
let ollamaServiceVersion = null

if (curlResult.success) {
  try {
    const data = JSON.parse(curlResult.output)
    serviceRunning = true
    ollamaServiceVersion = data.version
    log(`Service running (version ${ollamaServiceVersion})`)
  } catch (err) {
    log('Service not responding properly', 'warn')
  }
} else {
  log('Service not responding on localhost:11434', 'warn')
  log('Attempting to start Ollama service...', 'info')

  const startResult = execCmd('ollama serve &', 'Start service', true)

  // Wait a moment for service to start
  let retries = 3
  let connected = false
  while (retries > 0 && !connected) {
    try {
      const checkResult = execCmd(
        'curl -s -m 1 http://localhost:11434/api/version',
        'Retry service check',
        true
      )
      if (checkResult.success) {
        try {
          const data = JSON.parse(checkResult.output)
          ollamaServiceVersion = data.version
          serviceRunning = true
          connected = true
          log('Service started successfully')
        } catch (e) {
          // Silent parse error
        }
      }
    } catch (e) {
      // Silent retry error
    }

    if (!connected && retries > 1) {
      execCmd('sleep 2', 'Wait for service', true)
    }
    retries--
  }

  if (!connected) {
    log('Failed to start Ollama service', 'error')
    return {
      success: false,
      phase: 'Check Service',
      error: 'Service not running and startup failed',
      suggestion: 'Start Ollama manually: ollama serve',
    }
  }
}

// ============= PHASE 3: List Available Models =============
phase('List Models')
log('Retrieving available models...')

const listResult = execCmd('ollama list', 'List models', true)
if (!listResult.success) {
  log(`Failed to list models: ${listResult.error}`, 'error')
  return {
    success: false,
    phase: 'List Models',
    error: 'Could not retrieve model list',
  }
}

const parseModels = (output) => {
  const lines = output.split('\n').slice(1) // Skip header
  const models = []

  for (const line of lines) {
    if (!line.trim()) continue

    const parts = line.split(/\s+/)
    if (parts.length >= 2) {
      const name = parts[0]
      const id = parts[1]
      const sizeStr = parts[2] || ''

      // Extract size in MB
      let size = 0
      const sizeMatch = sizeStr.match(/(\d+(?:\.\d+)?)(MB|GB)/)
      if (sizeMatch) {
        size = parseFloat(sizeMatch[1])
        if (sizeMatch[2] === 'GB') size *= 1024
      }

      models.push({
        name,
        id,
        size,
        sizeStr,
      })
    }
  }

  return models
}

const models = parseModels(listResult.output)
log(`Found ${models.length} model(s)`)

if (models.length === 0) {
  log('No models available. Pull some first: ollama pull <model>', 'warn')
  return {
    success: false,
    phase: 'List Models',
    error: 'No models available',
    suggestion: 'Pull a model: ollama pull llama2',
  }
}

models.forEach(m => {
  log(`  - ${m.name} (${m.sizeStr})`, 'debug')
})

// ============= PHASE 4: Test Models =============
phase('Test Models')

const testedModels = {}
const failedModels = {}

if (!skipTest) {
  log(`Testing ${models.length} model(s)...`)

  for (const model of models) {
    log(`Testing: ${model.name}...`, 'debug')

    // Use spawnSync with argument array to avoid command injection via model names
    const testResult = spawnSync('ollama', ['run', model.name, '--nowordwrap'], {
      input: 'Say hello in one word',
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: MODEL_TEST_TIMEOUT_MS,
    })

    if (testResult.status === 0) {
      testedModels[model.name] = {
        ...model,
        status: 'working',
        tested_at: args?._timestamp || 'runtime-timestamp',
      }
      log(`${model.name} OK`, 'success')
    } else {
      const errorMsg = (testResult.stderr || testResult.error?.message || 'unknown error').toString().substring(0, 100)
      failedModels[model.name] = {
        ...model,
        status: 'failed',
        error: errorMsg,
      }
      log(`Failed to test ${model.name}`, 'warn')
    }
  }
} else {
  // Skip test - mark all as untested
  for (const model of models) {
    testedModels[model.name] = {
      ...model,
      status: 'untested',
    }
  }
  log('Skipping model tests (--skip-test)')
}

const workingCount = Object.keys(testedModels).length
const failedCount = Object.keys(failedModels).length

log(`Results: ${workingCount} working, ${failedCount} failed`)

// ============= PHASE 5: Update Config =============
phase('Update Config')

const currentConfig = readConfig()
log(`Current config: ${JSON.stringify(currentConfig.models)}`, 'debug')

// Categorize models
const categorized = {
  fast: null,
  balanced: null,
  powerful: null,
  code: null,
}

const modelNames = Object.keys(testedModels)

// Smart categorization based on model names
for (const modelName of modelNames) {
  const lower = modelName.toLowerCase()

  // Code models
  if (lower.includes('code') || lower.includes('coder') || lower.includes('phi')) {
    if (!categorized.code) categorized.code = modelName
  }
  // Fast models
  else if (lower.includes('lite') || lower.includes('tiny') || lower.includes('mini')) {
    if (!categorized.fast) categorized.fast = modelName
  }
  // Powerful models
  else if (lower.includes('dolphin') || lower.includes('wizard') || lower.includes('neural')) {
    if (!categorized.powerful) categorized.powerful = modelName
  }
  // Default balanced
  else if (!categorized.balanced) {
    categorized.balanced = modelName
  }
}

// Ensure at least some categorization
const orderedModels = modelNames.sort()
if (!categorized.fast && orderedModels.length > 0) categorized.fast = orderedModels[0]
if (!categorized.balanced && orderedModels.length > 1) categorized.balanced = orderedModels[1]
if (!categorized.powerful && orderedModels.length > 2) categorized.powerful = orderedModels[2]
if (!categorized.code && orderedModels.length > 3) categorized.code = orderedModels[3]

const updatedConfig = {
  ...currentConfig,
  enabled: (autoUpdate || enableFlag) ? true : currentConfig.enabled,
  provider: 'ollama',
  baseUrl: 'http://localhost:11434',
  models: Object.fromEntries(
    Object.entries(categorized).filter(([, v]) => v !== null)
  ),
  detected_at: args?._timestamp || 'runtime-timestamp',
  detected_models: testedModels,
  fallback_to_claude: true,
}

if (!autoUpdate && !enableFlag) {
  log('Detected models:')
  Object.entries(categorized).forEach(([role, model]) => {
    if (model) log(`  ${role}: ${model}`, 'debug')
  })

  log('Configuration ready to update', 'info')
} else {
  const writeSuccess = writeConfig(updatedConfig)
  if (writeSuccess) {
    log(`Config updated at ${configPath}`)
  } else {
    log('Failed to update config', 'error')
  }
}

// ============= PHASE 6: Status Report =============
phase('Report')

const report = {
  success: true,
  timestamp: args?._timestamp || 'runtime-timestamp',
  ollama: {
    installed: true,
    path: ollamaPath,
    version: ollamaVersion,
    service_running: serviceRunning,
    service_version: ollamaServiceVersion,
  },
  models: {
    available: models.length,
    working: workingCount,
    failed: failedCount,
    details: testedModels,
  },
  detection: {
    auto_update: autoUpdate,
    enable: enableFlag,
    config_path: configPath,
    fast: categorized.fast || null,
    balanced: categorized.balanced || null,
    powerful: categorized.powerful || null,
    code: categorized.code || null,
  },
  next_steps: [],
}

// Generate next steps
if (!serviceRunning) {
  report.next_steps.push('Start Ollama service: ollama serve')
}
if (failedCount > 0) {
  report.next_steps.push(`Investigate ${failedCount} failed model(s)`)
}
if (!autoUpdate && !enableFlag) {
  report.next_steps.push('Run with --auto to update configuration')
  report.next_steps.push('Run with --enable to enable in workflows')
}

// Print report
log('\n=== DETECTION REPORT ===')
log(`Timestamp: ${report.timestamp}`)
log(`Ollama: ${report.ollama.version} at ${report.ollama.path}`)
log(`Service: ${report.ollama.service_running ? 'RUNNING' : 'NOT RUNNING'}`)
log(`Models Found: ${report.models.available}`)
log(`  - Working: ${report.models.working}`)
if (report.models.failed > 0) {
  log(`  - Failed: ${report.models.failed}`, 'warn')
}
log(`\nDetected Roles:`)
Object.entries(categorized).forEach(([role, model]) => {
  if (model) log(`  ${role}: ${model}`, 'debug')
})

if (report.next_steps.length > 0) {
  log(`\nNext Steps:`)
  report.next_steps.forEach(step => {
    log(`  - ${step}`, 'info')
  })
}

// Ask about enabling in workflows
if ((autoUpdate || enableFlag) && workingCount > 0) {
  log('\nModels are ready to use in workflows!', 'success')
  report.ready_to_use = true
}

return report

}
