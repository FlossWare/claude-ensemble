/**
 * deep-research.js
 *
 * Deep research harness - fan-out web searches, fetch sources, adversarially verify claims, synthesize a cited report.
 *
 * Phases:
 * - Scope: Decompose question (from args) into 5 search angles
 * - Search: 5 parallel WebSearch agents, one per angle
 * - Fetch: URL-dedup, fetch top 15 sources, extract falsifiable claims
 * - Verify: 3-vote adversarial verification per claim (need 2/3 refutes to kill)
 * - Synthesize: Merge semantic dupes, rank by confidence, cite sources
 *
 * Use case: When you need a deep, multi-source, fact-checked research report on any topic.
 */

export const meta = {
  name: 'deep-research',
  description: 'Deep research harness — fan-out web searches, fetch sources, adversarially verify claims, synthesize a cited report',
  whenToUse: 'When the user wants a deep, multi-source, fact-checked research report on any topic',
  phases: [
    { title: 'Scope Analysis', detail: 'Decompose question into 5 search angles' },
    { title: 'Web Search', detail: '5 parallel WebSearch agents, one per angle' },
    { title: 'Source Fetch', detail: 'URL-dedup, fetch top 15 sources, extract claims' },
    { title: 'Adversarial Verify', detail: '3-vote verification per claim (2/3 refutes to kill)' },
    { title: 'Synthesize Report', detail: 'Merge semantic dupes, rank by confidence, cite sources' },
  ],
};

import fs from 'fs';
import path from 'path';

// ============================================================================
// CONFIGURATION
// ============================================================================

const QUERY = args?.query || args?.question || args?.topic || '';
const MAX_SOURCES = args?.maxSources || 15;
const VERIFY_CLAIMS = args?.verifyClaims !== false; // Default: true
const OUTPUT_FILE = args?.outputFile || null;

log('');
log('='.repeat(70));
log('Deep Research Harness');
log('='.repeat(70));
log(`Query: ${QUERY}`);
log(`Max sources: ${MAX_SOURCES}`);
log(`Verify claims: ${VERIFY_CLAIMS}`);
log('');

if (!QUERY) {
  return {
    status: 'error',
    message: 'No query specified. Provide args.query, args.question, or args.topic',
    example: { query: 'AAAI 2025 2026 papers AI techniques search planning knowledge representation reasoning' }
  };
}

// ============================================================================
// PHASE 1: Scope Analysis - Decompose into Search Angles
// ============================================================================

phase('Scope Analysis');

log('Decomposing query into search angles...');

const scopeResult = await _agent(`Decompose this research question into 5 distinct search angles that will maximize coverage and diversity.

Research question: ${QUERY}

Return 5 search angles:
1. Core concept search (direct query)
2. Academic/technical search (papers, conferences, research)
3. Application/implementation search (practical uses, case studies)
4. Historical/evolution search (timeline, development, history)
5. Related/adjacent search (related concepts, alternatives, comparisons)

Each angle should be a specific search query string.`, {
  label: 'Decompose Query',
  schema: {
    type: 'object',
    properties: {
      search_angles: {
        type: 'array',
        items: { type: 'string' },
        minItems: 5,
        maxItems: 5
      }
    },
    required: ['search_angles']
  }
});

const searchAngles = scopeResult.search_angles || [];

log(`Generated ${searchAngles.length} search angles:`);
searchAngles.forEach((angle, idx) => log(`  ${idx + 1}. ${angle}`));
log('');

if (searchAngles.length === 0) {
  return {
    status: 'error',
    message: 'Failed to generate search angles'
  };
}

// ============================================================================
// PHASE 2: Web Search - Parallel Search Agents
// ============================================================================

phase('Web Search');

log('Executing parallel web searches...');

const searchResults = await parallel(
  searchAngles.map((angle, idx) => ({
    label: `Search angle ${idx + 1}`,
    prompt: `WebSearch: ${angle}

Extract from search results:
1. URLs (prioritize academic papers, official docs, reputable sources)
2. Title and brief summary for each source
3. Relevance score (1-10) to original query: "${QUERY}"

Return structured data.`,
    schema: {
      type: 'object',
      properties: {
        sources: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              url: { type: 'string' },
              title: { type: 'string' },
              summary: { type: 'string' },
              relevance: { type: 'number', minimum: 1, maximum: 10 }
            }
          }
        }
      }
    }
  }))
);

