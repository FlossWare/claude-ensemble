#!/usr/bin/env node

/**
 * Perpetual Web Learner
 *
 * Autonomous, continuous web research system that runs every 6 hours via
 * systemd timer. Rotates through research topics and sources, stores all
 * findings, and adapts its topic selection based on what proves useful.
 *
 * NO STOPPING CONDITION. Designed to run indefinitely.
 *
 * Pipeline per run:
 *   1. Select topics (adaptive rotation + trending discovery)
 *   2. Research across all sources in parallel
 *   3. Synthesize and deduplicate findings
 *   4. Store to JSONL + generate vector embeddings
 *   5. Update topic effectiveness scores for next rotation
 *   6. Prune stale data (>90 days)
 *
 * Storage:
 *   ~/.claude/learning/research/web-synthesis-YYYY-MM-DD.jsonl  (daily append)
 *   ~/.claude/learning/research/web-synthesis-vectors.jsonl      (cumulative)
 *   ~/.claude/learning/research/web-synthesis-index.json         (rebuilt)
 *   ~/.claude/learning/research/web-synthesis-metadata.json      (latest)
 *   ~/.claude/learning/research/perpetual-state.json             (rotation state)
 *   ~/.claude/learning/research/sessions/                        (session archives)
 *
 * Usage:
 *   node perpetual-web-learner.js                # Normal run (called by timer)
 *   node perpetual-web-learner.js --status       # Show rotation state
 *   node perpetual-web-learner.js --force-topic "RAG frameworks"  # Force a topic
 *   node perpetual-web-learner.js --dry-run      # Show what would run, no writes
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Source scrapers
const arxiv = require('./research/arxiv');
const github = require('./research/github');
const hackernews = require('./research/hackernews');
const stackoverflow = require('./research/stackoverflow');

// Research session orchestrator
const research = require('./research-session');

// =============================================================================
// CONFIGURATION
// =============================================================================

const RESEARCH_DIR = path.join(process.env.HOME, '.claude', 'learning', 'research');
const STATE_FILE = path.join(RESEARCH_DIR, 'perpetual-state.json');
const LOG_DIR = path.join(process.env.HOME, '.claude', 'learning', 'logs');

// How many topics to research per run
const TOPICS_PER_RUN = 3;

// How many results per source per topic
const RESULTS_PER_SOURCE = 8;

// Source rotation: cycle through source combinations to avoid rate limits
const SOURCE_ROTATIONS = [
  ['arxiv', 'hackernews', 'github'],
  ['hackernews', 'stackoverflow', 'github'],
  ['arxiv', 'github', 'stackoverflow'],
  ['hackernews', 'arxiv', 'stackoverflow'],
];

// Topic categories with seed queries -- adaptive system will learn which yield best results
const TOPIC_REGISTRY = {
  // Core AI/ML research
  'multi-agent-systems':      { queries: ['multi-agent LLM orchestration', 'agent collaboration framework'], category: 'cs.MA', weight: 1.0 },
  'rag-architecture':         { queries: ['RAG retrieval augmented generation 2026', 'agentic RAG framework'], category: 'cs.IR', weight: 1.0 },
  'llm-reasoning':            { queries: ['LLM reasoning chain-of-thought', 'reasoning model evaluation'], category: 'cs.AI', weight: 1.0 },
  'model-quantization':       { queries: ['model quantization inference efficiency', 'GGUF quantization'], category: 'cs.LG', weight: 1.0 },
  'context-engineering':      { queries: ['context window management', 'context engineering LLM'], category: 'cs.CL', weight: 1.0 },
  'agent-security':           { queries: ['AI agent security vulnerability', 'LLM agent attack surface'], category: 'cs.CR', weight: 1.0 },
  'mcp-protocol':             { queries: ['model context protocol MCP', 'MCP tool integration'], category: null, weight: 1.0 },
  'local-inference':          { queries: ['local LLM inference Ollama', 'on-device AI inference'], category: null, weight: 1.0 },
  'code-generation':          { queries: ['AI code generation quality', 'LLM coding assistant'], category: 'cs.SE', weight: 1.0 },
  'evaluation-observability': { queries: ['LLM evaluation benchmark', 'AI observability OpenTelemetry'], category: null, weight: 1.0 },

  // Architecture and systems
  'ssm-transformer':          { queries: ['Mamba SSM transformer hybrid', 'state space model architecture'], category: 'cs.LG', weight: 0.8 },
  'kv-cache':                 { queries: ['KV cache optimization LLM', 'attention cache management'], category: 'cs.LG', weight: 0.8 },
  'structured-output':        { queries: ['structured output JSON LLM', 'grammar-constrained generation'], category: 'cs.CL', weight: 0.8 },
  'knowledge-graphs':         { queries: ['knowledge graph RAG GraphRAG', 'entity graph construction'], category: 'cs.AI', weight: 0.8 },
  'memory-systems':           { queries: ['agent memory architecture', 'long-term memory LLM'], category: 'cs.AI', weight: 0.8 },

  // Production engineering
  'inference-serving':        { queries: ['LLM inference serving vLLM SGLang', 'production model serving'], category: null, weight: 0.7 },
  'fine-tuning':              { queries: ['RL post-training GRPO DPO', 'fine-tuning production'], category: 'cs.LG', weight: 0.7 },
  'prompt-engineering':       { queries: ['prompt engineering techniques 2026', 'prompt optimization'], category: null, weight: 0.7 },
  'multimodal':               { queries: ['multimodal AI vision language', 'unified multimodal model'], category: 'cs.CV', weight: 0.7 },
  'document-processing':      { queries: ['document parsing AI OCR', 'PDF extraction LLM'], category: null, weight: 0.7 },

  // Emerging frontiers
  'ai-agents-tools':          { queries: ['AI agent tool use', 'autonomous agent framework'], category: 'cs.AI', weight: 0.6 },
  'synthetic-data':           { queries: ['synthetic data generation training', 'data augmentation LLM'], category: 'cs.LG', weight: 0.6 },
  'alignment-safety':         { queries: ['AI alignment safety RLHF', 'model alignment techniques'], category: 'cs.AI', weight: 0.6 },
  'edge-ai':                  { queries: ['edge AI deployment mobile', 'small language model'], category: 'cs.LG', weight: 0.6 },
};

// =============================================================================
// STATE MANAGEMENT
// =============================================================================

function loadState() {
  try {
    if (fs.existsSync(STATE_FILE)) {
      return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    }
  } catch (e) {
    log(`WARN: Could not load state: ${e.message}`);
  }

  return {
    version: 1,
    created: new Date().toISOString(),
    runCount: 0,
    lastRun: null,
    sourceRotationIndex: 0,
    topicRotationIndex: 0,
    topicEffectiveness: {},     // topic -> { totalFindings, avgEngagement, lastRun, runCount }
    recentTopics: [],           // last N topics researched (avoid repeating)
    totalFindingsStored: 0,
    totalRunDurationMs: 0,
    adaptationLog: [],          // records of weight adjustments
  };
}

function saveState(state) {
  try {
    if (!fs.existsSync(RESEARCH_DIR)) {
      fs.mkdirSync(RESEARCH_DIR, { recursive: true });
    }
    fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), 'utf8');
  } catch (e) {
    log(`ERROR: Could not save state: ${e.message}`);
  }
}

// =============================================================================
// LOGGING
// =============================================================================

function log(msg) {
  const timestamp = new Date().toISOString();
  const line = `[${timestamp}] [perpetual-web-learner] ${msg}`;
  console.log(line);

  // Also append to log file
  try {
    if (!fs.existsSync(LOG_DIR)) {
      fs.mkdirSync(LOG_DIR, { recursive: true });
    }
    fs.appendFileSync(
      path.join(LOG_DIR, 'perpetual-web-learner.log'),
      line + '\n',
      'utf8'
    );
  } catch (_e) {
    // Non-fatal
  }
}

// =============================================================================
// ADAPTIVE TOPIC SELECTION
// =============================================================================

/**
 * Select topics for this run using adaptive weighted rotation.
 * Topics that previously yielded high-engagement findings get higher weight.
 * Recently researched topics get suppressed.
 */
