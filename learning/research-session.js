#!/usr/bin/env node
/**
 * Research Session Orchestrator
 *
 * Coordinates research across multiple sources (ArXiv, GitHub, Stack Overflow,
 * Hacker News) and merges findings into a unified, structured report.
 *
 * Phase 1: Manual/user-triggered research sessions.
 * Phase 2 (future): Automated background research on scheduled intervals.
 *
 * Features:
 *   - Run research across all sources in parallel
 *   - Configurable source selection and per-source options
 *   - Merge and deduplicate findings
 *   - Rank findings by relevance and engagement
 *   - Store results via message bus for persistence
 *   - Session history and result caching
 *
 * Usage:
 *   const research = require('./research-session');
 *
 *   // Quick search across all sources
 *   const results = await research.investigate('RAG frameworks');
 *
 *   // Targeted research with options
 *   const results = await research.investigate('React Server Components', {
 *     sources: ['github', 'stackoverflow', 'hackernews'],
 *     github: { language: 'typescript', minStars: 100 },
 *     stackoverflow: { tags: ['reactjs', 'next.js'] },
 *     hackernews: { dateRange: 'month', minPoints: 50 },
 *     maxResultsPerSource: 10
 *   });
 *
 *   // Single-source research
 *   const papers = await research.investigateSource('arxiv', 'attention mechanisms');
 */

const path = require('path');
const fs = require('fs');
const os = require('os');

// Source scrapers
const arxiv = require('./research/arxiv');
const github = require('./research/github');
const stackoverflow = require('./research/stackoverflow');
const hackernews = require('./research/hackernews');

// Message bus for persisting results
let messageBus;
try {
  messageBus = require('./shared/message-bus');
} catch (e) {
  messageBus = null;
}

const RESEARCH_CHANNEL = 'research_findings';
const SESSIONS_DIR = path.join(os.homedir(), '.claude', 'learning', 'research', 'sessions');

/**
 * Source registry: maps source names to their scraper modules and default configurations
 */
const SOURCES = {
  arxiv: {
    module: arxiv,
    name: 'ArXiv',
    description: 'Academic papers and preprints',
    defaultOptions: {
      maxResults: 10,
      sortBy: 'relevance'
    },
    search: async (query, options) => {
      const result = await arxiv.search(query, {
        maxResults: options.maxResults || 10,
        sortBy: options.sortBy || 'relevance',
        category: options.category || null
      });
      return arxiv.toFinding(result);
    }
  },
  github: {
    module: github,
    name: 'GitHub',
    description: 'Repositories, code, and implementations',
    defaultOptions: {
      perPage: 10,
      sort: 'stars',
      minStars: null,
      language: null
    },
    search: async (query, options) => {
      const result = await github.searchRepos(query, {
        perPage: options.perPage || options.maxResults || 10,
        sort: options.sort || 'stars',
        language: options.language || null,
        minStars: options.minStars || null
      });
      return github.toFinding(result);
    }
  },
  stackoverflow: {
    module: stackoverflow,
    name: 'Stack Overflow',
    description: 'Q&A with top-voted answers',
    defaultOptions: {
      pageSize: 10,
      sort: 'relevance',
      accepted: false,
      tags: null
    },
    search: async (query, options) => {
      if (options.tags && options.tags.length > 0) {
        const result = await stackoverflow.topAnswers(options.tags[0], query, {
          maxQuestions: options.maxQuestions || 5,
          answersPerQuestion: options.answersPerQuestion || 3
        });
        return stackoverflow.toFinding(result);
      }
      const result = await stackoverflow.search(query, {
        pageSize: options.pageSize || options.maxResults || 10,
        sort: options.sort || 'relevance',
        accepted: options.accepted || false,
        tags: options.tags || null
      });
      return stackoverflow.toFinding(result);
    }
  },
  hackernews: {
    module: hackernews,
    name: 'Hacker News',
    description: 'Tech news and community discussion',
    defaultOptions: {
      hitsPerPage: 10,
      dateRange: 'month',
      minPoints: null,
      minComments: null
    },
    search: async (query, options) => {
      const result = await hackernews.search(query, {
        hitsPerPage: options.hitsPerPage || options.maxResults || 10,
        dateRange: options.dateRange || 'month',
        minPoints: options.minPoints || null,
        minComments: options.minComments || null,
        sortBy: options.sortBy || 'relevance'
      });
      return hackernews.toFinding(result);
    }
  }
};

