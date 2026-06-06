// Chunking Utilities
// Reusable chunking strategies for scalable processing
// Used by code-test, code-solve, code-review, and other workflows

/**
 * Chunks an array into smaller batches
 *
 * @param {Array} items - Items to chunk
 * @param {number} chunkSize - Size of each chunk
 * @returns {Array<Array>} Array of chunks
 */
export function chunkArray(items, chunkSize = 10) {
  const chunks = []
  for (let i = 0; i < items.length; i += chunkSize) {
    chunks.push(items.slice(i, i + chunkSize))
  }
  return chunks
}

/**
 * Calculates optimal chunk size based on time constraints
 *
 * @param {number} totalItems - Total number of items
 * @param {number} estimatedTimePerItem - Estimated seconds per item
 * @param {number} targetChunkTime - Target seconds per chunk (default: 120)
 * @returns {number} Optimal chunk size
 */
export function calculateOptimalChunkSize(
  totalItems,
  estimatedTimePerItem,
  targetChunkTime = 120
) {
  // Calculate items per chunk to hit target time
  const itemsPerChunk = Math.max(1, Math.floor(targetChunkTime / estimatedTimePerItem))

  // Cap at reasonable limits (1-20)
  const cappedSize = Math.min(Math.max(itemsPerChunk, 1), 20)

  // Don't chunk if total is small
  if (totalItems <= cappedSize) {
    return totalItems
  }

  return cappedSize
}

/**
 * Chunks items by context (groups related items together)
 *
 * @param {Array} items - Items to chunk
 * @param {Function} getContext - Function to extract context from item
 * @returns {Array<Object>} Array of chunks with context
 */
export function chunkByContext(items, getContext) {
  const contextGroups = {}

  for (const item of items) {
    const context = getContext(item)
    if (!contextGroups[context]) {
      contextGroups[context] = []
    }
    contextGroups[context].push(item)
  }

  return Object.entries(contextGroups).map(([context, items]) => ({
    context,
    items,
    size: items.length
  }))
}

/**
 * Chunks files by directory (keeps related files together)
 *
 * @param {Array<string>} filePaths - File paths to chunk
 * @param {number} maxFilesPerChunk - Maximum files in a chunk
 * @returns {Array<Object>} Chunks with directory context
 */
export function chunkFilesByDirectory(filePaths, maxFilesPerChunk = 5) {
  const byDirectory = {}

  for (const file of filePaths) {
    const dir = file.split('/').slice(0, -1).join('/') || '.'
    if (!byDirectory[dir]) byDirectory[dir] = []
    byDirectory[dir].push(file)
  }

  // If a directory has too many files, split it
  const chunks = []

  for (const [dir, files] of Object.entries(byDirectory)) {
    if (files.length <= maxFilesPerChunk) {
      chunks.push({ directory: dir, files })
    } else {
      // Split large directories into sub-chunks
      const subChunks = chunkArray(files, maxFilesPerChunk)
      subChunks.forEach((subChunk, idx) => {
        chunks.push({
          directory: `${dir} (part ${idx + 1})`,
          files: subChunk
        })
      })
    }
  }

  return chunks
}

/**
 * Processes chunks with progress tracking
 *
 * @param {Array<Array>} chunks - Array of chunks to process
 * @param {Function} processChunk - Async function to process each chunk
 * @param {Object} options - Processing options
 * @param {Function} options.onProgress - Progress callback (chunkIndex, total)
 * @param {Function} options.onChunkComplete - Chunk completion callback
 * @param {boolean} options.continueOnError - Continue if chunk fails (default: true)
 * @returns {Promise<Array>} All results from all chunks
 */
export async function processChunksWithProgress(chunks, processChunk, options = {}) {
  const {
    onProgress = null,
    onChunkComplete = null,
    continueOnError = true
  } = options

  const allResults = []

  for (let i = 0; i < chunks.length; i++) {
    const chunk = chunks[i]

    if (onProgress) {
      onProgress(i, chunks.length, chunk)
    }

    try {
      const chunkResults = await processChunk(chunk, i, chunks.length)
      allResults.push(...(chunkResults || []))

      if (onChunkComplete) {
        onChunkComplete(i, chunks.length, chunkResults, null)
      }
    } catch (error) {
      if (onChunkComplete) {
        onChunkComplete(i, chunks.length, null, error)
      }

      if (!continueOnError) {
        throw error
      }

      // Log error but continue with next chunk
      console.error(`Chunk ${i + 1}/${chunks.length} failed:`, error.message)
    }
  }

  return allResults
}

