#!/usr/bin/env node
/**
 * GitHub Research Scraper
 *
 * Searches GitHub for trending repositories, code patterns, and implementations
 * using the public GitHub API (v3 REST). Respects rate limits for unauthenticated
 * access (60 req/hour) and authenticated access via PERSONAL_GITHUB_TOKEN (5000 req/hour).
 *
 * Features:
 *   - Search repositories by keyword, language, stars
 *   - Search code for specific patterns/implementations
 *   - Get trending repositories (by recent stars)
 *   - Analyze repository README and structure
 *   - Rate-limit aware with automatic backoff
 *
 * Usage:
 *   const github = require('./research/github');
 *   const repos = await github.searchRepos('RAG framework', { language: 'python' });
 *   const trending = await github.trending('javascript', 'weekly');
 *   const code = await github.searchCode('useEffect cleanup pattern');
 */

const https = require('https');

const GITHUB_API_BASE = 'https://api.github.com';
const DEFAULT_PER_PAGE = 10;

// Rate limit tracking
let rateLimitRemaining = null;
let rateLimitReset = null;

/**
 * Make an authenticated GitHub API request
 * @param {string} endpoint - API path (e.g., '/search/repositories')
 * @param {object} [queryParams] - URL query parameters
 * @returns {Promise<object>} Parsed JSON response
 */
function apiRequest(endpoint, queryParams = {}) {
  return new Promise((resolve, reject) => {
    // Check rate limit
    if (rateLimitRemaining !== null && rateLimitRemaining <= 1) {
      const now = Math.floor(Date.now() / 1000);
      if (rateLimitReset && now < rateLimitReset) {
        const waitSec = rateLimitReset - now + 1;
        reject(new Error(`GitHub rate limit exceeded. Resets in ${waitSec}s. ` +
          `Set PERSONAL_GITHUB_TOKEN env var for higher limits (5000 req/hour).`));
        return;
      }
    }

    const queryString = Object.entries(queryParams)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join('&');

    const fullPath = queryString ? `${endpoint}?${queryString}` : endpoint;

    const headers = {
      'User-Agent': 'AI-Learning-Research/1.0',
      'Accept': 'application/vnd.github.v3+json'
    };

    // Use token if available for higher rate limits
    const token = process.env.PERSONAL_GITHUB_TOKEN || process.env.PERSONAL_GH_TOKEN;
    if (token) {
      headers['Authorization'] = `token ${token}`;
    }

    const options = {
      hostname: 'api.github.com',
      path: fullPath,
      method: 'GET',
      headers,
      timeout: 30000
    };

    const req = https.request(options, (res) => {
      // Track rate limit headers
      if (res.headers['x-ratelimit-remaining']) {
        rateLimitRemaining = parseInt(res.headers['x-ratelimit-remaining'], 10);
      }
      if (res.headers['x-ratelimit-reset']) {
        rateLimitReset = parseInt(res.headers['x-ratelimit-reset'], 10);
      }

      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        const body = Buffer.concat(chunks).toString('utf8');
        if (res.statusCode === 403 && body.includes('rate limit')) {
          reject(new Error('GitHub API rate limit exceeded. Set PERSONAL_GITHUB_TOKEN for higher limits.'));
          return;
        }
        if (res.statusCode !== 200) {
          reject(new Error(`GitHub API ${res.statusCode}: ${body.substring(0, 200)}`));
          return;
        }
        try {
          resolve(JSON.parse(body));
        } catch (e) {
          reject(new Error(`Failed to parse GitHub response: ${e.message}`));
        }
      });
      res.on('error', reject);
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('GitHub API request timed out'));
    });
    req.end();
  });
}

/**
 * Search GitHub repositories
 * @param {string} query - Search query
 * @param {object} [options] - Search options
 * @param {string} [options.language] - Filter by language
 * @param {string} [options.sort='stars'] - Sort by: stars, forks, help-wanted-issues, updated
 * @param {string} [options.order='desc'] - Sort order: asc, desc
 * @param {number} [options.perPage=10] - Results per page
 * @param {number} [options.minStars] - Minimum stars filter
 * @returns {Promise<object>} { query, totalCount, repos: [...] }
 */
async function searchRepos(query, options = {}) {
  let searchQuery = query;
  if (options.language) {
    searchQuery += ` language:${options.language}`;
  }
  if (options.minStars) {
    searchQuery += ` stars:>=${options.minStars}`;
  }

  const data = await apiRequest('/search/repositories', {
    q: searchQuery,
    sort: options.sort || 'stars',
    order: options.order || 'desc',
    per_page: options.perPage || DEFAULT_PER_PAGE
  });

  const repos = (data.items || []).map(parseRepo);

  return {
    query,
    source: 'github',
    totalCount: data.total_count || 0,
    returned: repos.length,
    repos
  };
}

