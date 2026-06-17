#!/usr/bin/env node
/**
 * Hacker News Research Scraper
 *
 * Fetches stories and comments from Hacker News using the official Firebase API
 * and the Algolia search API. Returns structured findings for the research framework.
 *
 * APIs used:
 *   - HN Firebase API: https://hacker-news.firebaseio.com/v0/
 *   - HN Algolia Search: https://hn.algolia.com/api/v1/
 *
 * Features:
 *   - Get front page (top stories)
 *   - Get best/new/ask/show stories
 *   - Search stories by keyword
 *   - Fetch top comments for stories
 *   - Filter by date range, points, comment count
 *
 * Usage:
 *   const hn = require('./research/hackernews');
 *   const front = await hn.frontPage(10);
 *   const results = await hn.search('LLM agents', { dateRange: 'month' });
 *   const comments = await hn.getTopComments(storyId, 5);
 */

const https = require('https');

const HN_API_BASE = 'https://hacker-news.firebaseio.com/v0';
const ALGOLIA_API_BASE = 'https://hn.algolia.com/api/v1';

/**
 * Make an HTTPS GET request and return parsed JSON
 * @param {string} url - Full URL to fetch
 * @returns {Promise<object>} Parsed JSON response
 */
function httpGetJson(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { timeout: 30000 }, (res) => {
      if (res.statusCode !== 200) {
        reject(new Error(`HTTP ${res.statusCode}: ${res.statusMessage}`));
        return;
      }
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        const body = Buffer.concat(chunks).toString('utf8');
        try {
          resolve(JSON.parse(body));
        } catch (e) {
          reject(new Error(`Failed to parse JSON: ${e.message}`));
        }
      });
      res.on('error', reject);
    });
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('Request timed out'));
    });
  });
}

/**
 * Fetch a single HN item by ID
 * @param {number} id - Item ID
 * @returns {Promise<object|null>} Item data or null if not found
 */
async function getItem(id) {
  try {
    return await httpGetJson(`${HN_API_BASE}/item/${id}.json`);
  } catch (e) {
    return null;
  }
}

/**
 * Fetch multiple items in parallel with concurrency limit
 * @param {number[]} ids - Array of item IDs
 * @param {number} [concurrency=5] - Max concurrent requests
 * @returns {Promise<object[]>} Array of items (nulls filtered out)
 */
async function getItems(ids, concurrency = 5) {
  const results = [];

  for (let i = 0; i < ids.length; i += concurrency) {
    const batch = ids.slice(i, i + concurrency);
    const batchResults = await Promise.all(batch.map(getItem));
    results.push(...batchResults);
  }

  return results.filter(Boolean);
}

/**
 * Parse an HN item into a clean story structure
 * @param {object} item - Raw HN API item
 * @returns {object} Parsed story
 */
function parseStory(item) {
  if (!item) return null;

  return {
    id: item.id,
    title: item.title || '',
    url: item.url || null,
    hnUrl: `https://news.ycombinator.com/item?id=${item.id}`,
    points: item.score || 0,
    author: item.by || '',
    commentCount: item.descendants || 0,
    commentIds: item.kids || [],
    createdAt: item.time ? new Date(item.time * 1000).toISOString() : null,
    type: item.type || 'story',
    text: item.text || null // For Ask HN / text posts
  };
}

/**
 * Parse an HN comment item
 * @param {object} item - Raw HN API comment item
 * @returns {object} Parsed comment
 */
function parseComment(item) {
  if (!item || item.deleted || item.dead) return null;

  return {
    id: item.id,
    text: stripHtmlTags(item.text || ''),
    author: item.by || '',
    createdAt: item.time ? new Date(item.time * 1000).toISOString() : null,
    parentId: item.parent || null,
    childIds: item.kids || [],
    childCount: (item.kids || []).length
  };
}

/**
 * Strip HTML tags from comment text
 * @param {string} html - HTML string
 * @returns {string} Plain text
 */
function stripHtmlTags(html) {
  if (!html) return '';
  return html
    .replace(/<p>/g, '\n\n')
    .replace(/<br\s*\/?>/g, '\n')
    .replace(/<a[^>]*href="([^"]*)"[^>]*>[^<]*<\/a>/g, '$1')
    .replace(/<code>([\s\S]*?)<\/code>/g, '`$1`')
    .replace(/<pre>([\s\S]*?)<\/pre>/g, '\n```\n$1\n```\n')
    .replace(/<i>([\s\S]*?)<\/i>/g, '$1')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&#x2F;/g, '/')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/**
 * Get front page stories (top stories)
 * @param {number} [count=10] - Number of stories to fetch
 * @returns {Promise<object>} { source, count, stories: [...] }
 */
async function frontPage(count = 10) {
  const storyIds = await httpGetJson(`${HN_API_BASE}/topstories.json`);
  const topIds = storyIds.slice(0, count);
  const items = await getItems(topIds);
  const stories = items.map(parseStory).filter(Boolean);

  return {
    source: 'hackernews',
    type: 'front_page',
    timestamp: new Date().toISOString(),
    returned: stories.length,
    stories
  };
}