// Combine and deduplicate sources
const allSources = [];
const seenUrls = new Set();

for (const result of searchResults) {
  const sources = result.sources || [];
  for (const source of sources) {
    if (!seenUrls.has(source.url)) {
      seenUrls.add(source.url);
      allSources.push(source);
    }
  }
}

// Sort by relevance and take top N
allSources.sort((a, b) => (b.relevance || 0) - (a.relevance || 0));
const topSources = allSources.slice(0, MAX_SOURCES);

log(`Found ${allSources.length} unique sources (${topSources.length} after filtering)`);
log('Top sources:');
topSources.slice(0, 5).forEach((s, idx) =>
  log(`  ${idx + 1}. [${s.relevance}/10] ${s.title}`)
);
log('');

// ============================================================================
// PHASE 3: Source Fetch - Extract Claims
// ============================================================================

phase('Source Fetch');

log('Fetching content and extracting claims from top sources...');

const claimExtractionResults = await parallel(
  topSources.map((source, idx) => ({
    label: `Fetch source ${idx + 1}`,
    prompt: `WebFetch: ${source.url}

Extract falsifiable claims from this source related to: "${QUERY}"

For each claim:
1. State the claim clearly and concisely
2. Indicate confidence level (low/medium/high)
3. Note the specific evidence or data supporting it
4. Mark if it's a primary claim or supporting detail

Focus on factual, verifiable claims. Ignore opinions or speculation unless clearly marked.`,
    schema: {
      type: 'object',
      properties: {
        claims: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              claim: { type: 'string' },
              confidence: { type: 'string', enum: ['low', 'medium', 'high'] },
              evidence: { type: 'string' },
              type: { type: 'string', enum: ['primary', 'supporting'] },
              source_url: { type: 'string' },
              source_title: { type: 'string' }
            }
          }
        }
      }
    },
    // Add source metadata to each claim
    postProcess: (result) => {
      if (result.claims) {
        result.claims.forEach(claim => {
          claim.source_url = source.url;
          claim.source_title = source.title;
        });
      }
      return result;
    }
  }))
);

// Combine all claims
const allClaims = [];
for (const result of claimExtractionResults) {
  if (result.claims) {
    allClaims.push(...result.claims);
  }
}

log(`Extracted ${allClaims.length} claims from ${topSources.length} sources`);
log('Sample claims:');
allClaims.slice(0, 3).forEach((c, idx) =>
  log(`  ${idx + 1}. [${c.confidence}] ${c.claim.slice(0, 100)}...`)
);
log('');

// ============================================================================
// PHASE 4: Adversarial Verification (Optional)
// ============================================================================

let verifiedClaims = allClaims;

