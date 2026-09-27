/**
 * Compression Bridge
 * Calls Python compression API from JavaScript
 * Reduces token usage via recursive text compression
 */

const { execSync } = require('child_process')
const path = require('path')

function compressDiff(diffText) {
  try {
    const jsonPayload = JSON.stringify({
      text: diffText,
      task_type: 'code-review'
    })

    const result = execSync(`python3 -c "
import sys, json
sys.path.insert(0, '${path.join(__dirname, '../compression')}')
from compression_api import compress_recursive
data = json.loads('${jsonPayload.replace(/'/g, "\\'")}')
result = compress_recursive(data['text'])
print(json.dumps({'compressed': result, 'original_length': len(data['text']), 'compressed_length': len(result)}))
"`, {
      encoding: 'utf-8',
      timeout: 5000,
      stdio: ['pipe', 'pipe', 'pipe']
    }).trim()

    const output = JSON.parse(result)
    const ratio = ((1 - output.compressed_length / output.original_length) * 100).toFixed(1)

    log(`[Compression] ${output.original_length} → ${output.compressed_length} bytes (${ratio}% reduction)`)
    return output.compressed
  } catch (err) {
    log(`⚠️ Compression unavailable: ${err.message} (using uncompressed)`)
    return diffText
  }
}

function compressContext(contextText) {
  try {
    const jsonPayload = JSON.stringify({
      text: contextText,
      task_type: 'context'
    })

    const result = execSync(`python3 -c "
import sys, json
sys.path.insert(0, '${path.join(__dirname, '../compression')}')
from compression_api import compress_recursive
data = json.loads('${jsonPayload.replace(/'/g, "\\'")}')
result = compress_recursive(data['text'])
print(json.dumps({'compressed': result}))
"`, {
      encoding: 'utf-8',
      timeout: 5000,
      stdio: ['pipe', 'pipe', 'pipe']
    }).trim()

    return JSON.parse(result).compressed
  } catch (err) {
    log(`⚠️ Compression unavailable (using uncompressed)`)
    return contextText
  }
}

module.exports = {
  compressDiff,
  compressContext
}