/**
 * Parse a GitHub repo API object into a clean structure
 * @param {object} item - Raw GitHub API repo object
 * @returns {object} Cleaned repo data
 */
function parseRepo(item) {
  return {
    name: item.full_name,
    description: item.description || '',
    url: item.html_url,
    stars: item.stargazers_count,
    forks: item.forks_count,
    openIssues: item.open_issues_count,
    language: item.language,
    topics: item.topics || [],
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    pushedAt: item.pushed_at,
    license: item.license ? item.license.spdx_id : null,
    size: item.size,
    defaultBranch: item.default_branch,
    isArchived: item.archived,
    isFork: item.fork,
    watchers: item.watchers_count,
    owner: {
      login: item.owner ? item.owner.login : '',
      type: item.owner ? item.owner.type : ''
    }
  };
}

/**
 * Get trending repositories (recent high-star repos created within a timeframe)
 * @param {string} [language] - Filter by language
 * @param {string} [period='weekly'] - Time period: daily, weekly, monthly
 * @param {number} [perPage=10] - Results per page
 * @returns {Promise<object>} { period, language, repos: [...] }
 */
async function trending(language, period = 'weekly', perPage = DEFAULT_PER_PAGE) {
  const periodDays = { daily: 1, weekly: 7, monthly: 30 };
  const days = periodDays[period] || 7;

  const since = new Date();
  since.setDate(since.getDate() - days);
  const sinceStr = since.toISOString().split('T')[0];

  let query = `created:>=${sinceStr}`;
  if (language) {
    query += ` language:${language}`;
  }

  const data = await apiRequest('/search/repositories', {
    q: query,
    sort: 'stars',
    order: 'desc',
    per_page: perPage
  });

  const repos = (data.items || []).map(parseRepo);

  return {
    period,
    language: language || 'all',
    source: 'github',
    since: sinceStr,
    totalCount: data.total_count || 0,
    returned: repos.length,
    repos
  };
}

/**
 * Search code across GitHub repositories
 * @param {string} query - Code search query
 * @param {object} [options] - Search options
 * @param {string} [options.language] - Filter by language
 * @param {string} [options.filename] - Filter by filename
 * @param {string} [options.extension] - Filter by file extension
 * @param {string} [options.repo] - Search within a specific repo
 * @param {number} [options.perPage=10] - Results per page
 * @returns {Promise<object>} { query, totalCount, codeResults: [...] }
 */
async function searchCode(query, options = {}) {
  let searchQuery = query;
  if (options.language) {
    searchQuery += ` language:${options.language}`;
  }
  if (options.filename) {
    searchQuery += ` filename:${options.filename}`;
  }
  if (options.extension) {
    searchQuery += ` extension:${options.extension}`;
  }
  if (options.repo) {
    searchQuery += ` repo:${options.repo}`;
  }

  const data = await apiRequest('/search/code', {
    q: searchQuery,
    per_page: options.perPage || DEFAULT_PER_PAGE
  });

  const codeResults = (data.items || []).map((item) => ({
    name: item.name,
    path: item.path,
    repo: item.repository ? item.repository.full_name : '',
    repoUrl: item.repository ? item.repository.html_url : '',
    url: item.html_url,
    score: item.score,
    sha: item.sha
  }));

  return {
    query,
    source: 'github',
    totalCount: data.total_count || 0,
    returned: codeResults.length,
    codeResults
  };
}

/**
 * Get repository details including README content
 * @param {string} owner - Repository owner
 * @param {string} repo - Repository name
 * @returns {Promise<object>} Repository details with README
 */
async function getRepoDetails(owner, repo) {
  const repoData = await apiRequest(`/repos/${owner}/${repo}`);
  const parsed = parseRepo(repoData);

  // Try to fetch README
  let readme = null;
  try {
    const readmeData = await apiRequest(`/repos/${owner}/${repo}/readme`);
    if (readmeData.content) {
      readme = Buffer.from(readmeData.content, 'base64').toString('utf8');
      // Truncate very long READMEs
      if (readme.length > 5000) {
        readme = readme.substring(0, 5000) + '\n\n... [truncated]';
      }
    }
  } catch (e) {
    readme = null;
  }

  // Try to fetch languages
  let languages = {};
  try {
    languages = await apiRequest(`/repos/${owner}/${repo}/languages`);
  } catch (e) {
    languages = {};
  }

  return {
    ...parsed,
    readme,
    languages,
    source: 'github'
  };
}