/**
 * Generate a unique session ID
 * @returns {string} Session ID
 */
function generateSessionId() {
  const ts = new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19);
  const rand = Math.random().toString(36).substring(2, 8);
  return `research_${ts}_${rand}`;
}

/**
 * Run research across multiple sources for a given query
 *
 * @param {string} query - Research query/topic
 * @param {object} [options] - Research options
 * @param {string[]} [options.sources] - Sources to search (default: all)
 * @param {number} [options.maxResultsPerSource=10] - Max results per source
 * @param {boolean} [options.persist=true] - Store results via message bus
 * @param {object} [options.arxiv] - ArXiv-specific options
 * @param {object} [options.github] - GitHub-specific options
 * @param {object} [options.stackoverflow] - Stack Overflow-specific options
 * @param {object} [options.hackernews] - Hacker News-specific options
 * @returns {Promise<object>} Unified research results
 */
async function investigate(query, options = {}) {
  const sessionId = generateSessionId();
  const startTime = Date.now();
  const sourcesToSearch = options.sources || Object.keys(SOURCES);

  // Validate requested sources
  const validSources = sourcesToSearch.filter((s) => SOURCES[s]);
  const invalidSources = sourcesToSearch.filter((s) => !SOURCES[s]);

  if (validSources.length === 0) {
    throw new Error(`No valid sources specified. Available: ${Object.keys(SOURCES).join(', ')}`);
  }

  // Run all source searches in parallel
  const searchPromises = validSources.map(async (sourceName) => {
    const source = SOURCES[sourceName];
    const sourceOptions = {
      ...source.defaultOptions,
      maxResults: options.maxResultsPerSource || 10,
      ...(options[sourceName] || {})
    };

    try {
      const finding = await source.search(query, sourceOptions);
      return {
        sourceName,
        status: 'success',
        finding
      };
    } catch (error) {
      return {
        sourceName,
        status: 'error',
        error: error.message,
        finding: {
          source: sourceName,
          type: 'error',
          timestamp: new Date().toISOString(),
          query,
          totalAvailable: 0,
          resultCount: 0,
          findings: [],
          error: error.message
        }
      };
    }
  });

  const sourceResults = await Promise.all(searchPromises);

  // Build the unified report
  const durationMs = Date.now() - startTime;
  const successSources = sourceResults.filter((r) => r.status === 'success');
  const errorSources = sourceResults.filter((r) => r.status === 'error');

  // Merge all findings into a single ranked list
  const allFindings = [];
  for (const result of sourceResults) {
    const findings = result.finding.findings || [];
    for (const finding of findings) {
      allFindings.push({
        ...finding,
        source: result.sourceName,
        sourceType: result.finding.type
      });
    }
  }

  // Rank findings by engagement/relevance signals
  const rankedFindings = rankFindings(allFindings);

  const report = {
    sessionId,
    query,
    timestamp: new Date().toISOString(),
    durationMs,
    sources: {
      searched: validSources,
      succeeded: successSources.map((r) => r.sourceName),
      failed: errorSources.map((r) => ({ source: r.sourceName, error: r.error })),
      invalid: invalidSources
    },
    summary: {
      totalFindings: allFindings.length,
      bySource: validSources.reduce((acc, name) => {
        const result = sourceResults.find((r) => r.sourceName === name);
        acc[name] = result ? (result.finding.resultCount || 0) : 0;
        return acc;
      }, {}),
      topFindings: rankedFindings.slice(0, 5)
    },
    sourceResults: sourceResults.reduce((acc, r) => {
      acc[r.sourceName] = r.finding;
      return acc;
    }, {}),
    allFindings: rankedFindings
  };

  // Persist results
  if (options.persist !== false) {
    persistSession(report);
  }

  return report;
}

/**
 * Research a single source
 * @param {string} sourceName - Source name (arxiv, github, stackoverflow, hackernews)
 * @param {string} query - Search query
 * @param {object} [options] - Source-specific options
 * @returns {Promise<object>} Source-specific finding
 */
async function investigateSource(sourceName, query, options = {}) {
  const source = SOURCES[sourceName];
  if (!source) {
    throw new Error(`Unknown source: ${sourceName}. Available: ${Object.keys(SOURCES).join(', ')}`);
  }

  const sourceOptions = {
    ...source.defaultOptions,
    ...options
  };

  return source.search(query, sourceOptions);
}

/**
 * Rank findings by relevance and engagement signals
 * @param {array} findings - Unranked findings from all sources
 * @returns {array} Ranked findings (highest relevance first)
 */