/**
 * Get best stories (highest-rated recent stories)
 * @param {number} [count=10] - Number of stories
 * @returns {Promise<object>} { source, count, stories: [...] }
 */
async function bestStories(count = 10) {
  const storyIds = await httpGetJson(`${HN_API_BASE}/beststories.json`);
  const topIds = storyIds.slice(0, count);
  const items = await getItems(topIds);
  const stories = items.map(parseStory).filter(Boolean);

  return {
    source: 'hackernews',
    type: 'best',
    timestamp: new Date().toISOString(),
    returned: stories.length,
    stories
  };
}

/**
 * Get newest stories
 * @param {number} [count=10] - Number of stories
 * @returns {Promise<object>} { source, count, stories: [...] }
 */
async function newStories(count = 10) {
  const storyIds = await httpGetJson(`${HN_API_BASE}/newstories.json`);
  const topIds = storyIds.slice(0, count);
  const items = await getItems(topIds);
  const stories = items.map(parseStory).filter(Boolean);

  return {
    source: 'hackernews',
    type: 'new',
    timestamp: new Date().toISOString(),
    returned: stories.length,
    stories
  };
}

/**
 * Get Ask HN stories
 * @param {number} [count=10] - Number of stories
 * @returns {Promise<object>} { source, count, stories: [...] }
 */
async function askStories(count = 10) {
  const storyIds = await httpGetJson(`${HN_API_BASE}/askstories.json`);
  const topIds = storyIds.slice(0, count);
  const items = await getItems(topIds);
  const stories = items.map(parseStory).filter(Boolean);

  return {
    source: 'hackernews',
    type: 'ask_hn',
    timestamp: new Date().toISOString(),
    returned: stories.length,
    stories
  };
}

/**
 * Get Show HN stories
 * @param {number} [count=10] - Number of stories
 * @returns {Promise<object>} { source, count, stories: [...] }
 */
async function showStories(count = 10) {
  const storyIds = await httpGetJson(`${HN_API_BASE}/showstories.json`);
  const topIds = storyIds.slice(0, count);
  const items = await getItems(topIds);
  const stories = items.map(parseStory).filter(Boolean);

  return {
    source: 'hackernews',
    type: 'show_hn',
    timestamp: new Date().toISOString(),
    returned: stories.length,
    stories
  };
}

/**
 * Get top comments for a story, sorted by depth-first with nested replies
 * @param {number} storyId - HN story ID
 * @param {number} [maxComments=10] - Max top-level comments to fetch
 * @param {number} [maxDepth=2] - Max reply depth to follow
 * @returns {Promise<object>} { storyId, comments: [...] }
 */
async function getTopComments(storyId, maxComments = 10, maxDepth = 2) {
  const story = await getItem(storyId);
  if (!story || !story.kids || story.kids.length === 0) {
    return {
      storyId,
      source: 'hackernews',
      storyTitle: story ? story.title : '',
      returned: 0,
      comments: []
    };
  }

  const topCommentIds = story.kids.slice(0, maxComments);
  const topComments = await getItems(topCommentIds);

  const comments = [];
  for (const commentItem of topComments) {
    const parsed = parseComment(commentItem);
    if (!parsed) continue;

    // Fetch replies up to maxDepth
    if (maxDepth > 0 && parsed.childIds.length > 0) {
      parsed.replies = await fetchReplies(parsed.childIds, maxDepth - 1, 3);
    } else {
      parsed.replies = [];
    }

    comments.push(parsed);
  }

  return {
    storyId,
    source: 'hackernews',
    storyTitle: story.title || '',
    returned: comments.length,
    comments
  };
}

/**
 * Recursively fetch reply comments
 * @param {number[]} childIds - Child comment IDs
 * @param {number} depthRemaining - Remaining depth to traverse
 * @param {number} maxPerLevel - Max replies to fetch per level
 * @returns {Promise<array>} Nested comment array
 */
async function fetchReplies(childIds, depthRemaining, maxPerLevel) {
  const ids = childIds.slice(0, maxPerLevel);
  const items = await getItems(ids);
  const replies = [];

  for (const item of items) {
    const parsed = parseComment(item);
    if (!parsed) continue;

    if (depthRemaining > 0 && parsed.childIds.length > 0) {
      parsed.replies = await fetchReplies(parsed.childIds, depthRemaining - 1, maxPerLevel);
    } else {
      parsed.replies = [];
    }

    replies.push(parsed);
  }

  return replies;
}

/**
 * Search HN stories via the Algolia API
 * @param {string} query - Search query
 * @param {object} [options] - Search options
 * @param {string} [options.dateRange] - Filter: 'day', 'week', 'month', 'year'
 * @param {number} [options.minPoints] - Minimum points
 * @param {number} [options.minComments] - Minimum comments
 * @param {number} [options.hitsPerPage=10] - Results per page
 * @param {string} [options.type='story'] - Type: story, comment, poll
 * @param {string} [options.sortBy='relevance'] - Sort: relevance, date
 * @returns {Promise<object>} { query, totalHits, stories: [...] }
 */
