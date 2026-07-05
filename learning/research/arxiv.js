#!/usr/bin/env node
/**
 * ArXiv Research Scraper
 *
 * Searches ArXiv papers via the public API, extracts metadata and abstracts,
 * and returns structured findings for the research framework.
 *
 * ArXiv API docs: https://info.arxiv.org/help/api/basics.html
 * Uses the Atom feed endpoint: https://export.arxiv.org/api/query
 *
 * Features:
 *   - Search by keyword, author, or category
 *   - Parse Atom XML responses into structured results
 *   - Extract key insights from abstracts
 *   - Rate-limit compliant (3 second delay between requests)
 *
 * Usage:
 *   const arxiv = require('./research/arxiv');
 *   const results = await arxiv.search('transformer attention mechanism');
 *   const recent = await arxiv.recentPapers('cs.AI', 10);
 */

const https = require('https');
const http = require('http');

const ARXIV_API_BASE = 'https://export.arxiv.org/api/query';
const DEFAULT_MAX_RESULTS = 10;
const REQUEST_DELAY_MS = 3000; // ArXiv asks for 3s between requests

let lastRequestTime = 0;

/**
 * Make an HTTP/HTTPS GET request and return the response body
 * @param {string} requestUrl - Full URL to fetch
 * @returns {Promise<string>} Response body
 */
function httpGet(requestUrl) {
  return new Promise((resolve, reject) => {
    const client = requestUrl.startsWith('https') ? https : http;
    const req = client.get(requestUrl, { timeout: 30000 }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        // Follow redirects
        httpGet(res.headers.location).then(resolve).catch(reject);
        return;
      }
      if (res.statusCode !== 200) {
        reject(new Error(`HTTP ${res.statusCode}: ${res.statusMessage}`));
        return;
      }
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
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
 * Enforce rate limiting between ArXiv API calls
 */
async function rateLimit() {
  const now = Date.now();
  const elapsed = now - lastRequestTime;
  if (elapsed < REQUEST_DELAY_MS) {
    await new Promise((r) => setTimeout(r, REQUEST_DELAY_MS - elapsed));
  }
  lastRequestTime = Date.now();
}

/**
 * Parse an Atom XML entry into a structured paper object.
 * Uses simple regex-based XML parsing to avoid external dependencies.
 * @param {string} entryXml - Raw XML for one <entry> element
 * @returns {object} Parsed paper
 */
function parseEntry(entryXml) {
  const getTag = (xml, tag) => {
    const match = xml.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`));
    return match ? match[1].trim() : '';
  };

  const getAllTags = (xml, tag) => {
    const results = [];
    const regex = new RegExp(`<${tag}([^>]*)>([\\s\\S]*?)</${tag}>`, 'g');
    let match;
    while ((match = regex.exec(xml)) !== null) {
      results.push({ attrs: match[1], content: match[2].trim() });
    }
    return results;
  };

  const getAttr = (attrStr, name) => {
    const match = attrStr.match(new RegExp(`${name}="([^"]*)"`));
    return match ? match[1] : '';
  };

  // Extract self-closing link tags
  const getLinks = (xml) => {
    const results = [];
    const regex = /<link([^>]*?)\/?\s*>/g;
    let match;
    while ((match = regex.exec(xml)) !== null) {
      results.push({
        href: getAttr(match[1], 'href'),
        type: getAttr(match[1], 'type'),
        rel: getAttr(match[1], 'rel'),
        title: getAttr(match[1], 'title')
      });
    }
    return results;
  };

  const id = getTag(entryXml, 'id');
  const title = getTag(entryXml, 'title').replace(/\s+/g, ' ');
  const summary = getTag(entryXml, 'summary').replace(/\s+/g, ' ');
  const published = getTag(entryXml, 'published');
  const updated = getTag(entryXml, 'updated');

  // Extract authors
  const authorBlocks = getAllTags(entryXml, 'author');
  const authors = authorBlocks.map((a) => getTag(a.content, 'name')).filter(Boolean);

  // Extract categories
  const categoryRegex = /<category[^>]*term="([^"]*)"[^>]*\/?\s*>/g;
  const categories = [];
  let catMatch;
  while ((catMatch = categoryRegex.exec(entryXml)) !== null) {
    categories.push(catMatch[1]);
  }

  // Extract links
  const links = getLinks(entryXml);
  const pdfLink = links.find((l) => l.title === 'pdf' || l.type === 'application/pdf');
  const absLink = links.find((l) => l.rel === 'alternate') || links[0];

  // Extract ArXiv ID from the full URL
  const arxivIdMatch = id.match(/abs\/(.+?)(?:v\d+)?$/);
  const arxivId = arxivIdMatch ? arxivIdMatch[1] : id;

  return {
    arxivId,
    title,
    authors,
    abstract: summary,
    categories,
    published,
    updated,
    pdfUrl: pdfLink ? pdfLink.href : `https://arxiv.org/pdf/${arxivId}`,
    absUrl: absLink ? absLink.href : `https://arxiv.org/abs/${arxivId}`,
    source: 'arxiv'
  };
}

