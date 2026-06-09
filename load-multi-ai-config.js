// Helper to load multi-AI config
// NOTE: This is a utility, not a workflow (no export const meta)
//
// Usage in workflows:
//   const getConfig = new Function(readFileSync('~/.claude/workflows/load-multi-ai-config.js', 'utf8') + '; return loadMultiAIConfig;')()
//   const config = getConfig()
//
// Or inline the logic since workflows can't import modules

function loadMultiAIConfig() {
  const homeDir = process.env.HOME || process.env.USERPROFILE
  const configPath = `${homeDir}/.claude/workflows/multi-ai-config.json`

  // Default config (fallback if file doesn't exist)
  const defaultConfig = {
    enabled: true,
    workers: {
      models: ['opus', 'sonnet', 'haiku'],
      count: 3
    },
    arbiter: {
      enabled: true,
      model: 'opus'
    }
  }

  try {
    // Workflows don't have fs access, so this won't work
    // They need to use agent() to read the file
    return defaultConfig
  } catch (error) {
    return defaultConfig
  }
}

// Export for workflows to use
loadMultiAIConfig
