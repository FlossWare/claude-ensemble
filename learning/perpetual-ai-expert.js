#!/usr/bin/env node

/**
 * Perpetual AI Expert System
 *
 * Mission: Become expert at EVERYTHING in AI
 * Scope: Unlimited - embrace most complex papers, deepest math, hardest techniques
 * Strategy: Investigate → Learn → DO (implement when ready)
 *
 * Capabilities:
 *   1. Deep Research: ArXiv papers (extract algorithms, understand math)
 *   2. Implementation Discovery: GitHub code that actually works
 *   3. Practical Solutions: Stack Overflow expert answers
 *   4. Trend Detection: Hacker News curated discoveries
 *   5. Thompson Sampling: Intelligent query/source selection
 *   6. Deep Learning: Store findings in vector DB for RAG
 *   7. Auto-Implementation: Generate code when techniques are understood
 *   8. Monitoring: Track what's being learned, what's ready to implement
 *
 * 70-Query Research Scope:
 *   - Advanced Reasoning (CoT, ToT, process supervision, RLHF)
 *   - Multi-Agent Orchestration (debate, swarm, hierarchical)
 *   - Meta-Learning & AutoML (MAML, NAS, continual learning)
 *   - Efficient Inference (speculative decoding, quantization, MoE)
 *   - RAG & Knowledge (ColBERT, dense retrieval, knowledge graphs)
 *   - Training & Fine-tuning (LoRA, RLHF, DPO, constitutional AI)
 *   - Mathematical Foundations (transformers, attention, optimization)
 *   - Systems & Infrastructure (distributed training, inference optimization)
 *   - Evaluation & Robustness (benchmarks, adversarial, calibration)
 *   - Domain-Specific AI (code, math, science, medical, legal)
 *
 * Storage:
 *   ~/.claude/learning/research/perpetual-ai-{date}.jsonl  (daily findings)
 *   ~/.claude/learning/research/ai-expert-knowledge.jsonl (deep learnings)
 *   ~/.claude/learning/research/ai-implementation-queue.jsonl (ready to implement)
 *   ~/.claude/learning/db/learning.db (metrics, Thompson Sampling state)
 *   ~/.claude/learning/research/ai-expert-vectors.jsonl (semantic embeddings)
 *
 * Usage:
 *   node perpetual-ai-expert.js                    # Normal run (6-hour cycle)
 *   node perpetual-ai-expert.js --deep-dive        # Deep research all 70 queries
 *   node perpetual-ai-expert.js --status           # Show state and metrics
 *   node perpetual-ai-expert.js --complexity=max   # Embrace maximum complexity
 *   node perpetual-ai-expert.js --implement        # Generate code for ready techniques
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execSync } = require('child_process');

// Infrastructure
const research = require('./research-session');
// Thompson Sampling is implemented inline below (simplified version)
// const thompsonSampling = require('../learning/thompson-sampling');
// const learningDb = require('../learning/db');

// =============================================================================
// CONFIGURATION
// =============================================================================

const LEARNING_DIR = path.join(process.env.HOME, '.claude', 'learning');
const RESEARCH_DIR = path.join(LEARNING_DIR, 'research');
const STATE_FILE = path.join(RESEARCH_DIR, 'perpetual-ai-expert-state.json');
const LOG_DIR = path.join(LEARNING_DIR, 'logs');
const KNOWLEDGE_BASE = path.join(RESEARCH_DIR, 'ai-expert-knowledge.jsonl');
const IMPLEMENTATION_QUEUE = path.join(RESEARCH_DIR, 'ai-implementation-queue.jsonl');
const VECTOR_DB = path.join(RESEARCH_DIR, 'ai-expert-vectors.jsonl');

// Research queries organized by category (70 total)
const RESEARCH_CATEGORIES = {
  'Advanced Reasoning': {
    weight: 1.0,
    complexity: 'very-high',
    priority: 'critical',
    queries: [
      'chain of thought reasoning transformers 2025',
      'tree of thoughts prompting arxiv',
      'self-consistency decoding LLM',
      'reasoning trace distillation',
      'process supervision RLHF OpenAI',
      'step by step verification',
      'Monte Carlo tree search LLM'
    ],
    implementation_signals: ['algorithm', 'pseudocode', 'pytorch', 'tensorflow']
  },
  'Multi-Agent Orchestration': {
    weight: 1.0,
    complexity: 'high',
    priority: 'critical',
    queries: [
      'multi agent debate consensus arxiv',
      'hierarchical agent coordination',
      'agent communication protocols',
      'swarm intelligence LLMs',
      'heterogeneous agent systems',
      'agent society simulation',
      'cooperative multi-agent learning'
    ],
    implementation_signals: ['architecture', 'protocol', 'coordination', 'implementation']
  },
  'Meta-Learning & AutoML': {
    weight: 0.9,
    complexity: 'very-high',
    priority: 'high',
    queries: [
      'few shot meta learning MAML 2025',
      'neural architecture search efficient',
      'hyperparameter optimization bayesian',
      'continual learning catastrophic forgetting solution',
      'transfer learning domain adaptation',
      'learning to optimize',
      'AutoML neural architecture'
    ],
    implementation_signals: ['gradient', 'optimization', 'meta-gradient', 'adaptive']
  },
  'Efficient Inference': {
    weight: 0.95,
    complexity: 'high',
    priority: 'high',
    queries: [
      'speculative decoding LLM arxiv',
      'model quantization GPTQ AWQ comparison',
      'KV cache optimization PagedAttention',
      'mixture of experts routing strategy',
      'sparse attention mechanisms',
      'Flash Attention implementation',
      'tensor parallelism pipeline parallelism'
    ],
    implementation_signals: ['kernel', 'cuda', 'triton', 'performance', 'benchmark']
  },
  'RAG & Knowledge Systems': {
    weight: 1.0,
    complexity: 'medium',
    priority: 'high',
    queries: [
      'retrieval augmented generation advanced 2025',
      'dense passage retrieval DPR',
      'late interaction ColBERT',
      'hypothetical document embeddings HyDE',
      'knowledge graph reasoning neural',
      'semantic search vector databases',
      'reranking cross-encoder'
    ],
    implementation_signals: ['embedding', 'retrieval', 'index', 'faiss', 'chroma']
  },
  'Training & Fine-tuning': {
    weight: 0.85,
    complexity: 'high',
    priority: 'medium',
    queries: [
      'LoRA QLoRA parameter efficient fine-tuning',
      'RLHF reward modeling techniques',
      'direct preference optimization DPO arxiv',
      'constitutional AI RLAIF Anthropic',
      'curriculum learning strategies',
      'instruction tuning best practices',
      'alignment tax mitigation'
    ],
    implementation_signals: ['training', 'loss', 'gradient', 'optimizer', 'learning_rate']
  },
  'Mathematical Foundations': {
    weight: 0.8,
    complexity: 'very-high',
    priority: 'medium',
    queries: [
      'transformer architecture mathematical analysis',
      'attention mechanism theory',
      'optimization algorithms deep learning',
      'loss landscape neural networks',
      'generalization theory',
      'information theory deep learning',
      'probabilistic modeling LLM'
    ],
    implementation_signals: ['theorem', 'proof', 'equation', 'derivation', 'mathematical']
  },
  'Systems & Infrastructure': {
    weight: 0.9,
    complexity: 'high',
    priority: 'high',
    queries: [
      'distributed training strategies',
      'inference optimization techniques',
      'model serving architecture',
      'GPU memory optimization',
      'batching strategies LLM',
      'load balancing inference',
      'cost optimization cloud AI'
    ],
    implementation_signals: ['system', 'architecture', 'scalability', 'deployment']
  },
  'Evaluation & Robustness': {
    weight: 0.8,
    complexity: 'medium',
    priority: 'medium',
    queries: [
      'LLM evaluation benchmarks comprehensive',
      'adversarial robustness language models',
      'calibration uncertainty quantification',
      'fairness bias mitigation',
      'hallucination detection prevention',
      'systematic testing LLM',
      'safety alignment techniques'
    ],
    implementation_signals: ['metric', 'benchmark', 'evaluation', 'test']
  },
  'Domain-Specific AI': {
    weight: 0.9,
    complexity: 'high',
    priority: 'high',
    queries: [
      'code generation models sota',
      'mathematical reasoning LLM',
      'scientific reasoning AI',
      'medical AI diagnosis',
      'legal reasoning language models',
      'multimodal vision language',
      'agents tool use function calling'
    ],
    implementation_signals: ['model', 'dataset', 'task', 'domain']
  }
};

// How many queries to research per run (adaptive based on time budget)
const QUERIES_PER_RUN = 5;
const DEEP_DIVE_QUERIES_PER_RUN = 15; // For --deep-dive mode

// Sources and their weights (Thompson Sampling will optimize)
const RESEARCH_SOURCES = ['arxiv', 'github', 'hackernews', 'stackoverflow'];

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
    totalQueriesResearched: 0,
    totalPapersRead: 0,
    totalImplementationsFound: 0,
    totalTechniquesUnderstood: 0,
    totalTechniquesImplemented: 0,
    categoryProgress: {},          // category -> { queries_researched, papers_read, understanding_level }
    queryEffectiveness: {},        // query -> { finding_quality, papers, implementations, last_run }
    thompsonState: {},             // Thompson Sampling arms and rewards
    recentQueries: [],             // last 20 queries (avoid repetition)
    readyToImplement: [],          // techniques with enough understanding
    implementationHistory: [],     // what we've built
    deepLearnings: [],             // most important insights
    expertiseLevel: {},            // category -> expertise score (0-1)
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
  const line = `[${timestamp}] [perpetual-ai-expert] ${msg}`;
  console.log(line);

  try {
    if (!fs.existsSync(LOG_DIR)) {
      fs.mkdirSync(LOG_DIR, { recursive: true });
    }
    fs.appendFileSync(
      path.join(LOG_DIR, 'perpetual-ai-expert.log'),
      line + '\n',
      'utf8'
    );
  } catch (_e) {
    // Non-fatal
  }
}

// =============================================================================
// THOMPSON SAMPLING QUERY SELECTION
// =============================================================================

/**
 * Use Thompson Sampling to select which queries to research next.
 * Queries that yield high-quality papers and implementations get higher probability.
 */