/**
 * Get the directory structure of a repository (top-level)
 * @param {string} owner - Repository owner
 * @param {string} repo - Repository name
 * @param {string} [path=''] - Subdirectory path
 * @returns {Promise<array>} Array of { name, type, size, path }
 */
async function getRepoTree(owner, repo, dirPath = '') {
  const endpoint = dirPath
    ? `/repos/${owner}/${repo}/contents/${dirPath}`
    : `/repos/${owner}/${repo}/contents`;

  const data = await apiRequest(endpoint);

  if (!Array.isArray(data)) {
    return [];
  }

  return data.map((item) => ({
    name: item.name,
    type: item.type, // 'file' or 'dir'
    size: item.size,
    path: item.path
  }));
}

/**
 * Analyze a repository's implementation patterns
 * @param {string} owner - Repository owner
 * @param {string} repo - Repository name
 * @returns {Promise<object>} Analysis results
 */
async function analyzeRepo(owner, repo) {
  const details = await getRepoDetails(owner, repo);

  let tree = [];
  try {
    tree = await getRepoTree(owner, repo);
  } catch (e) {
    tree = [];
  }

  // Identify project patterns from file structure
  const patterns = {
    hasTests: tree.some((f) => /^(test|tests|__tests__|spec|specs)$/i.test(f.name)),
    hasCI: tree.some((f) => f.name === '.github' || f.name === '.circleci' || f.name === '.travis.yml'),
    hasDocker: tree.some((f) => f.name === 'Dockerfile' || f.name === 'docker-compose.yml'),
    hasPackageJson: tree.some((f) => f.name === 'package.json'),
    hasPyproject: tree.some((f) => f.name === 'pyproject.toml' || f.name === 'setup.py'),
    hasConfig: tree.some((f) => /\.(ya?ml|toml|json|ini|cfg)$/.test(f.name)),
    hasDocs: tree.some((f) => /^(docs|documentation|doc)$/i.test(f.name)),
    hasExamples: tree.some((f) => /^(examples|example|demo|demos)$/i.test(f.name)),
    hasSrc: tree.some((f) => /^(src|lib|pkg|internal)$/i.test(f.name))
  };

  return {
    ...details,
    structure: tree,
    patterns,
    analysis: {
      maturityIndicators: Object.values(patterns).filter(Boolean).length,
      totalFiles: tree.filter((f) => f.type === 'file').length,
      totalDirs: tree.filter((f) => f.type === 'dir').length
    }
  };
}

/**
 * Convert search results to a structured finding for the research framework
 * @param {object} searchResult - Result from searchRepos/trending/searchCode
 * @returns {object} Structured finding
 */
function toFinding(searchResult) {
  if (searchResult.repos) {
    return {
      source: 'github',
      type: 'repositories',
      timestamp: new Date().toISOString(),
      query: searchResult.query || `${searchResult.period} trending`,
      totalAvailable: searchResult.totalCount,
      resultCount: searchResult.returned,
      findings: searchResult.repos.map((repo) => ({
        title: repo.name,
        description: repo.description,
        url: repo.url,
        metrics: {
          stars: repo.stars,
          forks: repo.forks,
          openIssues: repo.openIssues
        },
        language: repo.language,
        topics: repo.topics,
        license: repo.license,
        lastUpdated: repo.updatedAt,
        owner: repo.owner
      }))
    };
  }

  if (searchResult.codeResults) {
    return {
      source: 'github',
      type: 'code_search',
      timestamp: new Date().toISOString(),
      query: searchResult.query,
      totalAvailable: searchResult.totalCount,
      resultCount: searchResult.returned,
      findings: searchResult.codeResults.map((code) => ({
        title: `${code.repo}/${code.path}`,
        file: code.name,
        path: code.path,
        url: code.url,
        repo: code.repo,
        repoUrl: code.repoUrl
      }))
    };
  }

  return {
    source: 'github',
    type: 'unknown',
    timestamp: new Date().toISOString(),
    findings: []
  };
}

/**
 * Get current rate limit status
 * @returns {Promise<object>} Rate limit info
 */
async function getRateLimit() {
  const data = await apiRequest('/rate_limit');
  return {
    core: data.resources.core,
    search: data.resources.search,
    codeSearch: data.resources.code_search
  };
}

module.exports = {
  searchRepos,
  searchCode,
  trending,
  getRepoDetails,
  getRepoTree,
  analyzeRepo,
  toFinding,
  getRateLimit,

  // Expose internals for testing
  _internals: {
    apiRequest,
    parseRepo
  }
};
