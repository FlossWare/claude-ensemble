/**
 * code-ast-analysis.js - Standalone AST parsing and structural analysis
 *
 * Utility skill for extracting structural information from source code.
 * Parses code using tree-sitter when available, with a comprehensive
 * regex fallback for JavaScript, TypeScript, and Python.
 *
 * Designed to be reusable by other skills (code-review, code-security,
 * code-sdlc) for structural understanding prior to analysis.
 *
 * @returns {{
 *   status: 'complete' | 'partial' | 'failed',
 *   parser: 'tree-sitter' | 'regex',
 *   language: string,
 *   files_analyzed: number,
 *   functions: Array<{name: string, file: string, line: number, params: string[], returnType: string|null, async: boolean, exported: boolean, generator: boolean, complexity: {cyclomatic: number, cognitive: number}}>,
 *   classes: Array<{name: string, file: string, line: number, exported: boolean, extends: string|null, implements: string[], methods: Array<{name: string, line: number, visibility: string, static: boolean, async: boolean, params: string[], complexity: {cyclomatic: number, cognitive: number}}>, properties: string[]}>,
 *   dependencies: {imports: Array<{source: string, specifiers: string[], file: string, line: number, type: string}>, exports: Array<{name: string, file: string, line: number, type: string}>, call_graph: Array<{caller: string, callee: string, file: string, line: number}>},
 *   patterns: Array<{name: string, confidence: number, evidence: string[], files: string[]}>,
 *   summary: {total_functions: number, total_classes: number, total_imports: number, avg_cyclomatic: number, avg_cognitive: number, max_cyclomatic: {name: string, value: number}, max_cognitive: {name: string, value: number}, patterns_detected: string[]}
 * }}
 */
export const meta = {
  name: 'code-ast-analysis',
  description: 'Parse code structure via AST (tree-sitter or regex fallback) -- extract functions, classes, complexity, dependencies, patterns',
  whenToUse: 'When you need structural code analysis: function/class extraction, complexity metrics, dependency graphs, or design pattern detection. Reusable by code-review, code-security, and code-sdlc.',
  phases: [
    { title: 'Setup', detail: 'Check tree-sitter availability, detect language' },
    { title: 'Parse', detail: 'AST parsing with tree-sitter or regex fallback' },
    { title: 'Analyze', detail: 'Complexity metrics (cyclomatic, cognitive)' },
    { title: 'Dependencies', detail: 'Import/export graph, call graph' },
    { title: 'Patterns', detail: 'Design pattern detection' },
    { title: 'Output', detail: 'Structured JSON result' },
  ],
}

export default async function({ args, phase, log, agent, parallel }) {

// ============================================================================
// OUTPUT SCHEMAS (exported conceptually for consumer skills)
// ============================================================================

const SCHEMAS = {
  FUNCTION: {
    type: 'object',
    properties: {
      name: { type: 'string' },
      file: { type: 'string' },
      line: { type: 'number' },
      params: { type: 'array', items: { type: 'string' } },
      returnType: { type: ['string', 'null'] },
      async: { type: 'boolean' },
      exported: { type: 'boolean' },
      generator: { type: 'boolean' },
      complexity: {
        type: 'object',
        properties: {
          cyclomatic: { type: 'number' },
          cognitive: { type: 'number' },
        },
      },
    },
    required: ['name', 'file', 'line', 'params', 'complexity'],
  },

  CLASS: {
    type: 'object',
    properties: {
      name: { type: 'string' },
      file: { type: 'string' },
      line: { type: 'number' },
      exported: { type: 'boolean' },
      extends: { type: ['string', 'null'] },
      implements: { type: 'array', items: { type: 'string' } },
      methods: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            line: { type: 'number' },
            visibility: { type: 'string', enum: ['public', 'private', 'protected'] },
            static: { type: 'boolean' },
            async: { type: 'boolean' },
            params: { type: 'array', items: { type: 'string' } },
            complexity: {
              type: 'object',
              properties: {
                cyclomatic: { type: 'number' },
                cognitive: { type: 'number' },
              },
            },
          },
        },
      },
      properties: { type: 'array', items: { type: 'string' } },
    },
    required: ['name', 'file', 'line'],
  },

  IMPORT: {
    type: 'object',
    properties: {
      source: { type: 'string' },
      specifiers: { type: 'array', items: { type: 'string' } },
      file: { type: 'string' },
      line: { type: 'number' },
      type: { type: 'string', enum: ['esm', 'cjs', 'dynamic', 'python', 'go', 'java'] },
    },
    required: ['source', 'file', 'line', 'type'],
  },

  PATTERN: {
    type: 'object',
    properties: {
      name: { type: 'string' },
      confidence: { type: 'number', minimum: 0, maximum: 100 },
      evidence: { type: 'array', items: { type: 'string' } },
      files: { type: 'array', items: { type: 'string' } },
    },
    required: ['name', 'confidence', 'evidence'],
  },
}

// ============================================================================
// LANGUAGE DETECTION
// ============================================================================

const LANGUAGE_EXTENSIONS = {
  '.js': 'javascript',
  '.mjs': 'javascript',
  '.cjs': 'javascript',
  '.jsx': 'javascript',
  '.ts': 'typescript',
  '.tsx': 'typescript',
  '.mts': 'typescript',
  '.cts': 'typescript',
  '.py': 'python',
  '.pyw': 'python',
  '.java': 'java',
  '.go': 'go',
}

const SUPPORTED_LANGUAGES = ['javascript', 'typescript', 'python', 'java', 'go']

function detectLanguageFromExt(filename) {
  for (const [ext, lang] of Object.entries(LANGUAGE_EXTENSIONS)) {
    if (filename.endsWith(ext)) return lang
  }
  return null
}

// ============================================================================
// REGEX-BASED PARSERS (fallback when tree-sitter is unavailable)
// ============================================================================

/**
 * Parse JavaScript/TypeScript source using regex patterns.
 * Handles: functions, arrow functions, classes, methods, imports, exports.
 */