function rankFindings(findings) {
  return findings.map((finding) => {
    let score = 0;

    // GitHub: stars, forks
    if (finding.metrics) {
      score += Math.log10((finding.metrics.stars || 0) + 1) * 10;
      score += Math.log10((finding.metrics.forks || 0) + 1) * 5;
    }

    // Hacker News: points, comments
    if (finding.points !== undefined) {
      score += Math.log10((finding.points || 0) + 1) * 10;
    }
    if (finding.commentCount !== undefined) {
      score += Math.log10((finding.commentCount || 0) + 1) * 5;
    }
    if (finding.engagementScore) {
      score += Math.log10(finding.engagementScore + 1) * 8;
    }

    // Stack Overflow: question score, view count
    if (finding.questionScore !== undefined) {
      score += Math.log10((finding.questionScore || 0) + 1) * 10;
    }
    if (finding.score !== undefined && finding.source === 'stackoverflow') {
      score += Math.log10((finding.score || 0) + 1) * 10;
    }
    if (finding.viewCount !== undefined) {
      score += Math.log10((finding.viewCount || 0) + 1) * 3;
    }

    // ArXiv: relevance indicators
    if (finding.relevanceIndicators) {
      if (finding.relevanceIndicators.hasMethodology) score += 5;
      if (finding.relevanceIndicators.hasFindings) score += 5;
      if (finding.relevanceIndicators.isNovel) score += 8;
      score += (finding.relevanceIndicators.keywordCount || 0) * 1;
    }

    // Has a URL (more actionable)
    if (finding.url) score += 2;

    return { ...finding, relevanceScore: Math.round(score * 100) / 100 };
  }).sort((a, b) => b.relevanceScore - a.relevanceScore);
}

/**
 * Persist session results to the message bus and filesystem
 * @param {object} report - Research report
 */
function persistSession(report) {
  // Post to message bus if available
  if (messageBus) {
    try {
      messageBus.postMessage(RESEARCH_CHANNEL, {
        type: 'research_session',
        sessionId: report.sessionId,
        query: report.query,
        sources: report.sources.succeeded,
        totalFindings: report.summary.totalFindings,
        durationMs: report.durationMs,
        topFinding: report.summary.topFindings[0] || null
      });
    } catch (e) {
      // Non-fatal: log but continue
    }
  }

  // Save full session to filesystem
  try {
    if (!fs.existsSync(SESSIONS_DIR)) {
      fs.mkdirSync(SESSIONS_DIR, { recursive: true });
    }
    const sessionFile = path.join(SESSIONS_DIR, `${report.sessionId}.json`);
    fs.writeFileSync(sessionFile, JSON.stringify(report, null, 2), 'utf8');
  } catch (e) {
    // Non-fatal: filesystem save is best-effort
  }
}

/**
 * List previous research sessions
 * @param {number} [limit=20] - Max sessions to return
 * @returns {array} Session summaries (newest first)
 */
function listSessions(limit = 20) {
  if (!fs.existsSync(SESSIONS_DIR)) {
    return [];
  }

  const files = fs.readdirSync(SESSIONS_DIR)
    .filter((f) => f.endsWith('.json'))
    .sort()
    .reverse()
    .slice(0, limit);

  return files.map((f) => {
    try {
      const data = JSON.parse(fs.readFileSync(path.join(SESSIONS_DIR, f), 'utf8'));
      return {
        sessionId: data.sessionId,
        query: data.query,
        timestamp: data.timestamp,
        sources: data.sources.succeeded,
        totalFindings: data.summary.totalFindings,
        durationMs: data.durationMs,
        file: path.join(SESSIONS_DIR, f)
      };
    } catch (e) {
      return { file: f, error: e.message };
    }
  });
}

/**
 * Load a previous research session by ID
 * @param {string} sessionId - Session ID
 * @returns {object|null} Full session report or null if not found
 */
function loadSession(sessionId) {
  const sessionFile = path.join(SESSIONS_DIR, `${sessionId}.json`);
  if (!fs.existsSync(sessionFile)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(sessionFile, 'utf8'));
}

/**
 * Get available sources and their descriptions
 * @returns {object} Source descriptions
 */
function availableSources() {
  return Object.entries(SOURCES).reduce((acc, [key, source]) => {
    acc[key] = {
      name: source.name,
      description: source.description,
      defaultOptions: source.defaultOptions
    };
    return acc;
  }, {});
}