/**
 * Parse a full ArXiv API Atom response into structured results
 * @param {string} xml - Full Atom XML response
 * @returns {object} { totalResults, startIndex, itemsPerPage, papers }
 */
function parseAtomResponse(xml) {
  const getTag = (xmlStr, tag) => {
    const match = xmlStr.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`));
    return match ? match[1].trim() : '';
  };

  // Extract opensearch metadata
  const totalResults = parseInt(getTag(xml, 'opensearch:totalResults') || '0', 10);
  const startIndex = parseInt(getTag(xml, 'opensearch:startIndex') || '0', 10);
  const itemsPerPage = parseInt(getTag(xml, 'opensearch:itemsPerPage') || '0', 10);

  // Split into entries
  const entries = [];
  const entryRegex = /<entry>([\s\S]*?)<\/entry>/g;
  let match;
  while ((match = entryRegex.exec(xml)) !== null) {
    entries.push(match[1]);
  }

  const papers = entries.map(parseEntry);

  return { totalResults, startIndex, itemsPerPage, papers };
}

/**
 * Build an ArXiv API query URL
 * @param {object} params - Query parameters
 * @param {string} [params.query] - Free-text search query
 * @param {string} [params.author] - Author name search
 * @param {string} [params.category] - ArXiv category (e.g., 'cs.AI')
 * @param {string} [params.title] - Title search
 * @param {number} [params.maxResults] - Max results to return
 * @param {number} [params.start] - Pagination offset
 * @param {string} [params.sortBy] - Sort field: relevance, lastUpdatedDate, submittedDate
 * @param {string} [params.sortOrder] - ascending or descending
 * @returns {string} Full API URL
 */
function buildQueryUrl(params) {
  const searchParts = [];

  if (params.query) {
    searchParts.push(`all:${encodeURIComponent(params.query)}`);
  }
  if (params.author) {
    searchParts.push(`au:${encodeURIComponent(params.author)}`);
  }
  if (params.category) {
    searchParts.push(`cat:${encodeURIComponent(params.category)}`);
  }
  if (params.title) {
    searchParts.push(`ti:${encodeURIComponent(params.title)}`);
  }

  const searchQuery = searchParts.join('+AND+');
  const maxResults = params.maxResults || DEFAULT_MAX_RESULTS;
  const start = params.start || 0;

  let url = `${ARXIV_API_BASE}?search_query=${searchQuery}&start=${start}&max_results=${maxResults}`;

  if (params.sortBy) {
    url += `&sortBy=${params.sortBy}`;
  }
  if (params.sortOrder) {
    url += `&sortOrder=${params.sortOrder}`;
  }

  return url;
}

/**
 * Extract key insights from a paper's abstract
 * Identifies methodology, findings, and significance markers
 * @param {object} paper - Parsed paper object
 * @returns {object} { methodology, findings, significance, keywords }
 */
function extractInsights(paper) {
  const abstract = paper.abstract || '';
  const sentences = abstract.split(/(?<=[.!?])\s+/);

  // Methodology indicators
  const methodKeywords = ['propose', 'introduce', 'present', 'develop', 'design',
    'implement', 'framework', 'architecture', 'method', 'approach', 'algorithm',
    'model', 'technique', 'system'];
  const methodology = sentences.filter((s) => {
    const lower = s.toLowerCase();
    return methodKeywords.some((k) => lower.includes(k));
  });

  // Findings indicators
  const findingKeywords = ['achieve', 'outperform', 'improve', 'result', 'show',
    'demonstrate', 'observe', 'find', 'state-of-the-art', 'sota', 'surpass',
    'exceed', 'accuracy', 'performance'];
  const findings = sentences.filter((s) => {
    const lower = s.toLowerCase();
    return findingKeywords.some((k) => lower.includes(k));
  });

  // Significance indicators
  const sigKeywords = ['first', 'novel', 'new', 'significant', 'breakthrough',
    'challenging', 'fundamental', 'important', 'contribution', 'advance'];
  const significance = sentences.filter((s) => {
    const lower = s.toLowerCase();
    return sigKeywords.some((k) => lower.includes(k));
  });

  // Extract potential technical keywords (capitalized multi-word terms)
  const kwRegex = /\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b/g;
  const rawKeywords = abstract.match(kwRegex) || [];
  const keywords = [...new Set(rawKeywords)].slice(0, 10);

  return {
    methodology: methodology.slice(0, 3),
    findings: findings.slice(0, 3),
    significance: significance.slice(0, 2),
    keywords
  };
}

/**
 * Search ArXiv for papers matching a query
 * @param {string} query - Search query (free text)
 * @param {object} [options] - Search options
 * @param {number} [options.maxResults=10] - Max results
 * @param {string} [options.sortBy='relevance'] - Sort field
 * @param {string} [options.category] - Filter by category
 * @returns {Promise<object>} { query, totalResults, papers: [...] }
 */
async function search(query, options = {}) {
  await rateLimit();

  const params = {
    query,
    maxResults: options.maxResults || DEFAULT_MAX_RESULTS,
    sortBy: options.sortBy || 'relevance',
    sortOrder: options.sortOrder || 'descending',
    category: options.category || null
  };

  const url = buildQueryUrl(params);
  const xml = await httpGet(url);
  const result = parseAtomResponse(xml);

  // Enrich papers with extracted insights
  result.papers = result.papers.map((paper) => ({
    ...paper,
    insights: extractInsights(paper)
  }));

  return {
    query,
    source: 'arxiv',
    totalResults: result.totalResults,
    returned: result.papers.length,
    papers: result.papers
  };
}

/**
 * Get recent papers in a category
 * @param {string} category - ArXiv category (e.g., 'cs.AI', 'cs.CL', 'cs.LG')
 * @param {number} [maxResults=10] - Max results
 * @returns {Promise<object>} { category, papers: [...] }
 */
async function recentPapers(category, maxResults = DEFAULT_MAX_RESULTS) {
  await rateLimit();

  const params = {
    category,
    maxResults,
    sortBy: 'submittedDate',
    sortOrder: 'descending'
  };

  const url = buildQueryUrl(params);
  const xml = await httpGet(url);
  const result = parseAtomResponse(xml);

  result.papers = result.papers.map((paper) => ({
    ...paper,
    insights: extractInsights(paper)
  }));

  return {
    category,
    source: 'arxiv',
    totalResults: result.totalResults,
    returned: result.papers.length,
    papers: result.papers
  };
}

/**
 * Get a specific paper by its ArXiv ID
 * @param {string} arxivId - ArXiv paper ID (e.g., '2301.12345')
 * @returns {Promise<object>} Paper object with insights
 */
async function getPaper(arxivId) {
  await rateLimit();

  const url = `${ARXIV_API_BASE}?id_list=${encodeURIComponent(arxivId)}`;
  const xml = await httpGet(url);
  const result = parseAtomResponse(xml);

  if (result.papers.length === 0) {
    return null;
  }

  const paper = result.papers[0];
  paper.insights = extractInsights(paper);
  return paper;
}

/**
 * Search for papers by a specific author
 * @param {string} authorName - Author name
 * @param {number} [maxResults=10] - Max results
 * @returns {Promise<object>} { author, papers: [...] }
 */
async function searchByAuthor(authorName, maxResults = DEFAULT_MAX_RESULTS) {
  await rateLimit();

  const params = {
    author: authorName,
    maxResults,
    sortBy: 'submittedDate',
    sortOrder: 'descending'
  };

  const url = buildQueryUrl(params);
  const xml = await httpGet(url);
  const result = parseAtomResponse(xml);

  result.papers = result.papers.map((paper) => ({
    ...paper,
    insights: extractInsights(paper)
  }));

  return {
    author: authorName,
    source: 'arxiv',
    totalResults: result.totalResults,
    returned: result.papers.length,
    papers: result.papers
  };
}

/**
 * Convert search results to a structured finding for the research framework
 * @param {object} searchResult - Result from search/recentPapers
 * @returns {object} Structured finding
 */
function toFinding(searchResult) {
  return {
    source: 'arxiv',
    type: 'academic_papers',
    timestamp: new Date().toISOString(),
    query: searchResult.query || searchResult.category || searchResult.author,
    totalAvailable: searchResult.totalResults,
    resultCount: searchResult.returned,
    findings: searchResult.papers.map((paper) => ({
      title: paper.title,
      authors: paper.authors,
      date: paper.published,
      url: paper.absUrl,
      pdfUrl: paper.pdfUrl,
      categories: paper.categories,
      abstract: paper.abstract,
      insights: paper.insights,
      relevanceIndicators: {
        hasMethodology: (paper.insights.methodology || []).length > 0,
        hasFindings: (paper.insights.findings || []).length > 0,
        isNovel: (paper.insights.significance || []).length > 0,
        keywordCount: (paper.insights.keywords || []).length
      }
    }))
  };
}

// Available ArXiv categories relevant to AI/ML research
const AI_CATEGORIES = {
  'cs.AI': 'Artificial Intelligence',
  'cs.CL': 'Computation and Language (NLP)',
  'cs.CV': 'Computer Vision',
  'cs.LG': 'Machine Learning',
  'cs.MA': 'Multi-Agent Systems',
  'cs.NE': 'Neural and Evolutionary Computing',
  'cs.RO': 'Robotics',
  'cs.SE': 'Software Engineering',
  'cs.IR': 'Information Retrieval',
  'stat.ML': 'Machine Learning (Statistics)'
};

module.exports = {
  search,
  recentPapers,
  getPaper,
  searchByAuthor,
  toFinding,
  extractInsights,
  AI_CATEGORIES,

  // Expose internals for testing
  _internals: {
    buildQueryUrl,
    parseAtomResponse,
    parseEntry,
    httpGet,
    rateLimit
  }
};
