/**
 * Caching Bridge
 * Calls Python caching API from JavaScript
 * Tracks prompt cache hits/misses for token cost optimization
 */

const { execSync } = require('child_process')
const path = require('path')
const fs = require('fs')

class CachingBridge {
  constructor(workflowName) {
    this.workflowName = workflowName
    this.metricsFile = path.join(
      require('os').homedir(),
      `.claude/cache-metrics-${workflowName}-${Date.now()}.json`
    )
    this.initializeMetrics()
  }

  initializeMetrics() {
    try {
      const jsonPayload = JSON.stringify({
        workflow_name: this.workflowName,
        metrics_file: this.metricsFile
      })

      execSync(`python3 -c "
import sys, json
sys.path.insert(0, '${path.join(__dirname, '../caching')}')
from cache_metrics import CacheMetricsTracker
data = json.loads('${jsonPayload.replace(/'/g, "\\'")}')
tracker = CacheMetricsTracker(data['workflow_name'])
print(json.dumps({'status': 'initialized', 'file': data['metrics_file']}))
"`, {
        encoding: 'utf-8',
        timeout: 3000,
        stdio: ['pipe', 'pipe', 'pipe']
      })

      log(`[Caching] Initialized metrics for ${this.workflowName}`)
    } catch (err) {
      log(`⚠️ Caching initialization failed: ${err.message}`)
    }
  }

  logCacheRequest(requestType, inputTokens, outputTokens, cacheHit = false, cacheTokens = 0) {
    try {
      const jsonPayload = JSON.stringify({
        request_type: requestType,
        input_tokens: inputTokens,
        output_tokens: outputTokens,
        cache_hit: cacheHit,
        cache_tokens: cacheTokens,
        metrics_file: this.metricsFile
      })

      execSync(`python3 -c "
import sys, json
sys.path.insert(0, '${path.join(__dirname, '../caching')}')
from cache_metrics import CacheMetricsTracker
data = json.loads('${jsonPayload.replace(/'/g, "\\'")}')
tracker = CacheMetricsTracker()
if data['cache_hit']:
  tracker.log_cached_request(
    input_tokens=data['input_tokens'],
    output_tokens=data['output_tokens'],
    cache_read_tokens=data['cache_tokens']
  )
else:
  tracker.log_baseline_request(
    input_tokens=data['input_tokens'],
    output_tokens=data['output_tokens']
  )
print(json.dumps({'logged': True}))
"`, {
        encoding: 'utf-8',
        timeout: 3000,
        stdio: ['pipe', 'pipe', 'pipe']
      })

      const status = cacheHit ? 'HIT' : 'MISS'
      log(`[Caching] ${requestType}: ${status} (${inputTokens}→${outputTokens} tokens)`)
    } catch (err) {
      // Silent fail - caching is optional
    }
  }

  generateReport() {
    try {
      const result = execSync(`python3 -c "
import sys, json
sys.path.insert(0, '${path.join(__dirname, '../caching')}')
from cache_metrics import CacheMetricsTracker
tracker = CacheMetricsTracker('${this.workflowName}')
report = tracker.generate_report()
print(json.dumps({
  'cache_hits': report.get('cache_hits', 0),
  'cache_misses': report.get('cache_misses', 0),
  'total_tokens_saved': report.get('total_tokens_saved', 0),
  'total_cost_saved': report.get('total_cost_saved', 0)
}))
"`, {
        encoding: 'utf-8',
        timeout: 5000,
        stdio: ['pipe', 'pipe', 'pipe']
      }).trim()

      return JSON.parse(result)
    } catch (err) {
      log(`⚠️ Could not generate cache report: ${err.message}`)
      return { cache_hits: 0, cache_misses: 0, total_tokens_saved: 0 }
    }
  }
}

module.exports = CachingBridge
