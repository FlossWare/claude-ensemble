/**
 * Semantic Chunker Adapter - Node.js interface to Python semantic_chunker
 * Provides intelligent text chunking that preserves semantic boundaries
 *
 * Usage:
 *   const { chunkText, chunkTextStream } = require('./semantic-chunker-adapter.js');
 *
 *   const chunks = await chunkText('large document text...');
 *   // Returns array of chunk objects with content, metadata, overlap
 *
 *   // For very large texts, use streaming:
 *   for await (const chunk of chunkTextStream('huge document...')) {
 *     console.log(`Chunk ${chunk.index}: ${chunk.char_count} chars`);
 *   }
 */

const { execFileSync, spawn } = require('child_process');
const path = require('path');

// Path to semantic_chunker.py
const CHUNKER_PATH = path.join(__dirname, '..', 'tools', 'semantic_chunker.py');

/**
 * Chunk text using semantic boundaries (synchronous)
 *
 * @param {string} text - Text to chunk
 * @param {Object} options - Chunking options
 * @param {number} options.minChunkSize - Minimum characters per chunk (default: 500)
 * @param {number} options.maxChunkSize - Maximum characters per chunk (default: 1500)
 * @param {number} options.overlapSize - Characters to overlap between chunks (default: 100)
 * @returns {Array<Object>} Array of chunk objects
 */
function chunkText(text, options = {}) {
  const {
    minChunkSize = 500,
    maxChunkSize = 1500,
    overlapSize = 100
  } = options;

  // Create Python script to run chunker
  const pythonScript = `
import sys
import json
sys.path.insert(0, '${path.dirname(CHUNKER_PATH)}')
from semantic_chunker import SemanticChunker

chunker = SemanticChunker(
    min_chunk_size=${minChunkSize},
    max_chunk_size=${maxChunkSize},
    overlap_size=${overlapSize}
)

text = sys.stdin.read()
chunks = chunker.chunk_text(text)
print(json.dumps(chunks))
`;

  try {
    const result = execFileSync('python3', ['-c', pythonScript], {
      input: text,
      encoding: 'utf8',
      maxBuffer: 10 * 1024 * 1024 // 10MB buffer
    });

    return JSON.parse(result);
  } catch (error) {
    console.error('Error chunking text:', error.message);
    // Fallback: simple chunking
    return fallbackChunk(text, maxChunkSize);
  }
}

/**
 * Chunk text using semantic boundaries (streaming, async)
 * Memory-efficient for very large texts
 *
 * @param {string} text - Text to chunk
 * @param {Object} options - Chunking options
 * @returns {AsyncGenerator<Object>} Async generator yielding chunks
 */
async function* chunkTextStream(text, options = {}) {
  const {
    minChunkSize = 500,
    maxChunkSize = 1500,
    overlapSize = 100
  } = options;

  // Create Python script that streams chunks
  const pythonScript = `
import sys
import json
sys.path.insert(0, '${path.dirname(CHUNKER_PATH)}')
from semantic_chunker import SemanticChunker

chunker = SemanticChunker(
    min_chunk_size=${minChunkSize},
    max_chunk_size=${maxChunkSize},
    overlap_size=${overlapSize}
)

text = sys.stdin.read()
for chunk in chunker.chunk_text_stream(text):
    print(json.dumps(chunk))
    sys.stdout.flush()
`;

  return new Promise((resolve, reject) => {
    const python = spawn('python3', ['-c', pythonScript]);

    let buffer = '';
    const chunks = [];

    python.stdout.on('data', (data) => {
      buffer += data.toString();
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.trim()) {
          try {
            chunks.push(JSON.parse(line));
          } catch (e) {
            console.error('Error parsing chunk:', e.message);
          }
        }
      }
    });

    python.stderr.on('data', (data) => {
      console.error('Python stderr:', data.toString());
    });

    python.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`Python process exited with code ${code}`));
      } else {
        resolve(chunks);
      }
    });

    python.stdin.write(text);
    python.stdin.end();
  }).then(async function* () {
    for (const chunk of chunks) {
      yield chunk;
    }
  });
}

/**
 * Fallback chunking (simple split by size)
 * Used when Python chunker is unavailable
 */
function fallbackChunk(text, maxSize = 1500) {
  const chunks = [];
  const paragraphs = text.split(/\n\s*\n/);

  let current = '';
  let index = 0;

  for (const para of paragraphs) {
    if (current.length + para.length > maxSize && current) {
      chunks.push({
        index: index++,
        content: current,
        overlap_prefix: '',
        overlap_suffix: '',
        char_count: current.length,
        has_code: false,
        language: null,
        chunk_type: 'text'
      });
      current = para;
    } else {
      current += (current ? '\n\n' : '') + para;
    }
  }

  if (current) {
    chunks.push({
      index: index,
      content: current,
      overlap_prefix: '',
      overlap_suffix: '',
      char_count: current.length,
      has_code: false,
      language: null,
      chunk_type: 'text'
    });
  }

  return chunks;
}

/**
 * Analyze text to detect if it's primarily code
 */
function analyzeText(text) {
  const pythonScript = `
import sys
import json
sys.path.insert(0, '${path.dirname(CHUNKER_PATH)}')
from semantic_chunker import SemanticChunker

chunker = SemanticChunker()
text = sys.stdin.read()
is_code = chunker.is_code_block(text)
language = chunker.detect_language(text) if is_code else None

print(json.dumps({
    'is_code': is_code,
    'language': language,
    'char_count': len(text)
}))
`;

  try {
    const result = execFileSync('python3', ['-c', pythonScript], {
      input: text,
      encoding: 'utf8',
      maxBuffer: 1024 * 1024 // 1MB buffer
    });

    return JSON.parse(result);
  } catch (error) {
    console.error('Error analyzing text:', error.message);
    return { is_code: false, language: null, char_count: text.length };
  }
}

module.exports = {
  chunkText,
  chunkTextStream,
  analyzeText
};
