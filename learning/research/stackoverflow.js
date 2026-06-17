#!/usr/bin/env node
/**
 * Stack Overflow Research Scraper
 *
 * Searches Stack Overflow for top answers using the public Stack Exchange API v2.3.
 * Returns structured findings for the research framework.
 *
 * API docs: https://api.stackexchange.com/docs
 * Rate limit: 300 requests/day (unauthenticated), 10000/day (with key)
 *
 * Features:
 *   - Search questions by keyword
 *   - Search by tag (e.g., 'javascript', 'react')
 *   - Get top-voted answers for a topic
 *   - Extract code snippets from answers
 *   - Filter by score, answer count, accepted answers
 *
 * Usage:
 *   const so = require('./research/stackoverflow');
 *   const results = await so.search('React useEffect cleanup');
 *   const tagged = await so.searchByTag('node.js', 'async');
 *   const top = await so.topAnswers('javascript', 'closures');
 */

const https = require('https');
const zlib = require('zlib');

const SO_API_BASE = 'https://api.stackexchange.com/2.3';
const DEFAULT_PAGE_SIZE = 10;

/**
 * Make a Stack Exchange API request.
 * The API always returns gzip-compressed responses.
 * @param {string} endpoint - API path (e.g., '/search/advanced')
 * @param {object} [params] - Query parameters
 * @returns {Promise<object>} Parsed JSON response
 */
function apiRequest(endpoint, params = {}) {
  return new Promise((resolve, reject) => {
    // Always include site parameter
    const allParams = {
      site: 'stackoverflow',
      ...params
    };

    // Add API key if available for higher rate limits
    const apiKey = process.env.STACKEXCHANGE_KEY || process.env.SO_API_KEY;
    if (apiKey) {
      allParams.key = apiKey;
    }

    const queryString = Object.entries(allParams)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join('&');

    const fullPath = `${endpoint}?${queryString}`;
    const fullUrl = `${SO_API_BASE}${fullPath}`;

    const urlObj = new URL(fullUrl);

    const options = {
      hostname: urlObj.hostname,
      path: urlObj.pathname + urlObj.search,
      method: 'GET',
      headers: {
        'Accept-Encoding': 'gzip',
        'User-Agent': 'AI-Learning-Research/1.0'
      },
      timeout: 30000
    };

    const req = https.request(options, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        const buffer = Buffer.concat(chunks);

        // Stack Exchange API always returns gzip
        const decompress = (buf) => {
          return new Promise((resolveDecomp, rejectDecomp) => {
            zlib.gunzip(buf, (err, result) => {
              if (err) {
                // Maybe it was not compressed after all
                rejectDecomp(err);
              } else {
                resolveDecomp(result.toString('utf8'));
              }
            });
          });
        };

        decompress(buffer)
          .catch(() => buffer.toString('utf8'))
          .then((body) => {
            if (res.statusCode !== 200) {
              reject(new Error(`Stack Exchange API ${res.statusCode}: ${body.substring(0, 300)}`));
              return;
            }
            try {
              const data = JSON.parse(body);
              if (data.error_id) {
                reject(new Error(`SE API error ${data.error_id}: ${data.error_message}`));
                return;
              }
              resolve(data);
            } catch (e) {
              reject(new Error(`Failed to parse SE response: ${e.message}`));
            }
          });
      });
      res.on('error', reject);
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Stack Exchange API request timed out'));
    });
    req.end();
  });
}

/**
 * Decode HTML entities commonly found in SE API responses
 * @param {string} html - HTML-encoded string
 * @returns {string} Decoded string
 */
function decodeHtml(html) {
  if (!html) return '';
  return html
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/g, "'")
    .replace(/&#x2F;/g, '/');
}

/**
 * Strip HTML tags from a string, preserving code blocks
 * @param {string} html - HTML string
 * @returns {string} Plain text with code blocks preserved
 */
function stripHtml(html) {
  if (!html) return '';

  // Extract code blocks first
  const codeBlocks = [];
  let processed = html.replace(/<code>([\s\S]*?)<\/code>/g, (match, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push(decodeHtml(code));
    return `__CODE_BLOCK_${idx}__`;
  });

  // Replace common block elements with newlines
  processed = processed
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n\n')
    .replace(/<\/li>/gi, '\n')
    .replace(/<\/h[1-6]>/gi, '\n\n');

  // Strip remaining tags
  processed = processed.replace(/<[^>]+>/g, '');

  // Restore code blocks
  codeBlocks.forEach((code, idx) => {
    processed = processed.replace(`__CODE_BLOCK_${idx}__`, `\`${code}\``);
  });

  return decodeHtml(processed).replace(/\n{3,}/g, '\n\n').trim();
}