function selectTopics(state, forceTopic) {
  if (forceTopic) {
    return [{ key: 'forced', topic: { queries: [forceTopic], category: null, weight: 1.0 } }];
  }

  const allTopics = Object.entries(TOPIC_REGISTRY);
  const recentSet = new Set(state.recentTopics.slice(0, 10));

  // Compute adaptive weights
  const weighted = allTopics.map(([key, topic]) => {
    let weight = topic.weight;

    // Boost topics that have historically yielded more findings
    const effectiveness = state.topicEffectiveness[key];
    if (effectiveness && effectiveness.runCount > 0) {
      const avgFindings = effectiveness.totalFindings / effectiveness.runCount;
      const engagementBoost = Math.min(effectiveness.avgEngagement / 50, 1.0);
      weight *= (1 + avgFindings / 20 + engagementBoost * 0.5);
    }

    // Suppress recently researched topics
    if (recentSet.has(key)) {
      weight *= 0.1;
    }

    // Add small random jitter for exploration (epsilon-greedy)
    weight *= (0.8 + Math.random() * 0.4);

    return { key, topic, weight };
  });

  // Sort by weight descending, take top N
  weighted.sort((a, b) => b.weight - a.weight);
  const selected = weighted.slice(0, TOPICS_PER_RUN);

  log(`Topic selection: ${selected.map(s => `${s.key}(w=${s.weight.toFixed(2)})`).join(', ')}`);
  return selected;
}