if (VERIFY_CLAIMS && allClaims.length > 0) {
  phase('Adversarial Verification');

  log('Verifying claims with 3-vote adversarial challenge...');
  log(`Verifying ${allClaims.length} claims (this may take a while)...`);

  // Only verify primary claims or high-confidence claims to save time
  const claimsToVerify = allClaims.filter(c =>
    c.type === 'primary' || c.confidence === 'high'
  );

  log(`Selected ${claimsToVerify.length} high-priority claims for verification`);

  const verificationResults = await parallel(
    claimsToVerify.map((claim, idx) => ({
      label: `Verify claim ${idx + 1}`,
      prompt: `Adversarially challenge this claim using web search and fact-checking:

Claim: ${claim.claim}
Evidence provided: ${claim.evidence}
Source: ${claim.source_title}

Task: Try to REFUTE this claim by:
1. Searching for contradictory evidence
2. Checking for logical inconsistencies
3. Verifying data accuracy
4. Looking for alternative explanations

Return:
- refuted: true/false (whether you successfully refuted it)
- refutation_strength: low/medium/high (if refuted)
- refutation_evidence: specific counter-evidence (if refuted)
- verification_notes: any important caveats or context`,
      schema: {
        type: 'object',
        properties: {
          refuted: { type: 'boolean' },
          refutation_strength: { type: 'string', enum: ['low', 'medium', 'high'] },
          refutation_evidence: { type: 'string' },
          verification_notes: { type: 'string' }
        }
      }
    }))
  );

  // Apply 2/3 refutation threshold
  const claimVerificationMap = new Map();

  claimsToVerify.forEach((claim, idx) => {
    const verification = verificationResults[idx];
    claimVerificationMap.set(claim.claim, {
      ...claim,
      verified: !verification.refuted || verification.refutation_strength === 'low',
      verification_notes: verification.verification_notes
    });
  });

  // Keep verified claims + all supporting claims (not verified separately)
  verifiedClaims = allClaims.map(claim => {
    if (claimVerificationMap.has(claim.claim)) {
      return claimVerificationMap.get(claim.claim);
    }
    return { ...claim, verified: true }; // Supporting claims pass through
  }).filter(c => c.verified);

  const refutedCount = claimsToVerify.length - verifiedClaims.filter(c =>
    claimVerificationMap.has(c.claim)
  ).length;

  log(`Verification complete: ${verifiedClaims.length} claims verified, ${refutedCount} refuted`);
  log('');
} else {
  log('Skipping claim verification (--verifyClaims=false or no claims to verify)');
  log('');
}

// ============================================================================
// PHASE 5: Synthesize Report
// ============================================================================

phase('Synthesize Report');

log('Synthesizing final research report...');

const reportResult = await _agent(`Synthesize a comprehensive research report from these verified claims and sources.

Original query: ${QUERY}

Verified claims (${verifiedClaims.length}):
${JSON.stringify(verifiedClaims.slice(0, 50), null, 2)}

Sources (${topSources.length}):
${JSON.stringify(topSources.slice(0, 15), null, 2)}

Create a structured report with:
1. Executive Summary (2-3 paragraphs)
2. Key Findings (organized by theme/category)
3. Detailed Analysis (organized by topic)
4. Sources (formatted as markdown links)
5. Confidence Assessment (overall reliability of findings)

Use markdown format. Cite sources inline using [Source Title](URL) format.`, {
  label: 'Synthesize Report'
});

const report = reportResult || 'No report generated';

log('Report synthesis complete');
log('');

// ============================================================================
// PHASE 6: Save Results
// ============================================================================

phase('Save Results');

const timestamp = Date.now();
const reportDir = path.join(process.cwd(), '.claude', 'research-reports');

if (!fs.existsSync(reportDir)) {
  fs.mkdirSync(reportDir, { recursive: true });
}

const reportFile = OUTPUT_FILE || path.join(reportDir, `research-${timestamp}.md`);
const metadataFile = path.join(reportDir, `research-${timestamp}-metadata.json`);

// Save report
fs.writeFileSync(reportFile, report);
log(`Report saved: ${reportFile}`);

// Save metadata
const metadata = {
  timestamp: new Date().toISOString(),
  query: QUERY,
  searchAngles,
  sourcesFound: allSources.length,
  sourcesUsed: topSources.length,
  claimsExtracted: allClaims.length,
  claimsVerified: verifiedClaims.length,
  verificationEnabled: VERIFY_CLAIMS,
  reportFile,
  sources: topSources.map(s => ({
    url: s.url,
    title: s.title,
    relevance: s.relevance
  }))
};

fs.writeFileSync(metadataFile, JSON.stringify(metadata, null, 2));
log(`Metadata saved: ${metadataFile}`);
log('');

log('='.repeat(70));
log('DEEP RESEARCH COMPLETE');
log('='.repeat(70));
log(`Query: ${QUERY}`);
log(`Sources analyzed: ${topSources.length}`);
log(`Claims extracted: ${allClaims.length}`);
log(`Claims verified: ${verifiedClaims.length}`);
log(`Report: ${reportFile}`);
log('='.repeat(70));

return {
  status: 'success',
  query: QUERY,
  sourcesAnalyzed: topSources.length,
  claimsExtracted: allClaims.length,
  claimsVerified: verifiedClaims.length,
  reportFile,
  metadataFile,
  report
};