/**
 * Adaptive chunking - adjusts chunk size based on processing time
 *
 * @param {Array} items - Items to process
 * @param {Function} processChunk - Processing function
 * @param {Object} options - Options
 * @returns {Promise<Array>} Results
 */
export async function processWithAdaptiveChunking(items, processChunk, options = {}) {
  const {
    initialChunkSize = 10,
    targetTime = 120, // seconds
    minChunkSize = 1,
    maxChunkSize = 50
  } = options

  let currentChunkSize = initialChunkSize
  const allResults = []
  let offset = 0

  while (offset < items.length) {
    const chunk = items.slice(offset, offset + currentChunkSize)
    const startTime = Date.now()

    const chunkResults = await processChunk(chunk, offset, items.length)
    allResults.push(...(chunkResults || []))

    const elapsedTime = (Date.now() - startTime) / 1000

    // Adjust chunk size based on actual time
    if (elapsedTime > 0) {
      const itemsPerSecond = chunk.length / elapsedTime
      const optimalSize = Math.floor(itemsPerSecond * targetTime)
      currentChunkSize = Math.min(Math.max(optimalSize, minChunkSize), maxChunkSize)
    }

    offset += chunk.length

    console.log(`Adaptive chunking: processed ${offset}/${items.length}, next chunk size: ${currentChunkSize}`)
  }

  return allResults
}

/**
 * Paginated processing for database-style queries
 *
 * @param {Function} fetchPage - Function to fetch a page (offset, limit) => items
 * @param {Function} processPage - Function to process items
 * @param {Object} options - Pagination options
 * @returns {Promise<Array>} All results
 */
export async function processPaginated(fetchPage, processPage, options = {}) {
  const {
    pageSize = 100,
    maxPages = Infinity,
    onProgress = null
  } = options

  const allResults = []
  let pageIndex = 0
  let hasMore = true

  while (hasMore && pageIndex < maxPages) {
    const offset = pageIndex * pageSize
    const page = await fetchPage(offset, pageSize)

    if (!page || page.length === 0) {
      hasMore = false
      break
    }

    const pageResults = await processPage(page, pageIndex, offset)
    allResults.push(...(pageResults || []))

    if (onProgress) {
      onProgress(pageIndex, allResults.length, page.length)
    }

    hasMore = page.length === pageSize
    pageIndex++
  }

  return allResults
}

// ============================================================================
// INLINE VERSION (for workflows that can't use imports)
// ============================================================================

export const INLINE_CHUNKING = `
// Inline chunking utilities (copy into workflows)

function chunkArray(items, chunkSize = 10) {
  const chunks = []
  for (let i = 0; i < items.length; i += chunkSize) {
    chunks.push(items.slice(i, i + chunkSize))
  }
  return chunks
}

function calculateOptimalChunkSize(totalItems, estimatedTimePerItem, targetChunkTime = 120) {
  const itemsPerChunk = Math.max(1, Math.floor(targetChunkTime / estimatedTimePerItem))
  return Math.min(Math.max(itemsPerChunk, 1), 20)
}

async function processChunksWithProgress(chunks, processChunk, options = {}) {
  const { onProgress = null, continueOnError = true } = options
  const allResults = []

  for (let i = 0; i < chunks.length; i++) {
    if (onProgress) onProgress(i, chunks.length, chunks[i])

    try {
      const chunkResults = await processChunk(chunks[i], i, chunks.length)
      allResults.push(...(chunkResults || []))
    } catch (error) {
      if (!continueOnError) throw error
      console.error(\`Chunk \${i + 1}/\${chunks.length} failed:\`, error.message)
    }
  }

  return allResults
}
`
