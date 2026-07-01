#!/usr/bin/env node
/**
 * Knowledge System Integration for Perpetual Web Learner
 *
 * Stores web research findings in PostgreSQL knowledge.entries table
 * instead of (or in addition to) JSONL files.
 *
 * Benefits:
 * - Semantic search via pgvector (0.4ms queries)
 * - Provenance tracking
 * - Automatic deduplication
 * - Semantic chunking for large findings
 * - Unified knowledge base across all learning systems
 *
 * Usage:
 *   import { storeWebResearchFindings } from './perpetual-web-learner-knowledge-integration.js';
 *
 *   // In perpetual-web-learner.js storeFindings():
 *   await storeWebResearchFindings(allResults, state);
 */

import { getKnowledgeSystem, isAvailable } from '../shared/knowledge-system-adapter.js';

/**
 * Store web research findings to knowledge system
 *
 * @param {Object[]} allResults - Array of research results from perpetual-web-learner
 * @param {Object} state - Perpetual learner state
 * @returns {Promise<Object>} { stored, skipped, errors }
 */
export async function storeWebResearchFindings(allResults, state) {
  if (!isAvailable()) {
    console.log('  ⚠️  Knowledge system not available - skipping PostgreSQL storage');
    return { stored: 0, skipped: 0, errors: 0, available: false };
  }

  const ks = getKnowledgeSystem();
  let stored = 0;
  let skipped = 0;
  let errors = 0;

  for (const result of allResults) {
    if (!result.success) continue;

    for (const finding of result.allFindings) {
      try {
        // Build content for embedding
        const contentParts = [
          `Title: ${finding.title || finding.name || 'Untitled'}`,
          finding.abstract || finding.description || '',
        ];

        if (finding.topics && finding.topics.length > 0) {
          contentParts.push(`Topics: ${finding.topics.join(', ')}`);
        }
        if (finding.tags && finding.tags.length > 0) {
          contentParts.push(`Tags: ${finding.tags.join(', ')}`);
        }
        if (finding.categories && finding.categories.length > 0) {
          contentParts.push(`Categories: ${finding.categories.join(', ')}`);
        }

        const content = contentParts.filter(Boolean).join('\n\n');

        if (!content.trim()) {
          skipped++;
          continue;
        }

        // Store in knowledge system
        await ks.storeKnowledge({
          content,
          source: finding.source || 'perpetual-web-learner',
          source_type: 'web_synthesis',
          metadata: {
            title: finding.title || finding.name,
            url: finding.url || finding.discussionUrl,
            source_name: finding.source,
            source_type_detail: finding.sourceType,
            topic_key: result.topicKey,
            query: result.query,
            relevance_score: finding.relevanceScore || 0,
            points: finding.points || finding.score || finding.questionScore,
            stars: finding.metrics?.stars,
            comment_count: finding.commentCount,
            topics: finding.topics,
            tags: finding.tags || finding.categories,
            timestamp: new Date().toISOString(),
            // Track which perpetual learner run stored this
            run_count: state.runCount,
            run_timestamp: state.lastRun,
          },
          actor: 'perpetual-web-learner',
        });

        stored++;
      } catch (err) {
        console.error(`  ✗ Failed to store finding: ${err.message}`);
        errors++;
      }
    }
  }

  console.log(`  ✓ Knowledge system: stored ${stored}, skipped ${skipped}, errors ${errors}`);

  return { stored, skipped, errors, available: true };
}

/**
 * Search perpetual web learner findings by semantic similarity
 *
 * @param {string} query - Natural language query
 * @param {Object} [options]
 * @param {number} [options.limit] - Max results (default: 10)
 * @param {string} [options.topicKey] - Filter by topic key
 * @param {string} [options.source] - Filter by source (arxiv, hackernews, etc)
 * @param {number} [options.minSimilarity] - Minimum similarity 0-1 (default: 0.5)
 * @returns {Promise<Object[]>} Results with metadata
 */
export async function searchWebResearch(query, options = {}) {
  if (!isAvailable()) {
    throw new Error('Knowledge system not available');
  }

  const { limit = 10, minSimilarity = 0.5 } = options;

  const ks = getKnowledgeSystem();
  const results = await ks.semanticSearch(query, {
    limit,
    source_type: 'web_synthesis',
    min_similarity: minSimilarity,
  });

  // Optional: filter by topic or source in metadata
  let filtered = results;
  if (options.topicKey) {
    filtered = filtered.filter(r => r.metadata?.topic_key === options.topicKey);
  }
  if (options.source) {
    filtered = filtered.filter(r => r.metadata?.source_name === options.source);
  }

  return filtered;
}

/**
 * Get statistics about perpetual web learner knowledge
 *
 * @returns {Promise<Object>} { total, by_source, by_topic, recent_runs }
 */
export async function getWebResearchStats() {
  if (!isAvailable()) {
    throw new Error('Knowledge system not available');
  }

  const ks = getKnowledgeSystem();
  const stats = await ks.getStats();

  return {
    total_web_synthesis: stats.by_source_type?.web_synthesis || 0,
    total_all: stats.total_entries,
    by_source_type: stats.by_source_type,
  };
}

export default {
  storeWebResearchFindings,
  searchWebResearch,
  getWebResearchStats,
};