/**
 * Get which sources to use for this run (rotation to distribute API load)
 */
function selectSources(state) {
  const idx = state.sourceRotationIndex % SOURCE_ROTATIONS.length;
  return SOURCE_ROTATIONS[idx];
}

// =============================================================================
// RESEARCH EXECUTION
// =============================================================================

/**
 * Execute research for a single topic across selected sources.
 */
async function researchTopic(topicKey, topic, sources) {
  const query = topic.queries[Math.floor(Math.random() * topic.queries.length)];
  log(`Researching: "${query}" via [${sources.join(', ')}]`);

  const sourceOptions = {};
  if (topic.category) {
    sourceOptions.arxiv = { category: topic.category };
  }

  try {
    const result = await research.investigate(query, {
      sources,
      maxResultsPerSource: RESULTS_PER_SOURCE,
      persist: true,
      ...sourceOptions,
    });

    return {
      topicKey,
      query,
      success: true,
      totalFindings: result.summary.totalFindings,
      topFindings: result.summary.topFindings || [],
      sourceResults: result.sourceResults,
      allFindings: result.allFindings || [],
      durationMs: result.durationMs,
    };
  } catch (e) {
    log(`ERROR researching "${query}": ${e.message}`);
    return {
      topicKey,
      query,
      success: false,
      error: e.message,
      totalFindings: 0,
      topFindings: [],
      allFindings: [],
      durationMs: 0,
    };
  }
}

/**
 * Run trending/discovery research (no specific topic)
 */
async function runDiscovery() {
  log('Running discovery (trending content)...');
  try {
    const result = await research.discover({ count: RESULTS_PER_SOURCE, persist: true });
    return {
      topicKey: '_discovery',
      query: null,
      success: true,
      totalFindings: result.summary.totalFindings,
      topFindings: (result.allFindings || []).slice(0, 5),
      allFindings: result.allFindings || [],
      durationMs: result.durationMs,
    };
  } catch (e) {
    log(`ERROR in discovery: ${e.message}`);
    return {
      topicKey: '_discovery',
      query: null,
      success: false,
      error: e.message,
      totalFindings: 0,
      topFindings: [],
      allFindings: [],
      durationMs: 0,
    };
  }
}

