// INLINE File Analyzer
// Uses Read tool instead of Bash to avoid permission prompts
// Copy these functions directly into your workflow

// ============================================================================
// FILE READING WITHOUT BASH
// ============================================================================

async function readFileLines(agent, filepath, startLine, endLine) {
  // Use Read tool which doesn't trigger Bash prompts
  const offset = startLine > 0 ? startLine - 1 : 0
  const limit = endLine ? endLine - startLine + 1 : undefined

  const content = await agent(`Read file: ${filepath}

Lines ${startLine} to ${endLine || 'end'}

Return the file content.`, {
    label: `Read ${filepath}:${startLine}-${endLine || 'end'}`,
    schema: {
      type: 'object',
      properties: {
        content: { type: 'string' },
        line_count: { type: 'number' }
      }
    }
  })

  return content
}

async function analyzeFile(agent, filepath) {
  // Read entire file without Bash
  const content = await agent(`Analyze file: ${filepath}

Read the file and return:
1. Total line count
2. File content
3. Key sections

Return structured data.`, {
    label: `Analyze ${filepath}`,
    schema: {
      type: 'object',
      properties: {
        filepath: { type: 'string' },
        total_lines: { type: 'number' },
        content: { type: 'string' },
        sections: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              line_start: { type: 'number' },
              line_end: { type: 'number' }
            }
          }
        }
      }
    }
  })

  return content
}

async function findPattern(agent, filepath, pattern) {
  // Search for pattern without grep
  const result = await agent(`Search file: ${filepath}

Find all occurrences of pattern: "${pattern}"

Return line numbers and context.`, {
    label: `Find "${pattern}" in ${filepath}`,
    schema: {
      type: 'object',
      properties: {
        matches: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              line_number: { type: 'number' },
              line_content: { type: 'string' },
              context_before: { type: 'string' },
              context_after: { type: 'string' }
            }
          }
        },
        total_matches: { type: 'number' }
      }
    }
  })

  return result
}

async function countLinesInRange(agent, filepath, startLine, endLine) {
  // Count lines without sed/wc
  const lines = await readFileLines(agent, filepath, startLine, endLine)

  if (lines.content) {
    const lineCount = lines.content.split('\n').length
    return lineCount
  }

  return lines.line_count || 0
}

// ============================================================================
// USAGE EXAMPLE
// ============================================================================

/*

// Instead of: await agent(`Execute: sed -n '107,120p' file.js | wc -l`, ...)
// Use:
const lineCount = await countLinesInRange(agent, 'file.js', 107, 120)

// Instead of: await agent(`Execute: cat file.js`, ...)
// Use:
const content = await analyzeFile(agent, 'file.js')

// Instead of: await agent(`Execute: grep -n "pattern" file.js`, ...)
// Use:
const matches = await findPattern(agent, 'file.js', 'pattern')

*/