function parseJavaScriptRegex(source, filename) {
  const lines = source.split('\n')
  const functions = []
  const classes = []
  const imports = []
  const exports = []
  const callEdges = []

  // Track context for nesting
  let currentClass = null
  let braceDepth = 0
  let classStartDepth = -1

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const lineNum = i + 1
    const trimmed = line.trim()

    // Skip comments and empty lines
    if (trimmed.startsWith('//') || trimmed === '' || trimmed.startsWith('*') || trimmed.startsWith('/*')) {
      continue
    }

    // Track brace depth for class scope
    const openBraces = (line.match(/\{/g) || []).length
    const closeBraces = (line.match(/\}/g) || []).length
    braceDepth += openBraces - closeBraces

    // End of current class
    if (currentClass && braceDepth <= classStartDepth) {
      classes.push(currentClass)
      currentClass = null
      classStartDepth = -1
    }

    // --- IMPORTS ---

    // ESM: import { a, b } from 'module'
    // ESM: import defaultExport from 'module'
    // ESM: import * as name from 'module'
    // ESM: import 'module' (side effect)
    const esmImportMatch = trimmed.match(
      /^import\s+(?:type\s+)?(?:(\{[^}]*\})|(\*\s+as\s+\w+)|(\w+))?\s*(?:,\s*(?:(\{[^}]*\})|(\*\s+as\s+\w+)))?(?:\s+from\s+)?['"]([^'"]+)['"]/
    )
    if (esmImportMatch) {
      const specParts = []
      // Named imports: { a, b }
      if (esmImportMatch[1]) {
        esmImportMatch[1].replace(/[{}]/g, '').split(',').forEach(s => {
          const clean = s.trim().split(/\s+as\s+/).pop().trim()
          if (clean) specParts.push(clean)
        })
      }
      // Namespace import: * as name
      if (esmImportMatch[2]) specParts.push(esmImportMatch[2].trim())
      if (esmImportMatch[5]) specParts.push(esmImportMatch[5].trim())
      // Default import
      if (esmImportMatch[3]) specParts.push(esmImportMatch[3].trim())
      // Named imports after default
      if (esmImportMatch[4]) {
        esmImportMatch[4].replace(/[{}]/g, '').split(',').forEach(s => {
          const clean = s.trim().split(/\s+as\s+/).pop().trim()
          if (clean) specParts.push(clean)
        })
      }
      const source = esmImportMatch[6]
      if (source) {
        imports.push({
          source,
          specifiers: specParts,
          file: filename,
          line: lineNum,
          type: 'esm',
        })
      }
    }

    // CJS: const x = require('module')
    const cjsMatch = trimmed.match(
      /(?:const|let|var)\s+(?:(\{[^}]*\})|(\w+))\s*=\s*require\s*\(\s*['"]([^'"]+)['"]\s*\)/
    )
    if (cjsMatch) {
      const specParts = []
      if (cjsMatch[1]) {
        cjsMatch[1].replace(/[{}]/g, '').split(',').forEach(s => {
          const clean = s.trim().split(/\s*:\s*/).shift().trim()
          if (clean) specParts.push(clean)
        })
      }
      if (cjsMatch[2]) specParts.push(cjsMatch[2])
      imports.push({
        source: cjsMatch[3],
        specifiers: specParts,
        file: filename,
        line: lineNum,
        type: 'cjs',
      })
    }

    // Dynamic import: import('module')
    const dynMatch = trimmed.match(/import\s*\(\s*['"]([^'"]+)['"]\s*\)/)
    if (dynMatch && !esmImportMatch) {
      imports.push({
        source: dynMatch[1],
        specifiers: [],
        file: filename,
        line: lineNum,
        type: 'dynamic',
      })
    }

    // --- EXPORTS ---

    // export default, export const, export function, export class
    const exportMatch = trimmed.match(
      /^export\s+(default\s+)?(?:(const|let|var|function\*?|class|async\s+function\*?)\s+)?(\w+)?/
    )
    if (exportMatch) {
      const name = exportMatch[3] || (exportMatch[1] ? 'default' : 'unknown')
      const type = exportMatch[2] || 'default'
      exports.push({
        name,
        file: filename,
        line: lineNum,
        type: type.replace(/\s+/g, '_'),
      })
    }

    // module.exports
    if (trimmed.match(/^module\.exports\s*=/)) {
      exports.push({
        name: 'module.exports',
        file: filename,
        line: lineNum,
        type: 'cjs',
      })
    }

    // --- CLASSES ---

    const classMatch = trimmed.match(
      /^(export\s+)?(default\s+)?(abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?/
    )
    if (classMatch) {
      const implList = classMatch[6]
        ? classMatch[6].split(',').map(s => s.trim()).filter(Boolean)
        : []
      currentClass = {
        name: classMatch[4],
        file: filename,
        line: lineNum,
        exported: !!classMatch[1],
        extends: classMatch[5] || null,
        implements: implList,
        methods: [],
        properties: [],
      }
      classStartDepth = braceDepth - openBraces
    }

    // --- METHODS (inside class) ---

    if (currentClass) {
      // Method: async? static? get/set? name(params) { or name = (params) => {
      const methodMatch = trimmed.match(
        /^(public\s+|private\s+|protected\s+)?(static\s+)?(async\s+)?(?:get\s+|set\s+)?(\w+)\s*\(([^)]*)\)\s*(?::\s*\S+\s*)?[{]/
      )
      if (methodMatch && methodMatch[4] !== 'if' && methodMatch[4] !== 'for' && methodMatch[4] !== 'while' && methodMatch[4] !== 'switch') {
        const visibility = (methodMatch[1] || 'public').trim()
        const params = methodMatch[5]
          ? methodMatch[5].split(',').map(p => p.trim().split(/[=:]/)[0].trim()).filter(Boolean)
          : []
        currentClass.methods.push({
          name: methodMatch[4],
          line: lineNum,
          visibility,
          static: !!methodMatch[2],
          async: !!methodMatch[3],
          params,
          complexity: { cyclomatic: 1, cognitive: 0 }, // computed later
        })
      }

      // Property: name: type or name = value (not a method)
      const propMatch = trimmed.match(
        /^(public\s+|private\s+|protected\s+)?(static\s+)?(readonly\s+)?(\w+)\s*[=:]\s*(?![({])/
      )
      if (propMatch && !trimmed.includes('(') && propMatch[4] !== 'constructor') {
        currentClass.properties.push(propMatch[4])
      }
    }

    // --- STANDALONE FUNCTIONS ---

    if (!currentClass) {
      // function declaration: export? async? function* name(params)
      const fnDeclMatch = trimmed.match(
        /^(export\s+)?(default\s+)?(async\s+)?function\s*(\*)?\s*(\w+)?\s*\(([^)]*)\)\s*(?::\s*[^{]+)?\s*\{?/
      )
      if (fnDeclMatch) {
        const params = fnDeclMatch[6]
          ? fnDeclMatch[6].split(',').map(p => p.trim().split(/[=:]/)[0].trim()).filter(Boolean)
          : []
        functions.push({
          name: fnDeclMatch[5] || (fnDeclMatch[2] ? 'default' : 'anonymous'),
          file: filename,
          line: lineNum,
          params,
          returnType: null,
          async: !!fnDeclMatch[3],
          exported: !!fnDeclMatch[1],
          generator: !!fnDeclMatch[4],
          complexity: { cyclomatic: 1, cognitive: 0 },
        })
      }

      // Arrow function assigned to const/let/var: export? const name = (async?) (params) =>
      const arrowMatch = trimmed.match(
        /^(export\s+)?(const|let|var)\s+(\w+)\s*(?::\s*[^=]+)?\s*=\s*(async\s+)?(?:\(([^)]*)\)|(\w+))\s*=>/
      )
      if (arrowMatch) {
        const paramStr = arrowMatch[5] || arrowMatch[6] || ''
        const params = paramStr
          ? paramStr.split(',').map(p => p.trim().split(/[=:]/)[0].trim()).filter(Boolean)
          : []
        functions.push({
          name: arrowMatch[3],
          file: filename,
          line: lineNum,
          params,
          returnType: null,
          async: !!arrowMatch[4],
          exported: !!arrowMatch[1],
          generator: false,
          complexity: { cyclomatic: 1, cognitive: 0 },
        })
      }
    }

    // --- CALL GRAPH (lightweight) ---
    // Detect function calls: name(args)
    const callMatches = trimmed.matchAll(/(?<!\w)(\w+)\s*\(/g)
    for (const cm of callMatches) {
      const callee = cm[1]
      // Filter out language keywords and common false positives
      const keywords = new Set([
        'if', 'for', 'while', 'switch', 'catch', 'return', 'throw',
        'typeof', 'instanceof', 'new', 'delete', 'void', 'import',
        'export', 'const', 'let', 'var', 'function', 'class',
        'require', 'console', 'Array', 'Object', 'String', 'Number',
        'Boolean', 'Symbol', 'Map', 'Set', 'Promise', 'Error',
        'parseInt', 'parseFloat', 'JSON', 'Math',
      ])
      if (!keywords.has(callee)) {
        // Determine the containing function/method
        let caller = '<module>'
        if (currentClass) {
          const lastMethod = currentClass.methods[currentClass.methods.length - 1]
          if (lastMethod) caller = `${currentClass.name}.${lastMethod.name}`
        } else if (functions.length > 0) {
          caller = functions[functions.length - 1].name
        }
        callEdges.push({
          caller,
          callee,
          file: filename,
          line: lineNum,
        })
      }
    }
  }

  // Flush any remaining class
  if (currentClass) {
    classes.push(currentClass)
  }

  return { functions, classes, imports, exports, callEdges }
}

/**
 * Parse Python source using regex patterns.
 */
function parsePythonRegex(source, filename) {
  const lines = source.split('\n')
  const functions = []
  const classes = []
  const imports = []
  const exports = []
  const callEdges = []

  let currentClass = null
  let currentIndent = -1

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const lineNum = i + 1
    const trimmed = line.trim()

    if (trimmed === '' || trimmed.startsWith('#')) continue

    // Calculate indentation (spaces)
    const indent = line.search(/\S/)

    // Check if we exited a class
    if (currentClass && indent <= currentIndent && trimmed !== '') {
      classes.push(currentClass)
      currentClass = null
      currentIndent = -1
    }

    // --- IMPORTS ---

    // import module
    const importMatch = trimmed.match(/^import\s+(\S+)(?:\s+as\s+(\w+))?/)
    if (importMatch) {
      imports.push({
        source: importMatch[1],
        specifiers: [importMatch[2] || importMatch[1]],
        file: filename,
        line: lineNum,
        type: 'python',
      })
    }

    // from module import names
    const fromImportMatch = trimmed.match(/^from\s+(\S+)\s+import\s+(.+)/)
    if (fromImportMatch) {
      const specifiers = fromImportMatch[2]
        .split(',')
        .map(s => s.trim().split(/\s+as\s+/).pop().trim())
        .filter(s => s && s !== '(')
      imports.push({
        source: fromImportMatch[1],
        specifiers,
        file: filename,
        line: lineNum,
        type: 'python',
      })
    }

    // --- CLASSES ---

    const classMatch = trimmed.match(/^class\s+(\w+)(?:\(([^)]*)\))?/)
    if (classMatch) {
      const bases = classMatch[2]
        ? classMatch[2].split(',').map(s => s.trim()).filter(Boolean)
        : []
      currentClass = {
        name: classMatch[1],
        file: filename,
        line: lineNum,
        exported: !classMatch[1].startsWith('_'),
        extends: bases[0] || null,
        implements: bases.slice(1),
        methods: [],
        properties: [],
      }
      currentIndent = indent
    }

    // --- FUNCTIONS / METHODS ---

    const defMatch = trimmed.match(
      /^(async\s+)?def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*(\S+))?\s*:/
    )
    if (defMatch) {
      const name = defMatch[2]
      const rawParams = defMatch[3]
      const retType = defMatch[4] || null
      const params = rawParams
        ? rawParams.split(',').map(p => p.trim().split(/[=:]/)[0].trim()).filter(p => p && p !== 'self' && p !== 'cls')
        : []
      const isAsync = !!defMatch[1]

      if (currentClass) {
        // Method inside class
        let visibility = 'public'
        if (name.startsWith('__') && !name.endsWith('__')) visibility = 'private'
        else if (name.startsWith('_')) visibility = 'protected'

        currentClass.methods.push({
          name,
          line: lineNum,
          visibility,
          static: trimmed.includes('@staticmethod') || false,
          async: isAsync,
          params,
          complexity: { cyclomatic: 1, cognitive: 0 },
        })
      } else {
        // Standalone function
        functions.push({
          name,
          file: filename,
          line: lineNum,
          params,
          returnType: retType,
          async: isAsync,
          exported: !name.startsWith('_'),
          generator: false,
          complexity: { cyclomatic: 1, cognitive: 0 },
        })
      }
    }

    // --- __all__ exports ---

    const allMatch = trimmed.match(/^__all__\s*=\s*\[([^\]]*)\]/)
    if (allMatch) {
      allMatch[1].split(',').forEach(s => {
        const name = s.trim().replace(/['"]/g, '')
        if (name) exports.push({ name, file: filename, line: lineNum, type: 'python_all' })
      })
    }

    // --- CALL GRAPH (lightweight) ---
    const callMatches = trimmed.matchAll(/(?<!\w)(\w+)\s*\(/g)
    for (const cm of callMatches) {
      const callee = cm[1]
      const pyKeywords = new Set([
        'if', 'for', 'while', 'def', 'class', 'import', 'from', 'return',
        'print', 'len', 'range', 'int', 'str', 'float', 'list', 'dict',
        'set', 'tuple', 'type', 'isinstance', 'issubclass', 'super',
        'property', 'staticmethod', 'classmethod', 'enumerate', 'zip',
        'map', 'filter', 'sorted', 'reversed', 'hasattr', 'getattr',
        'setattr', 'delattr', 'open', 'with',
      ])
      if (!pyKeywords.has(callee)) {
        let caller = '<module>'
        if (currentClass) {
          const lastMethod = currentClass.methods[currentClass.methods.length - 1]
          if (lastMethod) caller = `${currentClass.name}.${lastMethod.name}`
        } else if (functions.length > 0) {
          caller = functions[functions.length - 1].name
        }
        callEdges.push({ caller, callee, file: filename, line: lineNum })
      }
    }
  }

  // Flush remaining class
  if (currentClass) classes.push(currentClass)

  return { functions, classes, imports, exports, callEdges }
}

// ============================================================================
// COMPLEXITY ANALYSIS
// ============================================================================

/**
 * Compute cyclomatic complexity for a block of source lines.
 * Cyclomatic = 1 + number of decision points (if, else if, for, while,
 * case, catch, &&, ||, ternary ?, ??, nullish coalescing).
 */
function computeCyclomaticComplexity(sourceLines, language) {
  let complexity = 1

  const jsDecisionPatterns = [
    /\bif\s*\(/,
    /\belse\s+if\s*\(/,
    /\bfor\s*\(/,
    /\bwhile\s*\(/,
    /\bcase\s+/,
    /\bcatch\s*\(/,
    /&&/,
    /\|\|/,
    /\?\?/,
    /[^?]\?[^?.]/,   // ternary (not optional chaining)
  ]

  const pyDecisionPatterns = [
    /\bif\s+/,
    /\belif\s+/,
    /\bfor\s+/,
    /\bwhile\s+/,
    /\bexcept\s*/,
    /\band\b/,
    /\bor\b/,
    /\bif\b.*\belse\b/,  // inline if-else
  ]

  const patterns = (language === 'python') ? pyDecisionPatterns : jsDecisionPatterns

  for (const line of sourceLines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('//') || trimmed.startsWith('#') || trimmed.startsWith('*')) continue
    for (const pattern of patterns) {
      if (pattern.test(trimmed)) {
        complexity++
      }
    }
  }

  return complexity
}

/**
 * Compute cognitive complexity.
 * Based on SonarSource's cognitive complexity model:
 * - +1 for each break in linear flow (if, for, while, catch)
 * - +1 for each level of nesting
 * - +1 for boolean sequences (&&, ||)
 * - NOT incremented by else, case, or default
 */
function computeCognitiveComplexity(sourceLines, language) {
  let complexity = 0
  let nestingLevel = 0

  const isPython = language === 'python'

  // Track nesting via braces (JS/TS) or indentation (Python)
  let prevIndent = 0

  for (const line of sourceLines) {
    const trimmed = line.trim()
    if (trimmed === '' || trimmed.startsWith('//') || trimmed.startsWith('#') || trimmed.startsWith('*')) continue

    if (isPython) {
      const indent = line.search(/\S/)
      if (indent > prevIndent) nestingLevel++
      else if (indent < prevIndent) nestingLevel = Math.max(0, nestingLevel - 1)
      prevIndent = indent
    } else {
      // For JS/TS, approximate nesting via braces on previous lines
      const openBraces = (trimmed.match(/\{/g) || []).length
      const closeBraces = (trimmed.match(/\}/g) || []).length
      if (closeBraces > openBraces) nestingLevel = Math.max(0, nestingLevel - (closeBraces - openBraces))
    }

    // Flow-breaking structures: +1 base + nesting increment
    const flowBreakers = isPython
      ? [/\bif\s+/, /\belif\s+/, /\bfor\s+/, /\bwhile\s+/, /\bexcept\s*/]
      : [/\bif\s*\(/, /\belse\s+if\s*\(/, /\bfor\s*\(/, /\bwhile\s*\(/, /\bcatch\s*\(/]

    for (const pattern of flowBreakers) {
      if (pattern.test(trimmed)) {
        complexity += 1 + nestingLevel
        break
      }
    }

    // Boolean operators: +1 each
    const boolOps = isPython
      ? [/\band\b/g, /\bor\b/g]
      : [/&&/g, /\|\|/g, /\?\?/g]

    for (const pattern of boolOps) {
      const matches = trimmed.match(pattern)
      if (matches) complexity += matches.length
    }

    // Recursion: +1 (detected if function calls itself -- handled at call site)

    if (!isPython) {
      const openBraces = (trimmed.match(/\{/g) || []).length
      const closeBraces = (trimmed.match(/\}/g) || []).length
      if (openBraces > closeBraces) nestingLevel += (openBraces - closeBraces)
    }
  }

  return complexity
}

/**
 * Extract the body lines of a function/method given its start line.
 * Uses brace matching (JS/TS) or indentation (Python).
 */
function extractFunctionBody(allLines, startLine, language) {
  const startIdx = startLine - 1
  if (startIdx < 0 || startIdx >= allLines.length) return []

  if (language === 'python') {
    // Python: collect lines with deeper indentation than the def line
    const defIndent = allLines[startIdx].search(/\S/)
    const bodyLines = []
    for (let i = startIdx + 1; i < allLines.length; i++) {
      const line = allLines[i]
      if (line.trim() === '') {
        bodyLines.push(line)
        continue
      }
      const indent = line.search(/\S/)
      if (indent <= defIndent) break
      bodyLines.push(line)
    }
    return bodyLines
  }

  // JS/TS: brace matching
  let depth = 0
  let started = false
  const bodyLines = []

  for (let i = startIdx; i < allLines.length; i++) {
    const line = allLines[i]
    for (const ch of line) {
      if (ch === '{') { depth++; started = true }
      if (ch === '}') depth--
    }
    if (started) bodyLines.push(line)
    if (started && depth <= 0) break
  }

  return bodyLines
}

// ============================================================================
// DESIGN PATTERN DETECTION
// ============================================================================

/**
 * Detect common design patterns from parsed structures.
 */
function detectPatterns(functions, classes, imports, exports, callEdges, sourcesByFile) {
  const patterns = []

  // --- Singleton Pattern ---
  // Evidence: class with private constructor and static getInstance
  for (const cls of classes) {
    const hasPrivateCtor = cls.methods.some(m => m.name === 'constructor' && m.visibility === 'private')
    const hasGetInstance = cls.methods.some(m => m.name === 'getInstance' && m.static)
    if (hasPrivateCtor || hasGetInstance) {
      patterns.push({
        name: 'Singleton',
        confidence: hasPrivateCtor && hasGetInstance ? 90 : 60,
        evidence: [
          hasPrivateCtor ? `Private constructor in ${cls.name}` : null,
          hasGetInstance ? `Static getInstance() in ${cls.name}` : null,
        ].filter(Boolean),
        files: [cls.file],
      })
    }
  }

  // --- Factory Pattern ---
  // Evidence: function/method named create*, build*, make* that returns objects
  const factoryNames = functions.filter(f =>
    /^(create|build|make|new)\w+/i.test(f.name)
  )
  const factoryMethods = classes.flatMap(c =>
    c.methods.filter(m => /^(create|build|make)\w+/i.test(m.name)).map(m => ({ ...m, className: c.name, file: c.file }))
  )
  if (factoryNames.length > 0 || factoryMethods.length > 0) {
    patterns.push({
      name: 'Factory',
      confidence: Math.min(90, 50 + (factoryNames.length + factoryMethods.length) * 15),
      evidence: [
        ...factoryNames.map(f => `Factory function: ${f.name} in ${f.file}`),
        ...factoryMethods.map(m => `Factory method: ${m.className}.${m.name} in ${m.file}`),
      ],
      files: [...new Set([...factoryNames.map(f => f.file), ...factoryMethods.map(m => m.file)])],
    })
  }

  // --- Observer/Event Pattern ---
  // Evidence: on/off/emit/addEventListener/subscribe methods or EventEmitter imports
  const eventMethods = ['on', 'off', 'emit', 'addEventListener', 'removeEventListener', 'subscribe', 'unsubscribe', 'notify']
  const eventClasses = classes.filter(c =>
    c.methods.some(m => eventMethods.includes(m.name)) ||
    (c.extends && /Event|Emitter|Observable|Subject/.test(c.extends))
  )
  const eventImports = imports.filter(imp =>
    /events|EventEmitter|rxjs|Observable|Subject/.test(imp.source)
  )
  if (eventClasses.length > 0 || eventImports.length > 0) {
    patterns.push({
      name: 'Observer/Event Emitter',
      confidence: Math.min(95, 60 + (eventClasses.length + eventImports.length) * 15),
      evidence: [
        ...eventClasses.map(c => `Event methods in class ${c.name}`),
        ...eventImports.map(i => `Event import: ${i.source}`),
      ],
      files: [...new Set([...eventClasses.map(c => c.file), ...eventImports.map(i => i.file)])],
    })
  }

  // --- Strategy Pattern ---
  // Evidence: interface/base class with multiple implementations, or objects keyed by strategy name
  const strategyIndicators = classes.filter(c =>
    c.methods.some(m => m.name === 'execute' || m.name === 'handle' || m.name === 'process') &&
    (c.extends || c.implements.length > 0)
  )
  if (strategyIndicators.length >= 2) {
    patterns.push({
      name: 'Strategy',
      confidence: Math.min(85, 50 + strategyIndicators.length * 15),
      evidence: strategyIndicators.map(c => `Strategy implementation: ${c.name} extends ${c.extends || c.implements.join(', ')}`),
      files: [...new Set(strategyIndicators.map(c => c.file))],
    })
  }

  // --- Decorator Pattern ---
  // Evidence: @decorator syntax (TS/Python) or wrapper functions
  for (const [file, source] of Object.entries(sourcesByFile)) {
    const decoratorMatches = source.match(/^[ \t]*@\w+/gm)
    if (decoratorMatches && decoratorMatches.length > 0) {
      patterns.push({
        name: 'Decorator',
        confidence: Math.min(90, 60 + decoratorMatches.length * 5),
        evidence: [`${decoratorMatches.length} decorator(s) in ${file}`],
        files: [file],
      })
    }
  }

  // --- Module Pattern ---
  // Evidence: IIFE or namespace-like exports
  const modulePatternFiles = []
  for (const [file, source] of Object.entries(sourcesByFile)) {
    if (source.includes('(function(') || source.includes('(() => {') || source.match(/\(function\s*\w*\s*\(/)) {
      modulePatternFiles.push(file)
    }
  }
  if (modulePatternFiles.length > 0) {
    patterns.push({
      name: 'Module (IIFE)',
      confidence: 70,
      evidence: modulePatternFiles.map(f => `IIFE pattern in ${f}`),
      files: modulePatternFiles,
    })
  }

  // --- Builder Pattern ---
  // Evidence: methods that return 'this' for chaining, or class named *Builder
  const builderClasses = classes.filter(c =>
    /Builder$/i.test(c.name) ||
    c.methods.filter(m => m.name.startsWith('set') || m.name.startsWith('with')).length >= 3
  )
  if (builderClasses.length > 0) {
    patterns.push({
      name: 'Builder',
      confidence: Math.min(90, 60 + builderClasses.length * 20),
      evidence: builderClasses.map(c => `Builder class: ${c.name}`),
      files: builderClasses.map(c => c.file),
    })
  }

  // --- Middleware Pattern ---
  // Evidence: use() method, next() callbacks, middleware-like function signatures
  const middlewareIndicators = functions.filter(f =>
    f.params.includes('next') || f.params.includes('middleware') ||
    /middleware/i.test(f.name)
  )
  const useMethodClasses = classes.filter(c =>
    c.methods.some(m => m.name === 'use')
  )
  if (middlewareIndicators.length > 0 || useMethodClasses.length > 0) {
    patterns.push({
      name: 'Middleware',
      confidence: Math.min(85, 50 + (middlewareIndicators.length + useMethodClasses.length) * 15),
      evidence: [
        ...middlewareIndicators.map(f => `Middleware function: ${f.name}`),
        ...useMethodClasses.map(c => `use() method in ${c.name}`),
      ],
      files: [...new Set([
        ...middlewareIndicators.map(f => f.file),
        ...useMethodClasses.map(c => c.file),
      ])],
    })
  }

  // Deduplicate patterns by name (keep highest confidence)
  const seen = new Map()
  for (const p of patterns) {
    const existing = seen.get(p.name)
    if (!existing || p.confidence > existing.confidence) {
      if (existing) {
        // Merge evidence and files
        p.evidence = [...new Set([...p.evidence, ...existing.evidence])]
        p.files = [...new Set([...p.files, ...existing.files])]
      }
      seen.set(p.name, p)
    }
  }

  return Array.from(seen.values()).sort((a, b) => b.confidence - a.confidence)
}

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

// Parse input arguments
const targetPath = args?.[0] || args?.path || args?.file || '.'
const targetLanguage = args?.language || args?.lang || null
const maxFiles = parseInt(args?.maxFiles || args?.max || '50', 10)

// ============================================================================
// PHASE 1: SETUP
// ============================================================================

phase('Setup')
log('Checking parser availability and detecting language...')

// Check tree-sitter availability via agent
const treeSitterCheck = await agent(
  `Check if tree-sitter CLI is available on this system.

Run these commands and report results:
1. which tree-sitter 2>/dev/null && echo "FOUND" || echo "NOT_FOUND"
2. If found, run: tree-sitter --version

Also check for tree-sitter Node.js bindings:
3. node -e "try { require('tree-sitter'); console.log('NODE_BINDINGS_FOUND') } catch(e) { console.log('NODE_BINDINGS_NOT_FOUND') }" 2>/dev/null

Return availability status.`,
  {
    label: 'check-tree-sitter',
    phase: 'Setup',
    schema: {
      type: 'object',
      properties: {
        cli_available: { type: 'boolean' },
        cli_version: { type: ['string', 'null'] },
        node_bindings: { type: 'boolean' },
      },
      required: ['cli_available', 'node_bindings'],
    },
  }
)

const useTreeSitter = treeSitterCheck?.cli_available || treeSitterCheck?.node_bindings || false
const parserMode = useTreeSitter ? 'tree-sitter' : 'regex'

log(`Parser: ${parserMode}${useTreeSitter ? ` (CLI: ${treeSitterCheck.cli_available}, Node: ${treeSitterCheck.node_bindings})` : ' (tree-sitter not available)'}`)

// Discover files to analyze
log(`Scanning target: ${targetPath}`)

const fileDiscovery = await agent(
  `Find source code files to analyze at path: ${targetPath}

Execute appropriate commands:
- If it is a single file, return just that file
- If it is a directory, find code files recursively

Use this command pattern:
find "${targetPath}" -type f \\( -name "*.js" -o -name "*.mjs" -o -name "*.cjs" -o -name "*.jsx" -o -name "*.ts" -o -name "*.tsx" -o -name "*.mts" -o -name "*.cts" -o -name "*.py" -o -name "*.java" -o -name "*.go" \\) -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/dist/*" -not -path "*/build/*" -not -path "*/__pycache__/*" -not -path "*/.next/*" -not -path "*/vendor/*" -not -path "*/.venv/*" -not -path "*/venv/*" -not -path "*/.tox/*" 2>/dev/null | sort | head -${maxFiles}

Return the list of files found, their count, and the dominant language.`,
  {
    label: 'discover-files',
    phase: 'Setup',
    schema: {
      type: 'object',
      properties: {
        files: { type: 'array', items: { type: 'string' } },
        count: { type: 'number' },
        dominant_language: { type: 'string' },
      },
      required: ['files', 'count'],
    },
  }
)

if (!fileDiscovery || fileDiscovery.count === 0) {
  log('No source files found at target path.')
  return {
    status: 'failed',
    parser: parserMode,
    language: 'unknown',
    files_analyzed: 0,
    functions: [],
    classes: [],
    dependencies: { imports: [], exports: [], call_graph: [] },
    patterns: [],
    summary: {
      total_functions: 0,
      total_classes: 0,
      total_imports: 0,
      avg_cyclomatic: 0,
      avg_cognitive: 0,
      max_cyclomatic: { name: 'N/A', value: 0 },
      max_cognitive: { name: 'N/A', value: 0 },
      patterns_detected: [],
    },
    error: `No source files found at: ${targetPath}`,
  }
}

const filesToAnalyze = fileDiscovery.files
const detectedLanguage = targetLanguage || fileDiscovery.dominant_language || 'javascript'

log(`Found ${fileDiscovery.count} file(s), dominant language: ${detectedLanguage}`)
log(`Analyzing up to ${maxFiles} files using ${parserMode} parser`)

// ============================================================================
// PHASE 2: PARSE
// ============================================================================

phase('Parse')
log(`Parsing ${filesToAnalyze.length} file(s)...`)

// Read all file contents via agent (batch to reduce overhead)
const BATCH_SIZE = 10
const allSources = {}
const allFunctions = []
const allClasses = []
const allImports = []
const allExports = []
const allCallEdges = []

for (let batch = 0; batch < filesToAnalyze.length; batch += BATCH_SIZE) {
  const batchFiles = filesToAnalyze.slice(batch, batch + BATCH_SIZE)
  const batchNum = Math.floor(batch / BATCH_SIZE) + 1
  const totalBatches = Math.ceil(filesToAnalyze.length / BATCH_SIZE)

  log(`  Batch ${batchNum}/${totalBatches}: ${batchFiles.length} file(s)`)

  // Read file contents via agent in parallel
  const fileContents = await parallel(batchFiles.map(file => () =>
    agent(
      `Read the complete contents of the file: ${file}

Return the EXACT file contents as a string. Do NOT summarize or truncate.
If the file is very large (>2000 lines), return the first 2000 lines.`,
      {
        label: `read-${file.split('/').pop()}`,
        phase: 'Parse',
        schema: {
          type: 'object',
          properties: {
            file: { type: 'string' },
            content: { type: 'string' },
            line_count: { type: 'number' },
            truncated: { type: 'boolean' },
          },
          required: ['file', 'content'],
        },
      }
    )
  ))

  // Parse each file using regex (or tree-sitter if available)
  for (const fileData of fileContents) {
    if (!fileData || !fileData.content) continue

    const filename = fileData.file
    const source = fileData.content
    allSources[filename] = source

    const lang = detectLanguageFromExt(filename) || detectedLanguage

    if (useTreeSitter) {
      // Tree-sitter parsing delegated to agent with CLI
      const tsResult = await agent(
        `Parse the following file using tree-sitter and extract structural information.

File: ${filename}
Language: ${lang}

Use tree-sitter to parse and extract:
1. All function declarations (name, line, params, async, exported, generator)
2. All class declarations (name, line, extends, implements, methods, properties)
3. All import statements (source, specifiers, type)
4. All export statements (name, type)

The file content has already been read. Parse it structurally.

Return the extracted structures.`,
        {
          label: `ts-parse-${filename.split('/').pop()}`,
          phase: 'Parse',
          schema: {
            type: 'object',
            properties: {
              functions: { type: 'array', items: SCHEMAS.FUNCTION },
              classes: { type: 'array', items: SCHEMAS.CLASS },
              imports: { type: 'array', items: SCHEMAS.IMPORT },
              exports: {
                type: 'array',
                items: {
                  type: 'object',
                  properties: {
                    name: { type: 'string' },
                    file: { type: 'string' },
                    line: { type: 'number' },
                    type: { type: 'string' },
                  },
                },
              },
            },
          },
        }
      )

      if (tsResult) {
        allFunctions.push(...(tsResult.functions || []))
        allClasses.push(...(tsResult.classes || []))
        allImports.push(...(tsResult.imports || []))
        allExports.push(...(tsResult.exports || []))
      }
    } else {
      // Regex fallback parsing (runs locally, no agent needed)
      let parsed
      if (lang === 'python') {
        parsed = parsePythonRegex(source, filename)
      } else if (lang === 'javascript' || lang === 'typescript') {
        parsed = parseJavaScriptRegex(source, filename)
      } else {
        // For Java/Go, fall back to agent-based extraction
        const agentParsed = await agent(
          `Extract structural information from this ${lang} source file using pattern matching.

File: ${filename}

Extract:
1. Functions/methods: name, line number, parameters, visibility, static, async
2. Classes/interfaces/structs: name, line number, extends/implements, methods, fields
3. Import statements: package/module, imported names
4. Export/public declarations

Analyze the file content that was read from: ${filename}

Return structured results.`,
          {
            label: `parse-${filename.split('/').pop()}`,
            phase: 'Parse',
            schema: {
              type: 'object',
              properties: {
                functions: { type: 'array', items: SCHEMAS.FUNCTION },
                classes: { type: 'array', items: SCHEMAS.CLASS },
                imports: { type: 'array', items: SCHEMAS.IMPORT },
                exports: {
                  type: 'array',
                  items: {
                    type: 'object',
                    properties: {
                      name: { type: 'string' },
                      file: { type: 'string' },
                      line: { type: 'number' },
                      type: { type: 'string' },
                    },
                  },
                },
              },
            },
          }
        )

        if (agentParsed) {
          allFunctions.push(...(agentParsed.functions || []))
          allClasses.push(...(agentParsed.classes || []))
          allImports.push(...(agentParsed.imports || []))
          allExports.push(...(agentParsed.exports || []))
        }
        continue
      }

      allFunctions.push(...parsed.functions)
      allClasses.push(...parsed.classes)
      allImports.push(...parsed.imports)
      allExports.push(...parsed.exports)
      allCallEdges.push(...parsed.callEdges)
    }
  }
}

log(`Parsed: ${allFunctions.length} functions, ${allClasses.length} classes, ${allImports.length} imports`)

// ============================================================================
// PHASE 3: ANALYZE (Complexity)
// ============================================================================

phase('Analyze')
log('Computing complexity metrics...')

// Compute complexity for each function
for (const fn of allFunctions) {
  const source = allSources[fn.file]
  if (!source) continue

  const allLines = source.split('\n')
  const lang = detectLanguageFromExt(fn.file) || detectedLanguage
  const bodyLines = extractFunctionBody(allLines, fn.line, lang)

  if (bodyLines.length > 0) {
    fn.complexity = {
      cyclomatic: computeCyclomaticComplexity(bodyLines, lang),
      cognitive: computeCognitiveComplexity(bodyLines, lang),
    }
  }
}

// Compute complexity for each class method
for (const cls of allClasses) {
  const source = allSources[cls.file]
  if (!source) continue

  const allLines = source.split('\n')
  const lang = detectLanguageFromExt(cls.file) || detectedLanguage

  for (const method of cls.methods) {
    const bodyLines = extractFunctionBody(allLines, method.line, lang)
    if (bodyLines.length > 0) {
      method.complexity = {
        cyclomatic: computeCyclomaticComplexity(bodyLines, lang),
        cognitive: computeCognitiveComplexity(bodyLines, lang),
      }
    }
  }
}

// Collect all complexity scores for summary
const allComplexities = [
  ...allFunctions.map(f => ({ name: f.name, file: f.file, ...f.complexity })),
  ...allClasses.flatMap(c =>
    c.methods.map(m => ({ name: `${c.name}.${m.name}`, file: c.file, ...m.complexity }))
  ),
]

const cyclomaticValues = allComplexities.map(c => c.cyclomatic).filter(v => typeof v === 'number')
const cognitiveValues = allComplexities.map(c => c.cognitive).filter(v => typeof v === 'number')

const avgCyclomatic = cyclomaticValues.length > 0
  ? Math.round((cyclomaticValues.reduce((a, b) => a + b, 0) / cyclomaticValues.length) * 10) / 10
  : 0
const avgCognitive = cognitiveValues.length > 0
  ? Math.round((cognitiveValues.reduce((a, b) => a + b, 0) / cognitiveValues.length) * 10) / 10
  : 0

const maxCyclomatic = allComplexities.reduce(
  (max, c) => (c.cyclomatic > max.value ? { name: c.name, value: c.cyclomatic } : max),
  { name: 'N/A', value: 0 }
)
const maxCognitive = allComplexities.reduce(
  (max, c) => (c.cognitive > max.value ? { name: c.name, value: c.cognitive } : max),
  { name: 'N/A', value: 0 }
)

log(`Complexity: avg cyclomatic=${avgCyclomatic}, avg cognitive=${avgCognitive}`)
log(`  Highest cyclomatic: ${maxCyclomatic.name} (${maxCyclomatic.value})`)
log(`  Highest cognitive: ${maxCognitive.name} (${maxCognitive.value})`)

// Flag high-complexity items
const highComplexity = allComplexities.filter(c => c.cyclomatic > 10 || c.cognitive > 15)
if (highComplexity.length > 0) {
  log(`  WARNING: ${highComplexity.length} function(s) with high complexity:`)
  for (const hc of highComplexity.slice(0, 5)) {
    log(`    - ${hc.name}: cyclomatic=${hc.cyclomatic}, cognitive=${hc.cognitive}`)
  }
}

// ============================================================================
// PHASE 4: DEPENDENCIES
// ============================================================================

phase('Dependencies')
log('Building dependency graph...')

// Deduplicate call edges
const uniqueCallEdges = []
const edgeSet = new Set()
for (const edge of allCallEdges) {
  const key = `${edge.caller}->${edge.callee}@${edge.file}:${edge.line}`
  if (!edgeSet.has(key)) {
    edgeSet.add(key)
    uniqueCallEdges.push(edge)
  }
}

// Categorize imports
const externalImports = allImports.filter(i => !i.source.startsWith('.') && !i.source.startsWith('/'))
const internalImports = allImports.filter(i => i.source.startsWith('.') || i.source.startsWith('/'))

log(`Dependencies: ${allImports.length} imports (${externalImports.length} external, ${internalImports.length} internal)`)
log(`  Exports: ${allExports.length}`)
log(`  Call edges: ${uniqueCallEdges.length}`)

// Top external dependencies
const depCounts = {}
for (const imp of externalImports) {
  // Normalize: @scope/package -> @scope/package, lodash/fp -> lodash
  const pkg = imp.source.startsWith('@')
    ? imp.source.split('/').slice(0, 2).join('/')
    : imp.source.split('/')[0]
  depCounts[pkg] = (depCounts[pkg] || 0) + 1
}
const topDeps = Object.entries(depCounts)
  .sort((a, b) => b[1] - a[1])
  .slice(0, 10)

if (topDeps.length > 0) {
  log('  Top external dependencies:')
  for (const [pkg, count] of topDeps) {
    log(`    - ${pkg}: ${count} import(s)`)
  }
}

// ============================================================================
// PHASE 5: PATTERNS
// ============================================================================

phase('Patterns')
log('Detecting design patterns...')

const detectedPatterns = detectPatterns(
  allFunctions, allClasses, allImports, allExports, uniqueCallEdges, allSources
)

if (detectedPatterns.length > 0) {
  log(`Detected ${detectedPatterns.length} pattern(s):`)
  for (const p of detectedPatterns) {
    log(`  - ${p.name} (${p.confidence}% confidence)`)
    for (const e of p.evidence.slice(0, 2)) {
      log(`      ${e}`)
    }
  }
} else {
  log('  No common design patterns detected.')
}

// ============================================================================
// PHASE 6: OUTPUT
// ============================================================================

phase('Output')
log('Assembling structured result...')

const result = {
  status: allFunctions.length > 0 || allClasses.length > 0 ? 'complete' : 'partial',
  parser: parserMode,
  language: detectedLanguage,
  files_analyzed: Object.keys(allSources).length,
  functions: allFunctions,
  classes: allClasses,
  dependencies: {
    imports: allImports,
    exports: allExports,
    call_graph: uniqueCallEdges,
  },
  patterns: detectedPatterns,
  summary: {
    total_functions: allFunctions.length,
    total_classes: allClasses.length,
    total_imports: allImports.length,
    avg_cyclomatic: avgCyclomatic,
    avg_cognitive: avgCognitive,
    max_cyclomatic: maxCyclomatic,
    max_cognitive: maxCognitive,
    patterns_detected: detectedPatterns.map(p => p.name),
    high_complexity_count: highComplexity.length,
    external_dependencies: topDeps.map(([pkg, count]) => ({ package: pkg, import_count: count })),
  },
}

log('')
log('='.repeat(60))
log('AST ANALYSIS COMPLETE')
log('='.repeat(60))
log(`Files: ${result.files_analyzed}`)
log(`Functions: ${result.summary.total_functions}`)
log(`Classes: ${result.summary.total_classes}`)
log(`Imports: ${result.summary.total_imports}`)
log(`Avg Cyclomatic: ${result.summary.avg_cyclomatic}`)
log(`Avg Cognitive: ${result.summary.avg_cognitive}`)
log(`Patterns: ${result.summary.patterns_detected.join(', ') || 'none'}`)
log(`High Complexity: ${result.summary.high_complexity_count} function(s)`)
log('='.repeat(60))

return result

}