// =============================================================================
// STORAGE PIPELINE
// =============================================================================

/**
 * Create a deterministic embedding vector for text content.
 * Uses hash-based proxy; production would use sentence-transformers or API.
 */
function createEmbedding(text, type) {
  const hash = crypto.createHash('sha256').update(text + type).digest();
  const embedding = new Float32Array(768);

  for (let i = 0; i < 768; i++) {
    const byte1 = hash[(i * 2) % 32];
    const byte2 = hash[((i * 2) + 1) % 32];
    embedding[i] = ((byte1 ^ byte2) / 255) * 2 - 1;
  }

  const typeHash = crypto.createHash('sha256').update(type).digest();
  for (let i = 0; i < 64; i++) {
    embedding[i] = (embedding[i] * 0.7) + ((typeHash[i % 32] / 255) * 0.3);
  }

  let norm = 0;
  for (let i = 0; i < 768; i++) norm += embedding[i] * embedding[i];
  norm = Math.sqrt(norm);
  for (let i = 0; i < 768; i++) embedding[i] /= norm;

  return Array.from(embedding.slice(0, 100));
}

/**
 * Store findings to JSONL, vectors, and index files.
 * Appends to daily file; rebuilds cumulative vector index.
 */
function storeFindings(allResults, state) {
  const today = new Date().toISOString().split('T')[0];
  const synthesisFile = path.join(RESEARCH_DIR, `web-synthesis-${today}.jsonl`);
  const vectorFile = path.join(RESEARCH_DIR, 'web-synthesis-vectors.jsonl');
  const indexFile = path.join(RESEARCH_DIR, 'web-synthesis-index.json');
  const metadataFile = path.join(RESEARCH_DIR, 'web-synthesis-metadata.json');

  if (!fs.existsSync(RESEARCH_DIR)) {
    fs.mkdirSync(RESEARCH_DIR, { recursive: true });
  }

  let storedCount = 0;
  const newItems = [];
  const existingIds = loadExistingIds(synthesisFile);

  for (const result of allResults) {
    if (!result.success) continue;

    for (const finding of result.allFindings) {
      // Generate a unique ID for deduplication
      const findingId = generateFindingId(finding);
      if (existingIds.has(findingId)) continue;

      const item = {
        type: classifyFinding(finding),
        id: findingId,
        timestamp: new Date().toISOString(),
        title: finding.title || finding.name || '',
        source: finding.source,
        sourceType: finding.sourceType,
        url: finding.url || finding.discussionUrl || null,
        relevanceScore: finding.relevanceScore || 0,
        topicKey: result.topicKey,
        query: result.query,
        // Source-specific fields
        points: finding.points || finding.score || finding.questionScore || null,
        stars: finding.metrics ? finding.metrics.stars : null,
        commentCount: finding.commentCount || null,
        abstract: finding.abstract || null,
        description: finding.description || null,
        tags: finding.tags || finding.topics || finding.categories || [],
        source_tags: [finding.source, result.topicKey].filter(Boolean),
      };

      fs.appendFileSync(synthesisFile, JSON.stringify(item) + '\n', 'utf8');
      existingIds.add(findingId);

      // Create vector embedding
      const textForEmbedding = [
        item.title,
        item.description || item.abstract || '',
        (item.tags || []).join(' '),
      ].filter(Boolean).join(' ');

      const embedding = createEmbedding(textForEmbedding, item.type);

      fs.appendFileSync(vectorFile, JSON.stringify({
        id: findingId,
        type: item.type,
        embedding,
        timestamp: item.timestamp,
        source_tags: item.source_tags,
        summary: (item.title || '').substring(0, 100),
      }) + '\n', 'utf8');

      newItems.push({
        id: findingId,
        type: item.type,
        title: item.title,
        timestamp: item.timestamp,
        embedding_dim: 100,
        source_tags: item.source_tags,
      });

      storedCount++;
    }
  }

  // Rebuild index (merge with existing)
  let existingIndex = { items: [] };
  try {
    if (fs.existsSync(indexFile)) {
      existingIndex = JSON.parse(fs.readFileSync(indexFile, 'utf8'));
    }
  } catch (_e) { /* start fresh */ }

  const mergedItems = [...(existingIndex.items || []), ...newItems];

  // Deduplicate by ID
  const seen = new Set();
  const dedupedItems = mergedItems.filter(item => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });

  const typeCounts = dedupedItems.reduce((acc, item) => {
    acc[item.type] = (acc[item.type] || 0) + 1;
    return acc;
  }, {});

  fs.writeFileSync(indexFile, JSON.stringify({
    version: '2.0',
    created: new Date().toISOString(),
    embedding_model: 'deterministic-hash-768-to-100',
    vector_dim: 100,
    total_vectors: dedupedItems.length,
    item_types: typeCounts,
    last_update: new Date().toISOString(),
    perpetual_run: state.runCount + 1,
    items: dedupedItems,
  }, null, 2), 'utf8');

  // Update metadata
  const totalFindings = allResults.reduce((sum, r) => sum + r.totalFindings, 0);
  fs.writeFileSync(metadataFile, JSON.stringify({
    synthesisDate: today,
    timestamp: new Date().toISOString(),
    source: 'perpetual-web-learner',
    totalItems: dedupedItems.length,
    newItemsThisRun: storedCount,
    breakdown: typeCounts,
    evidenceSources: [
      'ArXiv research papers',
      'GitHub Trending projects',
      'Hacker News discussions',
      'Stack Overflow Q&A',
    ],
    indexedFields: ['type', 'id', 'title', 'timestamp', 'source_tags'],
    perpetualState: {
      runCount: state.runCount + 1,
      totalFindingsAllTime: state.totalFindingsStored + storedCount,
    },
  }, null, 2), 'utf8');

  log(`Stored ${storedCount} new findings (${dedupedItems.length} total in index)`);
  return storedCount;
}