/**
 * Run a trending/discovery research session (no specific query)
 * Fetches trending content from each source
 * @param {object} [options] - Options per source
 * @param {number} [options.count=10] - Items per source
 * @returns {Promise<object>} Discovery report
 */
async function discover(options = {}) {
  const sessionId = generateSessionId();
  const startTime = Date.now();
  const count = options.count || 10;

  const discoveryPromises = [
    // ArXiv: recent ML papers
    (async () => {
      try {
        const result = await arxiv.recentPapers(
          options.arxivCategory || 'cs.AI', count
        );
        return { source: 'arxiv', status: 'success', finding: arxiv.toFinding(result) };
      } catch (e) {
        return { source: 'arxiv', status: 'error', error: e.message };
      }
    })(),

    // GitHub: trending repos
    (async () => {
      try {
        const result = await github.trending(
          options.githubLanguage || null,
          options.trendingPeriod || 'weekly',
          count
        );
        return { source: 'github', status: 'success', finding: github.toFinding(result) };
      } catch (e) {
        return { source: 'github', status: 'error', error: e.message };
      }
    })(),

    // HN: front page
    (async () => {
      try {
        const result = await hackernews.frontPage(count);
        return { source: 'hackernews', status: 'success', finding: hackernews.toFinding(result) };
      } catch (e) {
        return { source: 'hackernews', status: 'error', error: e.message };
      }
    })()
  ];

  const results = await Promise.all(discoveryPromises);
  const durationMs = Date.now() - startTime;

  const allFindings = [];
  for (const result of results) {
    if (result.finding && result.finding.findings) {
      for (const f of result.finding.findings) {
        allFindings.push({ ...f, source: result.source });
      }
    }
  }

  const report = {
    sessionId,
    type: 'discovery',
    query: null,
    timestamp: new Date().toISOString(),
    durationMs,
    sources: {
      searched: results.map((r) => r.source),
      succeeded: results.filter((r) => r.status === 'success').map((r) => r.source),
      failed: results.filter((r) => r.status === 'error').map((r) => ({
        source: r.source, error: r.error
      }))
    },
    summary: {
      totalFindings: allFindings.length,
      bySource: results.reduce((acc, r) => {
        acc[r.source] = r.finding ? (r.finding.resultCount || 0) : 0;
        return acc;
      }, {})
    },
    sourceResults: results.reduce((acc, r) => {
      acc[r.source] = r.finding || { error: r.error };
      return acc;
    }, {}),
    allFindings: rankFindings(allFindings)
  };

  if (options.persist !== false) {
    persistSession(report);
  }

  return report;
}

// CLI support: run from command line
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === '--help') {
    console.log(`
Research Session Orchestrator

Usage:
  node research-session.js <query>              Search all sources
  node research-session.js --discover           Trending/discovery mode
  node research-session.js --source <src> <q>   Search single source
  node research-session.js --list               List past sessions
  node research-session.js --load <sessionId>   Load a past session
  node research-session.js --sources            List available sources

Sources: ${Object.keys(SOURCES).join(', ')}

Examples:
  node research-session.js "LLM agents frameworks"
  node research-session.js --source arxiv "attention mechanisms"
  node research-session.js --discover
`);
    process.exit(0);
  }

  (async () => {
    try {
      let result;

      if (args[0] === '--discover') {
        result = await discover();
      } else if (args[0] === '--source' && args.length >= 3) {
        result = await investigateSource(args[1], args.slice(2).join(' '));
      } else if (args[0] === '--list') {
        result = listSessions();
      } else if (args[0] === '--load' && args[1]) {
        result = loadSession(args[1]);
        if (!result) {
          console.error(`Session not found: ${args[1]}`);
          process.exit(1);
        }
      } else if (args[0] === '--sources') {
        result = availableSources();
      } else {
        const query = args.join(' ');
        result = await investigate(query);
      }

      console.log(JSON.stringify(result, null, 2));
    } catch (e) {
      console.error(`Error: ${e.message}`);
      process.exit(1);
    }
  })();
}

module.exports = {
  // Primary API
  investigate,
  investigateSource,
  discover,

  // Session management
  listSessions,
  loadSession,

  // Utilities
  availableSources,
  rankFindings,

  // Expose for testing
  _internals: {
    SOURCES,
    generateSessionId,
    persistSession,
    SESSIONS_DIR,
    RESEARCH_CHANNEL
  }
};