async function search(query, options = {}) {
  const endpoint = options.sortBy === 'date' ? 'search_by_date' : 'search';

  const params = {
    query,
    tags: options.type || 'story',
    hitsPerPage: options.hitsPerPage || 10
  };

  // Date range filter
  if (options.dateRange) {
    const now = Math.floor(Date.now() / 1000);
    const ranges = {
      day: 86400,
      week: 604800,
      month: 2592000,
      year: 31536000
    };
    const seconds = ranges[options.dateRange] || ranges.month;
    params.numericFilters = `created_at_i>${now - seconds}`;
  }

  // Points/comments filter
  const numericFilters = [];
  if (params.numericFilters) {
    numericFilters.push(params.numericFilters);
    delete params.numericFilters;
  }
  if (options.minPoints) {
    numericFilters.push(`points>=${options.minPoints}`);
  }
  if (options.minComments) {
    numericFilters.push(`num_comments>=${options.minComments}`);
  }
  if (numericFilters.length > 0) {
    params.numericFilters = numericFilters.join(',');
  }

  const queryString = Object.entries(params)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&');

  const url = `${ALGOLIA_API_BASE}/${endpoint}?${queryString}`;
  const data = await httpGetJson(url);

  const stories = (data.hits || []).map((hit) => ({
    id: parseInt(hit.objectID, 10),
    title: hit.title || '',
    url: hit.url || null,
    hnUrl: `https://news.ycombinator.com/item?id=${hit.objectID}`,
    points: hit.points || 0,
    author: hit.author || '',
    commentCount: hit.num_comments || 0,
    createdAt: hit.created_at || null,
    storyText: hit.story_text ? stripHtmlTags(hit.story_text) : null,
    tags: hit._tags || []
  }));

  return {
    query,
    source: 'hackernews',
    type: 'search',
    totalHits: data.nbHits || 0,
    returned: stories.length,
    stories
  };
}

/**
 * Search for HN comments on a topic
 * @param {string} query - Search query
 * @param {object} [options] - Search options (same as search())
 * @returns {Promise<object>} { query, totalHits, comments: [...] }
 */
async function searchComments(query, options = {}) {
  const result = await search(query, {
    ...options,
    type: 'comment'
  });

  // Rename stories to comments for clarity
  return {
    query,
    source: 'hackernews',
    type: 'comment_search',
    totalHits: result.totalHits,
    returned: result.returned,
    comments: result.stories.map((s) => ({
      id: s.id,
      text: s.storyText || s.title,
      hnUrl: s.hnUrl,
      author: s.author,
      points: s.points,
      createdAt: s.createdAt
    }))
  };
}

/**
 * Convert results to a structured finding for the research framework
 * @param {object} result - Result from frontPage/search/getTopComments
 * @returns {object} Structured finding
 */
function toFinding(result) {
  // Story results (frontPage, bestStories, search, etc.)
  if (result.stories) {
    return {
      source: 'hackernews',
      type: result.type || 'stories',
      timestamp: new Date().toISOString(),
      query: result.query || null,
      totalAvailable: result.totalHits || result.returned,
      resultCount: result.returned,
      findings: result.stories.map((story) => ({
        title: story.title,
        url: story.url,
        discussionUrl: story.hnUrl,
        points: story.points,
        commentCount: story.commentCount,
        author: story.author,
        createdAt: story.createdAt,
        engagementScore: (story.points || 0) + (story.commentCount || 0) * 2
      }))
    };
  }

  // Comment results (getTopComments)
  if (result.comments) {
    const flatComments = flattenComments(result.comments);
    return {
      source: 'hackernews',
      type: 'discussion',
      timestamp: new Date().toISOString(),
      storyId: result.storyId,
      storyTitle: result.storyTitle,
      resultCount: flatComments.length,
      findings: flatComments.map((comment) => ({
        text: comment.text,
        author: comment.author,
        createdAt: comment.createdAt,
        depth: comment.depth || 0,
        replyCount: comment.childCount || 0
      }))
    };
  }

  return {
    source: 'hackernews',
    type: 'unknown',
    timestamp: new Date().toISOString(),
    findings: []
  };
}

/**
 * Flatten nested comments into a flat list with depth markers
 * @param {array} comments - Nested comment array
 * @param {number} [depth=0] - Current depth
 * @returns {array} Flat array with depth property
 */
function flattenComments(comments, depth = 0) {
  const flat = [];
  for (const comment of comments) {
    flat.push({ ...comment, depth, replies: undefined });
    if (comment.replies && comment.replies.length > 0) {
      flat.push(...flattenComments(comment.replies, depth + 1));
    }
  }
  return flat;
}

module.exports = {
  // Story endpoints
  frontPage,
  bestStories,
  newStories,
  askStories,
  showStories,

  // Comments
  getTopComments,

  // Search (via Algolia)
  search,
  searchComments,

  // Framework integration
  toFinding,

  // Expose internals for testing
  _internals: {
    httpGetJson,
    getItem,
    getItems,
    parseStory,
    parseComment,
    stripHtmlTags,
    flattenComments,
    fetchReplies
  }
};