/**
 * Load existing finding IDs from today's synthesis file for deduplication.
 */
function loadExistingIds(synthesisFile) {
  const ids = new Set();
  try {
    if (fs.existsSync(synthesisFile)) {
      const lines = fs.readFileSync(synthesisFile, 'utf8').trim().split('\n');
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const item = JSON.parse(line);
          if (item.id) ids.add(item.id);
        } catch (_e) { /* skip malformed */ }
      }
    }
  } catch (_e) { /* file doesn't exist yet */ }
  return ids;
}

/**
 * Generate a unique ID for a finding based on content hash.
 */
function generateFindingId(finding) {
  const key = [
    finding.title || '',
    finding.url || '',
    finding.source || '',
  ].join('|');
  return crypto.createHash('sha256').update(key).digest('hex').substring(0, 16);
}

/**
 * Classify a finding into a type category.
 */
function classifyFinding(finding) {
  const source = finding.source || '';
  const sourceType = finding.sourceType || '';

  if (source === 'arxiv' || sourceType === 'academic_papers') return 'research_paper';
  if (source === 'github' || sourceType === 'repositories') return 'tool';
  if (source === 'hackernews' || sourceType === 'front_page') return 'discussion';
  if (source === 'stackoverflow' || sourceType === 'questions') return 'qa';
  return 'general';
}

// =============================================================================
// ADAPTIVE FEEDBACK
// =============================================================================

/**
 * Update topic effectiveness scores based on research results.
 * Topics that yield more findings and higher engagement get boosted.
 */