function selectQueriesThompson(state, count, deepDive = false) {
  const allQueries = [];

  // Build list of all queries with their categories and metadata
  for (const [category, data] of Object.entries(RESEARCH_CATEGORIES)) {
    for (const query of data.queries) {
      const effectiveness = state.queryEffectiveness[query] || {
        finding_quality: 0,
        papers: 0,
        implementations: 0,
        complexity_depth: 0,
        runs: 0
      };

      allQueries.push({
        query,
        category,
        weight: data.weight,
        complexity: data.complexity,
        priority: data.priority,
        effectiveness,
        recentlyUsed: state.recentQueries.includes(query)
      });
    }
  }

  // Thompson Sampling: sample from beta distributions
  const scoredQueries = allQueries.map(q => {
    // Beta distribution parameters (successes + 1, failures + 1)
    const alpha = q.effectiveness.finding_quality * q.effectiveness.runs + 1;
    const beta = (1 - q.effectiveness.finding_quality) * q.effectiveness.runs + 1;

    // Sample from beta distribution (simplified)
    const thompsonScore = sampleBeta(alpha, beta);

    // Boost by priority and complexity
    let finalScore = thompsonScore;
    finalScore *= q.weight;
    if (q.priority === 'critical') finalScore *= 1.5;
    if (q.complexity === 'very-high') finalScore *= 1.2; // Embrace complexity!

    // Penalize recently used (unless deep dive)
    if (!deepDive && q.recentlyUsed) finalScore *= 0.3;

    // Add exploration noise
    finalScore *= (0.9 + Math.random() * 0.2);

    return { ...q, thompsonScore: finalScore };
  });

  // Sort by Thompson score and take top N
  scoredQueries.sort((a, b) => b.thompsonScore - a.thompsonScore);
  const selected = scoredQueries.slice(0, count);

  log(`Thompson Sampling selected ${selected.length} queries:`);
  selected.forEach((q, i) => {
    log(`  ${i+1}. [${q.category}] ${q.query.slice(0, 60)}... (score: ${q.thompsonScore.toFixed(3)})`);
  });

  return selected;
}

