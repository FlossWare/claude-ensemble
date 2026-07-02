/**
 * Knowledge Integration - Wires Python knowledge tools into Node.js workflows
 * Integrates: knowledge_sync.py, semantic_chunker.py, task_queue_system.py, fleet_health_monitor.py
 *
 * Usage:
 *   const { shareKnowledge, chunkDocument, queueTask } = require('./knowledge-integration.js');
 *
 *   await shareKnowledge('worker-01', 'discovery', 'Found that X causes Y', 0.9);
 *   const chunks = await chunkDocument(longText, { minSize: 500, maxSize: 1500 });
 */

const { spawn } = require('child_process');
const { promisify } = require('util');
const exec = promisify(require('child_process').exec);
const path = require('path');

const TOOLS_DIR = path.join(__dirname, '..', 'tools');

/**
 * Execute Python tool and return JSON result
 * @private
 */
async function runPythonTool(scriptName, method, args = {}) {
  const scriptPath = path.join(TOOLS_DIR, scriptName);

  // Create Python command to import module and call method
  const pythonCode = `
import sys
import json
sys.path.insert(0, '${TOOLS_DIR}')
from ${scriptName.replace('.py', '')} import *

# Call method with args
result = ${method}(**${JSON.stringify(args)})

# Output as JSON
if hasattr(result, '__dict__'):
    print(json.dumps(result.__dict__))
elif isinstance(result, (dict, list)):
    print(json.dumps(result))
else:
    print(json.dumps({"value": str(result)}))
`.trim();

  try {
    const { stdout, stderr } = await exec(`python3 -c '${pythonCode.replace(/'/g, "'\\''")}'`, {
      timeout: 30000,
      maxBuffer: 10 * 1024 * 1024 // 10MB
    });

    if (stderr && !stderr.includes('Warning')) {
      console.warn(`[knowledge-integration] Python stderr: ${stderr}`);
    }

    return JSON.parse(stdout.trim());
  } catch (error) {
    throw new Error(`Python tool ${scriptName}::${method} failed: ${error.message}`);
  }
}

/**
 * Share knowledge discovery with fleet
 *
 * @param {string} workerId - Worker ID sharing the discovery
 * @param {string} discoveryType - Type of discovery (e.g., 'bug', 'pattern', 'insight')
 * @param {string} content - Discovery content
 * @param {number} confidence - Confidence score (0.0-1.0)
 * @param {Object} [metadata={}] - Additional metadata
 * @returns {Promise<Object>} Discovery record
 */
async function shareKnowledge(workerId, discoveryType, content, confidence, metadata = {}) {
  // Use knowledge_sync.py KnowledgeSync class
  const result = await runPythonTool('knowledge_sync.py', 'share_discovery', {
    worker_id: workerId,
    discovery_type: discoveryType,
    content,
    confidence,
    metadata
  });

  console.log(`[knowledge-integration] ${workerId} shared ${discoveryType}: ${content.substring(0, 50)}...`);
  return result;
}

/**
 * Get verified knowledge from fleet
 *
 * @param {string} [discoveryType] - Filter by type (optional)
 * @param {number} [minConfidence=0.7] - Minimum confidence threshold
 * @returns {Promise<Array>} Verified discoveries
 */
async function getVerifiedKnowledge(discoveryType = null, minConfidence = 0.7) {
  const result = await runPythonTool('knowledge_sync.py', 'get_verified_knowledge', {
    discovery_type: discoveryType,
    min_confidence: minConfidence
  });

  return result.discoveries || [];
}

/**
 * Chunk large document using semantic chunking
 *
 * @param {string} text - Text to chunk
 * @param {Object} [options]
 * @param {number} [options.minSize=500] - Min chunk size
 * @param {number} [options.maxSize=1500] - Max chunk size
 * @param {number} [options.overlap=100] - Overlap between chunks
 * @returns {Promise<Array>} Array of text chunks
 */
async function chunkDocument(text, { minSize = 500, maxSize = 1500, overlap = 100 } = {}) {
  // Escape text for Python string
  const escapedText = text.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n');

  const pythonCode = `
import sys
sys.path.insert(0, '${TOOLS_DIR}')
from semantic_chunker import SemanticChunker
import json

chunker = SemanticChunker(min_chunk_size=${minSize}, max_chunk_size=${maxSize}, overlap_size=${overlap})
chunks = chunker.chunk_text("${escapedText}")
print(json.dumps([{"text": c.text, "start": c.start_idx, "end": c.end_idx} for c in chunks]))
`.trim();

  try {
    const { stdout } = await exec(`python3 -c '${pythonCode.replace(/'/g, "'\\''")}'`, {
      timeout: 60000,
      maxBuffer: 50 * 1024 * 1024
    });

    return JSON.parse(stdout.trim());
  } catch (error) {
    console.warn(`[knowledge-integration] Semantic chunking failed, using simple split: ${error.message}`);
    // Fallback to simple chunking
    const chunks = [];
    for (let i = 0; i < text.length; i += maxSize - overlap) {
      chunks.push({
        text: text.slice(i, i + maxSize),
        start: i,
        end: Math.min(i + maxSize, text.length)
      });
    }
    return chunks;
  }
}

/**
 * Queue task for background processing
 *
 * @param {string} taskType - Task type
 * @param {Object} taskData - Task data
 * @param {number} [priority=5] - Priority (1-10)
 * @returns {Promise<Object>} Task record
 */
async function queueTask(taskType, taskData, priority = 5) {
  const result = await runPythonTool('task_queue_system.py', 'enqueue_task', {
    task_type: taskType,
    task_data: taskData,
    priority
  });

  console.log(`[knowledge-integration] Queued ${taskType} task with priority ${priority}`);
  return result;
}

/**
 * Get next task from queue
 *
 * @param {string} workerId - Worker ID claiming the task
 * @returns {Promise<Object|null>} Task or null if queue empty
 */
async function claimNextTask(workerId) {
  const result = await runPythonTool('task_queue_system.py', 'claim_next_task', {
    worker_id: workerId
  });

  return result.task || null;
}

/**
 * Monitor fleet health
 *
 * @returns {Promise<Object>} Fleet health metrics
 */
async function monitorFleetHealth() {
  const result = await runPythonTool('fleet_health_monitor.py', 'get_fleet_health', {});

  return {
    workers: result.workers || [],
    healthy: result.healthy_count || 0,
    degraded: result.degraded_count || 0,
    failed: result.failed_count || 0,
    totalCpu: result.total_cpu_cores || 0,
    totalRam: result.total_ram_gb || 0
  };
}

module.exports = {
  // Knowledge sync
  shareKnowledge,
  getVerifiedKnowledge,

  // Semantic chunking
  chunkDocument,

  // Task queue
  queueTask,
  claimNextTask,

  // Fleet health
  monitorFleetHealth
};