function updateEffectiveness(state, results) {
  for (const result of results) {
    if (result.topicKey === '_discovery') continue;

    const key = result.topicKey;
    if (!state.topicEffectiveness[key]) {
      state.topicEffectiveness[key] = {
        totalFindings: 0,
        avgEngagement: 0,
        lastRun: null,
        runCount: 0,
      };
    }

    const eff = state.topicEffectiveness[key];
    eff.totalFindings += result.totalFindings;
    eff.runCount++;
    eff.lastRun = new Date().toISOString();

    // Compute average engagement from top findings
    if (result.topFindings.length > 0) {
      const avgScore = result.topFindings.reduce((sum, f) => {
        return sum + (f.relevanceScore || f.engagementScore || 0);
      }, 0) / result.topFindings.length;
      // Exponential moving average
      eff.avgEngagement = eff.avgEngagement * 0.7 + avgScore * 0.3;
    }
  }

  // Log any significant weight changes
  const topTopics = Object.entries(state.topicEffectiveness)
    .sort((a, b) => (b[1].avgEngagement || 0) - (a[1].avgEngagement || 0))
    .slice(0, 5);

  if (topTopics.length > 0) {
    log(`Top topics by engagement: ${topTopics.map(([k, v]) => `${k}(${v.avgEngagement.toFixed(1)})`).join(', ')}`);
  }
}

// =============================================================================
// DATA PRUNING
// =============================================================================

/**
 * Remove synthesis files older than 90 days to prevent unbounded growth.
 */
function pruneOldData() {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 90);
  const cutoffStr = cutoff.toISOString().split('T')[0];

  try {
    const files = fs.readdirSync(RESEARCH_DIR)
      .filter(f => f.startsWith('web-synthesis-') && f.endsWith('.jsonl'))
      .filter(f => {
        const dateMatch = f.match(/web-synthesis-(\d{4}-\d{2}-\d{2})\.jsonl/);
        return dateMatch && dateMatch[1] < cutoffStr;
      });

    for (const file of files) {
      const filePath = path.join(RESEARCH_DIR, file);
      fs.unlinkSync(filePath);
      log(`Pruned old synthesis file: ${file}`);
    }

    if (files.length > 0) {
      log(`Pruned ${files.length} synthesis files older than 90 days`);
    }
  } catch (e) {
    log(`WARN: Pruning failed: ${e.message}`);
  }

  // Also prune old session files
  const sessionsDir = path.join(RESEARCH_DIR, 'sessions');
  try {
    if (fs.existsSync(sessionsDir)) {
      const sessionFiles = fs.readdirSync(sessionsDir)
        .filter(f => f.endsWith('.json'))
        .sort();

      // Keep only last 200 sessions
      if (sessionFiles.length > 200) {
        const toRemove = sessionFiles.slice(0, sessionFiles.length - 200);
        for (const file of toRemove) {
          fs.unlinkSync(path.join(sessionsDir, file));
        }
        log(`Pruned ${toRemove.length} old session files (kept 200)`);
      }
    }
  } catch (e) {
    log(`WARN: Session pruning failed: ${e.message}`);
  }
}

// =============================================================================
// LOG ROTATION
// =============================================================================

function rotateLog() {
  const logFile = path.join(LOG_DIR, 'perpetual-web-learner.log');
  try {
    if (fs.existsSync(logFile)) {
      const stats = fs.statSync(logFile);
      // Rotate at 10MB
      if (stats.size > 10 * 1024 * 1024) {
        const rotated = logFile + '.1';
        if (fs.existsSync(rotated)) {
          fs.unlinkSync(rotated);
        }
        fs.renameSync(logFile, rotated);
        log('Log rotated');
      }
    }
  } catch (_e) {
    // Non-fatal
  }
}

// =============================================================================
// MAIN EXECUTION
// =============================================================================

