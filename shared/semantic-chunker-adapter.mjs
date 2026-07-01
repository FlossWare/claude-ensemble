/**
 * Semantic Chunker Adapter - ESM version for modern workflows
 * Provides intelligent text chunking that preserves semantic boundaries
 *
 * Usage:
 *   import { chunkText, analyzeText } from './semantic-chunker-adapter.mjs';
 *
 *   const chunks = await chunkText('large document text...');
 */

import { execFileSync, spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Path to semantic_chunker.py
const CHUNKER_PATH = join(__dirname, '..', 'tools', 'semantic_chunker.py');

/**
 * Chunk text using semantic boundaries
 *
 * @param {string} text - Text to chunk
 * @param {Object} options - Chunking options
 * @returns {Array<Object>} Array of chunk objects
 */
export function chunkText(text, options = {}) {
  const {
    minChunkSize = 500,
    maxChunkSize = 1500,
    overlapSize = 100
  } = options;

  const pythonScript = `
import sys
import json
sys.path.insert(0, '${dirname(CHUNKER_PATH)}')
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
    return fallbackChunk(text, maxChunkSize);
  }
}

/**
 * Analyze text to detect if it's primarily code
 */
export function analyzeText(text) {
  const pythonScript = `
import sys
import json
sys.path.insert(0, '${dirname(CHUNKER_PATH)}')
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
      maxBuffer: 1024 * 1024
    });

    return JSON.parse(result);
  } catch (error) {
    console.error('Error analyzing text:', error.message);
    return { is_code: false, language: null, char_count: text.length };
  }
}

/**
 * Fallback chunking for when Python is unavailable
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

export default { chunkText, analyzeText };