/**
 * Extract code snippets from an HTML answer body
 * @param {string} html - HTML body of an answer
 * @returns {array} Array of code snippet strings
 */
function extractCodeSnippets(html) {
  if (!html) return [];

  const snippets = [];
  const preCodeRegex = /<pre><code[^>]*>([\s\S]*?)<\/code><\/pre>/g;
  let match;
  while ((match = preCodeRegex.exec(html)) !== null) {
    snippets.push(decodeHtml(match[1]).trim());
  }

  return snippets;
}

/**
 * Parse a question from the API response
 * @param {object} item - Raw API question object
 * @returns {object} Parsed question
 */
function parseQuestion(item) {
  return {
    questionId: item.question_id,
    title: decodeHtml(item.title),
    body: item.body ? stripHtml(item.body) : null,
    tags: item.tags || [],
    score: item.score,
    viewCount: item.view_count,
    answerCount: item.answer_count,
    isAnswered: item.is_answered,
    acceptedAnswerId: item.accepted_answer_id || null,
    url: item.link,
    createdAt: item.creation_date ? new Date(item.creation_date * 1000).toISOString() : null,
    lastActivity: item.last_activity_date ? new Date(item.last_activity_date * 1000).toISOString() : null,
    owner: item.owner ? {
      name: item.owner.display_name,
      reputation: item.owner.reputation,
      userId: item.owner.user_id
    } : null
  };
}

/**
 * Parse an answer from the API response
 * @param {object} item - Raw API answer object
 * @returns {object} Parsed answer
 */
function parseAnswer(item) {
  const body = item.body || '';
  return {
    answerId: item.answer_id,
    questionId: item.question_id,
    body: stripHtml(body),
    bodyHtml: body,
    score: item.score,
    isAccepted: item.is_accepted || false,
    codeSnippets: extractCodeSnippets(body),
    createdAt: item.creation_date ? new Date(item.creation_date * 1000).toISOString() : null,
    lastEdited: item.last_edit_date ? new Date(item.last_edit_date * 1000).toISOString() : null,
    url: item.link || null,
    owner: item.owner ? {
      name: item.owner.display_name,
      reputation: item.owner.reputation,
      userId: item.owner.user_id
    } : null
  };
}

/**
 * Search Stack Overflow questions
 * @param {string} query - Search query
 * @param {object} [options] - Search options
 * @param {string} [options.sort='relevance'] - Sort: activity, votes, creation, relevance
 * @param {string} [options.order='desc'] - Order: asc, desc
 * @param {number} [options.pageSize=10] - Results per page
 * @param {boolean} [options.accepted=false] - Only questions with accepted answers
 * @param {number} [options.minScore] - Minimum question score
 * @param {string[]} [options.tags] - Filter by tags
 * @returns {Promise<object>} { query, totalCount, questions: [...] }
 */
async function search(query, options = {}) {
  const params = {
    q: query,
    sort: options.sort || 'relevance',
    order: options.order || 'desc',
    pagesize: options.pageSize || DEFAULT_PAGE_SIZE,
    filter: 'withbody'
  };

  if (options.accepted) {
    params.accepted = 'True';
  }
  if (options.minScore) {
    params.min = options.minScore;
    params.sort = 'votes';
  }
  if (options.tags && options.tags.length > 0) {
    params.tagged = options.tags.join(';');
  }

  const data = await apiRequest('/search/advanced', params);

  const questions = (data.items || []).map(parseQuestion);

  return {
    query,
    source: 'stackoverflow',
    totalCount: data.total || 0,
    returned: questions.length,
    hasMore: data.has_more || false,
    quotaRemaining: data.quota_remaining,
    questions
  };
}

/**
 * Search questions by tag
 * @param {string} tag - Primary tag (e.g., 'javascript', 'python')
 * @param {string} [query] - Optional additional search query
 * @param {object} [options] - Search options (same as search())
 * @returns {Promise<object>} { tag, query, questions: [...] }
 */
async function searchByTag(tag, query = '', options = {}) {
  const tags = [tag];
  if (options.additionalTags) {
    tags.push(...options.additionalTags);
  }

  const searchOpts = {
    ...options,
    tags
  };

  const result = await search(query || tag, searchOpts);
  result.tag = tag;
  return result;
}

/**
 * Get top answers for a specific question
 * @param {number} questionId - Question ID
 * @param {object} [options] - Options
 * @param {string} [options.sort='votes'] - Sort: activity, votes, creation
 * @param {number} [options.pageSize=5] - Max answers to return
 * @returns {Promise<object>} { questionId, answers: [...] }
 */