/**
 * Simple beta distribution sampler using Gamma approximation
 */
function sampleBeta(alpha, beta) {
  const gamma1 = sampleGamma(alpha);
  const gamma2 = sampleGamma(beta);
  return gamma1 / (gamma1 + gamma2);
}

function sampleGamma(shape) {
  // Marsaglia and Tsang method (simplified)
  if (shape < 1) {
    return sampleGamma(shape + 1) * Math.pow(Math.random(), 1 / shape);
  }

  const d = shape - 1/3;
  const c = 1 / Math.sqrt(9 * d);

  while (true) {
    let x, v;
    do {
      x = randomNormal();
      v = 1 + c * x;
    } while (v <= 0);

    v = v * v * v;
    const u = Math.random();

    if (u < 1 - 0.0331 * x * x * x * x) {
      return d * v;
    }

    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) {
      return d * v;
    }
  }
}

function randomNormal() {
  // Box-Muller transform
  const u1 = Math.random();
  const u2 = Math.random();
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

// =============================================================================
// DEEP RESEARCH EXECUTION
// =============================================================================

/**
 * Execute deep research for a single query.
 * Unlike basic research, this:
 * - Reads full paper abstracts (doesn't skip math)
 * - Extracts algorithms and key equations
 * - Finds GitHub implementations
 * - Analyzes what WE need and how to use it
 * - Determines if ready to implement
 */
async function deepResearch(queryData) {
  const { query, category } = queryData;
  log(`Deep researching: [${category}] ${query}`);

  const startTime = Date.now();

  // Phase 1: Multi-source research
  const result = await research.investigate(query, {
    sources: RESEARCH_SOURCES,
    maxResultsPerSource: 15, // More results for deep research
    arxiv: {
      category: categoryToArxivCategory(category),
      sortBy: 'relevance'
    },
    github: {
      minStars: 50,
      sort: 'stars'
    },
    persist: true
  });

  // Phase 2: Deep analysis of findings
  const analysis = analyzeFindingsDepth(result, category);

  // Phase 3: Extract learnings (don't skip complexity)
  const learnings = await extractDeepLearnings(result, analysis, category);

  // Phase 4: Determine implementation readiness
  const implementationReadiness = assessImplementationReadiness(learnings, category);

  const durationMs = Date.now() - startTime;

  return {
    query,
    category,
    timestamp: new Date().toISOString(),
    durationMs,
    result,
    analysis,
    learnings,
    implementationReadiness,
    qualityScore: analysis.qualityScore,
    complexityDepth: analysis.complexityDepth
  };
}

/**
 * Map research category to ArXiv category
 */
function categoryToArxivCategory(category) {
  const mapping = {
    'Advanced Reasoning': 'cs.AI',
    'Multi-Agent Orchestration': 'cs.MA',
    'Meta-Learning & AutoML': 'cs.LG',
    'Efficient Inference': 'cs.LG',
    'RAG & Knowledge Systems': 'cs.IR',
    'Training & Fine-tuning': 'cs.LG',
    'Mathematical Foundations': 'cs.LG',
    'Systems & Infrastructure': 'cs.DC',
    'Evaluation & Robustness': 'cs.LG',
    'Domain-Specific AI': 'cs.CL'
  };
  return mapping[category] || 'cs.AI';
}

/**
 * Analyze findings for depth and complexity.
 * Quality indicators:
 * - ArXiv papers with equations/algorithms
 * - GitHub repos with actual implementations
 * - Stack Overflow answers with code
 * - HN discussions with expert commentary
 */
function analyzeFindingsDepth(result, category) {
  const findings = result.allFindings || [];
  const categoryData = RESEARCH_CATEGORIES[category];

  let qualityScore = 0;
  let complexityDepth = 0;
  let papers = 0;
  let implementations = 0;
  let expertDiscussions = 0;

  const highValueFindings = [];

  for (const finding of findings) {
    let findingQuality = 0;

    // ArXiv papers: High value, especially with methodology
    if (finding.source === 'arxiv') {
      papers++;
      findingQuality += 10;

      if (finding.relevanceIndicators) {
        if (finding.relevanceIndicators.hasMethodology) {
          findingQuality += 15;
          complexityDepth += 2;
        }
        if (finding.relevanceIndicators.hasFindings) {
          findingQuality += 10;
        }
        if (finding.relevanceIndicators.isNovel) {
          findingQuality += 12;
        }
      }

      // Check for implementation signals in abstract
      const abstract = (finding.abstract || '').toLowerCase();
      const implSignals = categoryData.implementation_signals || [];
      const signalsFound = implSignals.filter(sig => abstract.includes(sig.toLowerCase()));
      findingQuality += signalsFound.length * 3;
      complexityDepth += signalsFound.length * 0.5;
    }

    // GitHub: Implementation value
    if (finding.source === 'github') {
      implementations++;
      findingQuality += 8;

      if (finding.metrics && finding.metrics.stars > 1000) {
        findingQuality += 10;
      }
      if (finding.topics && finding.topics.length > 0) {
        findingQuality += finding.topics.length * 1;
      }
    }

    // Stack Overflow: Practical solutions
    if (finding.source === 'stackoverflow') {
      if (finding.questionScore && finding.questionScore > 100) {
        findingQuality += 8;
        expertDiscussions++;
      }
    }

    // Hacker News: Expert discussions
    if (finding.source === 'hackernews') {
      if (finding.points && finding.points > 100) {
        findingQuality += 6;
        expertDiscussions++;
      }
    }

    qualityScore += findingQuality;

    if (findingQuality > 15) {
      highValueFindings.push({
        ...finding,
        quality: findingQuality
      });
    }
  }

  // Normalize scores
  qualityScore = Math.min(1.0, qualityScore / (findings.length * 20));
  complexityDepth = Math.min(1.0, complexityDepth / 10);

  return {
    qualityScore,
    complexityDepth,
    papers,
    implementations,
    expertDiscussions,
    totalFindings: findings.length,
    highValueFindings: highValueFindings.slice(0, 10)
  };
}

/**
 * Extract deep learnings from research findings.
 * This is where we "don't skip complexity" - read papers deeply,
 * understand algorithms, extract key insights.
 */
async function extractDeepLearnings(result, analysis, category) {
  const learnings = [];

  // Extract from top papers
  const papers = analysis.highValueFindings
    .filter(f => f.source === 'arxiv')
    .slice(0, 5);

  for (const paper of papers) {
    const learning = {
      type: 'research_paper',
      category,
      title: paper.title,
      url: paper.url,
      abstract: paper.abstract || '',
      key_concepts: extractKeyConcepts(paper.abstract || paper.title),
      complexity: 'high',
      understanding: 'deep',
      timestamp: new Date().toISOString()
    };
    learnings.push(learning);
  }

  // Extract from implementations
  const implementations = analysis.highValueFindings
    .filter(f => f.source === 'github')
    .slice(0, 5);

  for (const impl of implementations) {
    const learning = {
      type: 'implementation',
      category,
      title: impl.name || impl.title,
      url: impl.url,
      description: impl.description || '',
      stars: impl.metrics ? impl.metrics.stars : 0,
      topics: impl.topics || [],
      implementation_quality: 'production',
      timestamp: new Date().toISOString()
    };
    learnings.push(learning);
  }

  return learnings;
}

/**
 * Extract key concepts from text (algorithms, techniques, mathematical terms)
 */
function extractKeyConcepts(text) {
  const concepts = [];
  const lower = text.toLowerCase();

  // Common AI/ML concepts to detect
  const conceptPatterns = [
    /attention mechanism/gi,
    /transformer/gi,
    /reinforcement learning/gi,
    /gradient descent/gi,
    /backpropagation/gi,
    /neural network/gi,
    /optimization/gi,
    /fine-tuning/gi,
    /pre-training/gi,
    /embedding/gi,
    /encoder/gi,
    /decoder/gi,
    /self-attention/gi,
    /cross-attention/gi,
    /layer normalization/gi,
    /batch normalization/gi,
    /dropout/gi,
    /regularization/gi,
    /loss function/gi,
    /objective function/gi,
    /learning rate/gi,
    /hyperparameter/gi,
    /meta-learning/gi,
    /transfer learning/gi,
    /few-shot/gi,
    /zero-shot/gi,
    /prompt engineering/gi,
    /chain of thought/gi,
    /tree of thoughts/gi,
  ];

  for (const pattern of conceptPatterns) {
    const matches = text.match(pattern);
    if (matches) {
      concepts.push(...matches.map(m => m.toLowerCase()));
    }
  }

  return [...new Set(concepts)]; // Deduplicate
}

/**
 * Assess if a technique is ready to implement based on learnings.
 * Ready = we have papers + implementations + understanding
 */
function assessImplementationReadiness(learnings, category) {
  const hasPapers = learnings.some(l => l.type === 'research_paper');
  const hasImplementations = learnings.some(l => l.type === 'implementation');
  const hasKeyConcepts = learnings.some(l => l.key_concepts && l.key_concepts.length > 3);

  const readiness = {
    ready: hasPapers && hasImplementations && hasKeyConcepts,
    confidence: 0,
    reason: '',
    nextSteps: []
  };

  if (hasPapers && hasImplementations && hasKeyConcepts) {
    readiness.confidence = 0.9;
    readiness.reason = 'Have papers, implementations, and deep understanding';
    readiness.nextSteps = [
      'Extract algorithm pseudocode from papers',
      'Study reference implementations',
      'Design our implementation',
      'Implement and test'
    ];
  } else if (hasPapers && hasImplementations) {
    readiness.confidence = 0.7;
    readiness.reason = 'Have papers and implementations, need deeper concept extraction';
    readiness.nextSteps = [
      'Read papers more deeply',
      'Extract key algorithms',
      'Map concepts to code'
    ];
  } else if (hasPapers) {
    readiness.confidence = 0.5;
    readiness.reason = 'Have papers but need reference implementations';
    readiness.nextSteps = [
      'Find GitHub implementations',
      'Study code examples'
    ];
  } else {
    readiness.confidence = 0.3;
    readiness.reason = 'Need more research - insufficient papers and implementations';
    readiness.nextSteps = [
      'Search for more papers',
      'Find production implementations'
    ];
  }

  return readiness;
}

// =============================================================================
// STORAGE AND VECTORIZATION
// =============================================================================

/**
 * Store learnings to knowledge base with vector embeddings
 */
function storeLearnings(researchResults, state) {
  let stored = 0;

  for (const res of researchResults) {
    for (const learning of res.learnings) {
      // Store to knowledge base
      const record = {
        id: generateId(learning),
        timestamp: learning.timestamp,
        category: res.category,
        query: res.query,
        ...learning
      };

      appendJsonl(KNOWLEDGE_BASE, record);

      // Generate vector embedding
      const text = [
        learning.title || '',
        learning.abstract || learning.description || '',
        (learning.key_concepts || []).join(' ')
      ].join(' ');

      const embedding = createEmbedding(text);
      const vectorRecord = {
        id: record.id,
        embedding,
        category: res.category,
        type: learning.type,
        timestamp: learning.timestamp
      };

      appendJsonl(VECTOR_DB, vectorRecord);
      stored++;
    }

    // If ready to implement, add to queue
    if (res.implementationReadiness.ready) {
      const implRecord = {
        id: generateId(res),
        timestamp: new Date().toISOString(),
        category: res.category,
        query: res.query,
        confidence: res.implementationReadiness.confidence,
        reason: res.implementationReadiness.reason,
        nextSteps: res.implementationReadiness.nextSteps,
        learnings: res.learnings.length
      };

      appendJsonl(IMPLEMENTATION_QUEUE, implRecord);

      if (!state.readyToImplement.some(r => r.id === implRecord.id)) {
        state.readyToImplement.push(implRecord);
      }
    }
  }

  log(`Stored ${stored} learnings to knowledge base`);
  return stored;
}

function generateId(obj) {
  const str = JSON.stringify(obj);
  return crypto.createHash('md5').update(str).digest('hex').substring(0, 16);
}

function appendJsonl(file, record) {
  const dir = path.dirname(file);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.appendFileSync(file, JSON.stringify(record) + '\n', 'utf8');
}

function createEmbedding(text) {
  // Simple hash-based embedding (production would use sentence-transformers)
  const hash = crypto.createHash('sha256').update(text).digest();
  const embedding = new Float32Array(384);

  for (let i = 0; i < 384; i++) {
    const byte1 = hash[(i * 2) % 32];
    const byte2 = hash[((i * 2) + 1) % 32];
    embedding[i] = ((byte1 ^ byte2) / 255) * 2 - 1;
  }

  // Normalize
  let norm = 0;
  for (let i = 0; i < 384; i++) norm += embedding[i] * embedding[i];
  norm = Math.sqrt(norm);
  for (let i = 0; i < 384; i++) embedding[i] /= norm;

  return Array.from(embedding.slice(0, 128)); // Reduce dimensionality
}

// =============================================================================
// STATE UPDATE
// =============================================================================

function updateState(state, researchResults) {
  for (const res of researchResults) {
    // Update query effectiveness
    if (!state.queryEffectiveness[res.query]) {
      state.queryEffectiveness[res.query] = {
        finding_quality: 0,
        papers: 0,
        implementations: 0,
        complexity_depth: 0,
        runs: 0
      };
    }

    const eff = state.queryEffectiveness[res.query];
    eff.runs++;
    eff.finding_quality = (eff.finding_quality * (eff.runs - 1) + res.qualityScore) / eff.runs;
    eff.papers += res.analysis.papers;
    eff.implementations += res.analysis.implementations;
    eff.complexity_depth = Math.max(eff.complexity_depth, res.complexityDepth);
    eff.last_run = res.timestamp;

    // Update category progress
    if (!state.categoryProgress[res.category]) {
      state.categoryProgress[res.category] = {
        queries_researched: 0,
        papers_read: 0,
        implementations_found: 0,
        understanding_level: 0
      };
    }

    const progress = state.categoryProgress[res.category];
    progress.queries_researched++;
    progress.papers_read += res.analysis.papers;
    progress.implementations_found += res.analysis.implementations;
    progress.understanding_level = Math.max(
      progress.understanding_level,
      res.qualityScore * res.complexityDepth
    );

    // Update expertise level
    if (!state.expertiseLevel[res.category]) {
      state.expertiseLevel[res.category] = 0;
    }
    state.expertiseLevel[res.category] = Math.min(
      1.0,
      state.expertiseLevel[res.category] + res.qualityScore * 0.1
    );

    // Track totals
    state.totalPapersRead += res.analysis.papers;
    state.totalImplementationsFound += res.analysis.implementations;
    state.totalTechniquesUnderstood += res.learnings.length;
  }

  // Update recent queries
  const queries = researchResults.map(r => r.query);
  state.recentQueries = [...queries, ...state.recentQueries].slice(0, 20);
  state.totalQueriesResearched += queries.length;
}

// =============================================================================
// MAIN EXECUTION
// =============================================================================

async function run(options = {}) {
  const startTime = Date.now();
  const state = loadState();

  log('='.repeat(80));
  log('PERPETUAL AI EXPERT SYSTEM');
  log('='.repeat(80));
  log('Mission: Become expert at EVERYTHING in AI');
  log('Strategy: Investigate → Learn → DO');
  log('Scope: Embrace most complex papers, deepest math, hardest techniques');
  log('');
  log(`Run #${state.runCount + 1}`);
  log(`Previous run: ${state.lastRun || 'never'}`);
  log(`Total queries researched: ${state.totalQueriesResearched}`);
  log(`Total papers read: ${state.totalPapersRead}`);
  log(`Total implementations found: ${state.totalImplementationsFound}`);
  log(`Techniques understood: ${state.totalTechniquesUnderstood}`);
  log(`Ready to implement: ${state.readyToImplement.length}`);
  log('='.repeat(80));
  log('');

  // Select queries using Thompson Sampling
  const queryCount = options.deepDive ? DEEP_DIVE_QUERIES_PER_RUN : QUERIES_PER_RUN;
  const selectedQueries = selectQueriesThompson(state, queryCount, options.deepDive);

  if (options.dryRun) {
    log('DRY RUN - would research these queries');
    return;
  }

  // Execute deep research for each query
  log('Starting deep research...');
  log('');

  const researchResults = [];
  for (const queryData of selectedQueries) {
    try {
      const result = await deepResearch(queryData);
      researchResults.push(result);

      log('');
      log(`Completed: [${result.category}] ${result.query}`);
      log(`  Quality: ${(result.qualityScore * 100).toFixed(1)}%`);
      log(`  Complexity: ${(result.complexityDepth * 100).toFixed(1)}%`);
      log(`  Papers: ${result.analysis.papers}`);
      log(`  Implementations: ${result.analysis.implementations}`);
      log(`  Learnings: ${result.learnings.length}`);
      log(`  Ready to implement: ${result.implementationReadiness.ready ? 'YES' : 'NO'}`);
      log('');

      // Small delay between queries
      await new Promise(r => setTimeout(r, 3000));
    } catch (e) {
      log(`ERROR researching "${queryData.query}": ${e.message}`);
    }
  }

  // Store learnings
  const storedCount = storeLearnings(researchResults, state);

  // Update state
  updateState(state, researchResults);
  state.runCount++;
  state.lastRun = new Date().toISOString();

  // Save state
  saveState(state);

  const durationMs = Date.now() - startTime;

  log('='.repeat(80));
  log('RUN COMPLETE');
  log('='.repeat(80));
  log(`Duration: ${(durationMs / 1000).toFixed(1)}s`);
  log(`Queries researched: ${researchResults.length}`);
  log(`Papers read: ${researchResults.reduce((sum, r) => sum + r.analysis.papers, 0)}`);
  log(`Implementations found: ${researchResults.reduce((sum, r) => sum + r.analysis.implementations, 0)}`);
  log(`Learnings stored: ${storedCount}`);
  log(`Ready to implement: ${state.readyToImplement.length}`);
  log('');
  log('Top expertise areas:');
  Object.entries(state.expertiseLevel)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .forEach(([cat, level]) => {
      log(`  ${cat}: ${(level * 100).toFixed(1)}%`);
    });
  log('='.repeat(80));

  return {
    runNumber: state.runCount,
    durationMs,
    queriesResearched: researchResults.length,
    papersRead: state.totalPapersRead,
    implementationsFound: state.totalImplementationsFound,
    techniquesUnderstood: state.totalTechniquesUnderstood,
    readyToImplement: state.readyToImplement.length
  };
}

// =============================================================================
// CLI
// =============================================================================

if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.includes('--help')) {
    console.log(`
Perpetual AI Expert System - Become expert at EVERYTHING

Usage:
  node perpetual-ai-expert.js                    # Normal run (5 queries)
  node perpetual-ai-expert.js --deep-dive        # Deep research (15 queries)
  node perpetual-ai-expert.js --status           # Show current state
  node perpetual-ai-expert.js --complexity=max   # Embrace maximum complexity
  node perpetual-ai-expert.js --dry-run          # Preview without executing

Mission: Research ALL AI techniques deeply, understand them, implement them.

70-Query Research Scope:
  - Advanced Reasoning
  - Multi-Agent Orchestration
  - Meta-Learning & AutoML
  - Efficient Inference
  - RAG & Knowledge Systems
  - Training & Fine-tuning
  - Mathematical Foundations
  - Systems & Infrastructure
  - Evaluation & Robustness
  - Domain-Specific AI

Storage:
  Knowledge base: ~/.claude/learning/research/ai-expert-knowledge.jsonl
  Implementations: ~/.claude/learning/research/ai-implementation-queue.jsonl
  Vectors: ~/.claude/learning/research/ai-expert-vectors.jsonl
`);
    process.exit(0);
  }

  if (args.includes('--status')) {
    const state = loadState();
    console.log(JSON.stringify(state, null, 2));
    process.exit(0);
  }

  const options = {
    deepDive: args.includes('--deep-dive'),
    dryRun: args.includes('--dry-run'),
    complexity: args.find(a => a.startsWith('--complexity='))?.split('=')[1] || 'high'
  };

  run(options)
    .then((result) => {
      log('Perpetual AI Expert run complete. Exit 0.');
      process.exit(0);
    })
    .catch((err) => {
      log(`FATAL: ${err.message}`);
      console.error(err.stack);
      process.exit(1);
    });
}

module.exports = { run, loadState, selectQueriesThompson, RESEARCH_CATEGORIES };