async function run(options = {}) {
  const startTime = Date.now();
  const state = loadState();

  log('='.repeat(70));
  log(`PERPETUAL WEB LEARNER - Run #${state.runCount + 1}`);
  log(`Previous run: ${state.lastRun || 'never'}`);
  log('='.repeat(70));

  // Rotate log if needed
  rotateLog();

  // Select topics and sources
  const topics = selectTopics(state, options.forceTopic);
  const sources = selectSources(state);

  log(`Sources for this run: [${sources.join(', ')}]`);

  if (options.dryRun) {
    log('DRY RUN - would research:');
    for (const t of topics) {
      log(`  - ${t.key}: ${t.topic.queries[0]}`);
    }
    log(`  - discovery (trending)`);
    log('DRY RUN complete, no writes performed');
    return;
  }

  // Execute research
  const results = [];

  // Always include a discovery run for trending content
  const discoveryResult = await runDiscovery();
  results.push(discoveryResult);

  // Research selected topics sequentially (to respect rate limits)
  for (const { key, topic } of topics) {
    // Small delay between topics to be polite to APIs
    await new Promise(r => setTimeout(r, 2000));
    const result = await researchTopic(key, topic, sources);
    results.push(result);
  }

  // Store all findings
  const storedCount = storeFindings(results, state);

  // Update adaptive weights
  updateEffectiveness(state, results);

  // Update rotation state
  state.runCount++;
  state.lastRun = new Date().toISOString();
  state.sourceRotationIndex = (state.sourceRotationIndex + 1) % SOURCE_ROTATIONS.length;
  state.totalFindingsStored += storedCount;
  state.totalRunDurationMs += (Date.now() - startTime);

  // Track recent topics for suppression
  const researchedKeys = topics.map(t => t.key);
  state.recentTopics = [...researchedKeys, ...state.recentTopics].slice(0, 20);

  // Prune old data periodically (every 10 runs)
  if (state.runCount % 10 === 0) {
    pruneOldData();
  }

  // Save state
  saveState(state);

  const durationMs = Date.now() - startTime;
  const successCount = results.filter(r => r.success).length;
  const totalFindings = results.reduce((sum, r) => sum + r.totalFindings, 0);

  log('');
  log('--- RUN SUMMARY ---');
  log(`Run:            #${state.runCount}`);
  log(`Duration:       ${(durationMs / 1000).toFixed(1)}s`);
  log(`Topics:         ${topics.length} + discovery`);
  log(`Sources:        [${sources.join(', ')}]`);
  log(`Succeeded:      ${successCount}/${results.length}`);
  log(`Findings:       ${totalFindings} found, ${storedCount} new stored`);
  log(`All-time total: ${state.totalFindingsStored}`);
  log('-------------------');
  log('');

  return {
    runNumber: state.runCount,
    durationMs,
    topicsResearched: topics.length,
    sourcesUsed: sources,
    successCount,
    totalFindings,
    newStored: storedCount,
    allTimeTotal: state.totalFindingsStored,
  };
}

// =============================================================================
// CLI
// =============================================================================

if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.includes('--help')) {
    console.log(`
Perpetual Web Learner - Autonomous continuous research system

Usage:
  node perpetual-web-learner.js                          # Normal run
  node perpetual-web-learner.js --status                 # Show state
  node perpetual-web-learner.js --force-topic "query"    # Force a topic
  node perpetual-web-learner.js --dry-run                # Preview without writes

Runs every 6 hours via systemd timer. NO STOPPING CONDITION.

Sources: ArXiv, GitHub, Hacker News, Stack Overflow
Topics:  ${Object.keys(TOPIC_REGISTRY).length} registered, adaptive rotation
Storage: ~/.claude/learning/research/
`);
    process.exit(0);
  }

  if (args.includes('--status')) {
    const state = loadState();
    console.log(JSON.stringify(state, null, 2));
    process.exit(0);
  }

  const options = {};
  if (args.includes('--dry-run')) options.dryRun = true;

  const forceIdx = args.indexOf('--force-topic');
  if (forceIdx >= 0 && args[forceIdx + 1]) {
    options.forceTopic = args[forceIdx + 1];
  }

  run(options)
    .then((result) => {
      if (result) {
        log(`Run complete. Exit 0.`);
      }
      process.exit(0);
    })
    .catch((err) => {
      log(`FATAL: ${err.message}`);
      log(err.stack);
      process.exit(1);
    });
}

module.exports = { run, loadState, selectTopics, TOPIC_REGISTRY };