async function getAnswers(questionId, options = {}) {
  const params = {
    sort: options.sort || 'votes',
    order: 'desc',
    pagesize: options.pageSize || 5,
    filter: 'withbody'
  };

  const data = await apiRequest(`/questions/${questionId}/answers`, params);

  const answers = (data.items || []).map(parseAnswer);

  return {
    questionId,
    source: 'stackoverflow',
    returned: answers.length,
    answers
  };
}

/**
 * Get top-voted answers for a topic (searches, then fetches answers)
 * @param {string} tag - Tag to search
 * @param {string} query - Search query
 * @param {object} [options] - Options
 * @param {number} [options.maxQuestions=3] - Questions to fetch answers for
 * @param {number} [options.answersPerQuestion=3] - Answers per question
 * @returns {Promise<object>} { tag, query, questionsWithAnswers: [...] }
 */
async function topAnswers(tag, query, options = {}) {
  const maxQuestions = options.maxQuestions || 3;
  const answersPerQuestion = options.answersPerQuestion || 3;

  // Search for top questions
  const searchResult = await searchByTag(tag, query, {
    sort: 'votes',
    pageSize: maxQuestions,
    accepted: true
  });

  // Fetch answers for each question
  const questionsWithAnswers = [];
  for (const question of searchResult.questions) {
    try {
      const answersResult = await getAnswers(question.questionId, {
        pageSize: answersPerQuestion
      });
      questionsWithAnswers.push({
        question,
        answers: answersResult.answers
      });
    } catch (e) {
      questionsWithAnswers.push({
        question,
        answers: [],
        error: e.message
      });
    }
  }

  return {
    tag,
    query,
    source: 'stackoverflow',
    questionsSearched: searchResult.totalCount,
    returned: questionsWithAnswers.length,
    questionsWithAnswers
  };
}

/**
 * Get popular tags related to a topic
 * @param {string} query - Tag search query
 * @param {number} [pageSize=10] - Max tags to return
 * @returns {Promise<object>} { query, tags: [...] }
 */
async function relatedTags(query, pageSize = 10) {
  const params = {
    inname: query,
    sort: 'popular',
    order: 'desc',
    pagesize: pageSize
  };

  const data = await apiRequest('/tags', params);

  const tags = (data.items || []).map((item) => ({
    name: item.name,
    count: item.count,
    isRequired: item.is_required || false,
    isModeratorOnly: item.is_moderator_only || false,
    hasSynonyms: item.has_synonyms || false
  }));

  return {
    query,
    source: 'stackoverflow',
    returned: tags.length,
    tags
  };
}

/**
 * Convert search results to a structured finding for the research framework
 * @param {object} searchResult - Result from search/searchByTag/topAnswers
 * @returns {object} Structured finding
 */
function toFinding(searchResult) {
  // Handle topAnswers format
  if (searchResult.questionsWithAnswers) {
    return {
      source: 'stackoverflow',
      type: 'qa_with_answers',
      timestamp: new Date().toISOString(),
      query: searchResult.query,
      tag: searchResult.tag,
      totalAvailable: searchResult.questionsSearched,
      resultCount: searchResult.returned,
      findings: searchResult.questionsWithAnswers.map((qa) => ({
        title: qa.question.title,
        url: qa.question.url,
        questionScore: qa.question.score,
        viewCount: qa.question.viewCount,
        tags: qa.question.tags,
        isAnswered: qa.question.isAnswered,
        topAnswer: qa.answers.length > 0 ? {
          score: qa.answers[0].score,
          isAccepted: qa.answers[0].isAccepted,
          body: qa.answers[0].body,
          codeSnippets: qa.answers[0].codeSnippets,
          author: qa.answers[0].owner
        } : null,
        answerCount: qa.answers.length
      }))
    };
  }

  // Handle basic search format
  return {
    source: 'stackoverflow',
    type: 'questions',
    timestamp: new Date().toISOString(),
    query: searchResult.query,
    tag: searchResult.tag || null,
    totalAvailable: searchResult.totalCount,
    resultCount: searchResult.returned,
    findings: searchResult.questions.map((q) => ({
      title: q.title,
      url: q.url,
      score: q.score,
      viewCount: q.viewCount,
      answerCount: q.answerCount,
      isAnswered: q.isAnswered,
      tags: q.tags,
      createdAt: q.createdAt,
      owner: q.owner
    }))
  };
}

module.exports = {
  search,
  searchByTag,
  getAnswers,
  topAnswers,
  relatedTags,
  toFinding,

  // Expose internals for testing
  _internals: {
    apiRequest,
    parseQuestion,
    parseAnswer,
    extractCodeSnippets,
    stripHtml,
    decodeHtml
  }
};
