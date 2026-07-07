#!/usr/bin/env node

/**
 * AI Consensus Disagreement Workflow
 * Runs multiple LLM models on the same prompt, detects disagreements,
 * calculates consensus scores, and synthesizes results with disagreement metadata.
 *
 * Meta Block:
 * - name: ai-consensus-disagreement
 * - description: Multi-model consensus analysis with disagreement detection
 * - version: 1.0.0
 * - author: Claude Code Workflow System
 * - category: analysis
 * - tags: [consensus, disagreement, multi-model, analysis]
 */

import fs from 'fs';
import path from 'path';
import { execSync } from 'child_process';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Configuration
const DEFAULT_MODELS = [
  'claude-opus-4-1@latest',
  'claude-sonnet-4@latest',
  'claude-haiku-4-5@latest'
];

const DEFAULT_CONFIG = {
  temperature: 0.7,
  max_tokens: 2000,
  timeout: 30000
};

/**
 * Fetch response from a model via Claude API
 */
async function fetchModelResponse(prompt, model, config = {}) {
  const apiConfig = { ...DEFAULT_CONFIG, ...config };

  try {
    // Call Claude API using the Anthropic SDK
    const { default: Anthropic } = await import('@anthropic-ai/sdk');
    const client = new Anthropic({
      apiKey: process.env.ANTHROPIC_API_KEY
    });

    const message = await client.messages.create({
      model: model,
      max_tokens: apiConfig.max_tokens,
      temperature: apiConfig.temperature,
      messages: [
        {
          role: 'user',
          content: prompt
        }
      ]
    });

    return {
      model: model,
      response: message.content[0].type === 'text' ? message.content[0].text : '',
      status: 'success',
      tokens_used: message.usage.output_tokens
    };
  } catch (error) {
    return {
      model: model,
      response: '',
      status: 'error',
      error: error.message
    };
  }
}

/**
 * Normalize text for comparison (lowercase, remove extra whitespace)
 */
function normalizeText(text) {
  return text
    .toLowerCase()
    .trim()
    .replace(/\s+/g, ' ')
    .replace(/[^\w\s]/g, '');
}

/**
 * Calculate similarity score between two texts using simple string matching
 */
function calculateSimilarity(text1, text2) {
  const norm1 = normalizeText(text1);
  const norm2 = normalizeText(text2);

  if (norm1 === norm2) return 1.0;

  const words1 = new Set(norm1.split(' '));
  const words2 = new Set(norm2.split(' '));

  let matches = 0;
  for (const word of words1) {
    if (words2.has(word)) matches++;
  }

  const maxLen = Math.max(words1.size, words2.size);
  return maxLen > 0 ? matches / maxLen : 0;
}

/**
 * Detect key differences between responses
 */
function detectDisagreements(responses) {
  const disagreements = [];

  // Extract key statements from each response
  const statements = responses.map(r => ({
    model: r.model,
    sentences: r.response.split(/[.!?]+/).filter(s => s.trim().length > 20)
  }));

  // Compare statements between models
  for (let i = 0; i < statements.length; i++) {
    for (let j = i + 1; j < statements.length; j++) {
      const model1 = statements[i];
      const model2 = statements[j];

      // Find sentences with low similarity
      for (const sent1 of model1.sentences) {
        let maxSimilarity = 0;
        let bestMatch = '';

        for (const sent2 of model2.sentences) {
          const similarity = calculateSimilarity(sent1, sent2);
          if (similarity > maxSimilarity) {
            maxSimilarity = similarity;
            bestMatch = sent2;
          }
        }

        // Flag as disagreement if similarity is low
        if (maxSimilarity < 0.4) {
          disagreements.push({
            type: 'statement_mismatch',
            model1: model1.model,
            model2: model2.model,
            statement1: sent1.trim().substring(0, 100),
            statement2: bestMatch.trim().substring(0, 100),
            similarity: parseFloat(maxSimilarity.toFixed(2))
          });
        }
      }
    }
  }

  return disagreements;
}

/**
 * Calculate consensus score based on agreement levels
 */
function calculateConsensusScore(responses) {
  if (responses.length < 2) return 100;

  let totalSimilarity = 0;
  let comparisons = 0;

  for (let i = 0; i < responses.length; i++) {
    for (let j = i + 1; j < responses.length; j++) {
      const similarity = calculateSimilarity(
        responses[i].response,
        responses[j].response
      );
      totalSimilarity += similarity;
      comparisons++;
    }
  }

  const avgSimilarity = comparisons > 0 ? totalSimilarity / comparisons : 1;
  return Math.round(avgSimilarity * 100);
}

/**
 * Detect if models strongly disagree
 */
function detectStrongDisagreement(consensusScore, disagreements) {
  return {
    isStronglyDisagreeing: consensusScore < 40,
    disagreementLevel: consensusScore < 40 ? 'critical' : consensusScore < 60 ? 'moderate' : 'low',
    disagreementCount: disagreements.length,
    warningThreshold: consensusScore < 60
  };
}

/**
 * Synthesize results with disagreement metadata
 */
function synthesizeResults(responses, consensusScore, disagreements, strongDisagreement) {
  return {
    meta: {
      workflow: 'ai-consensus-disagreement',
      timestamp: new Date().toISOString(),
      version: '1.0.0'
    },
    summary: {
      total_models: responses.length,
      consensus_score: consensusScore,
      disagreement_level: strongDisagreement.disagreementLevel,
      strongly_disagreeing: strongDisagreement.isStronglyDisagreeing,
      warning: strongDisagreement.warningThreshold
    },
    model_responses: responses.map(r => ({
      model: r.model,
      status: r.status,
      tokens_used: r.tokens_used,
      preview: r.response.substring(0, 150) + (r.response.length > 150 ? '...' : '')
    })),
    disagreements: {
      count: disagreements.length,
      details: disagreements.slice(0, 10), // Top 10 disagreements
      summary: disagreements.length > 0
        ? `Models disagree on ${disagreements.length} key statements`
        : 'All models are in consensus'
    },
    analysis: {
      consensus_interpretation:
        consensusScore >= 80 ? 'Strong consensus across all models' :
        consensusScore >= 60 ? 'Moderate consensus with some variations' :
        consensusScore >= 40 ? 'Weak consensus, significant disagreements detected' :
        'Critical disagreement - models have fundamentally different perspectives',
      recommendation:
        consensusScore >= 80 ? 'Use results with high confidence' :
        consensusScore >= 60 ? 'Use results with caution, review disagreements' :
        'Review all model outputs individually before deciding'
    }
  };
}

/**
 * Main workflow function
 */
async function runConsensusWorkflow(prompt, options = {}) {
  const {
    models = DEFAULT_MODELS,
    config = DEFAULT_CONFIG,
    verbose = false
  } = options;

  console.log('\n=== AI Consensus Disagreement Workflow ===\n');
  console.log(`Prompt: ${prompt.substring(0, 100)}...\n`);
  console.log(`Running models: ${models.join(', ')}\n`);

  // Fetch responses from all models
  console.log('Fetching responses from models...');
  const responses = [];

  for (const model of models) {
    console.log(`  - ${model}`);
    const result = await fetchModelResponse(prompt, model, config);
    responses.push(result);

    if (result.status === 'error') {
      console.log(`    ERROR: ${result.error}`);
    } else {
      console.log(`    OK (${result.tokens_used} tokens)`);
    }
  }

  // Calculate consensus score
  console.log('\nAnalyzing responses...');
  const consensusScore = calculateConsensusScore(responses);
  console.log(`Consensus score: ${consensusScore}/100`);

  // Detect disagreements
  const disagreements = detectDisagreements(responses);
  console.log(`Disagreements detected: ${disagreements.length}`);

  // Check for strong disagreement
  const strongDisagreement = detectStrongDisagreement(consensusScore, disagreements);
  if (strongDisagreement.isStronglyDisagreeing) {
    console.log('\nWARNING: Models are strongly disagreeing!');
  }

  // Synthesize results
  const synthesis = synthesizeResults(
    responses,
    consensusScore,
    disagreements,
    strongDisagreement
  );

  if (verbose) {
    console.log('\n=== Full Results ===\n');
    console.log(JSON.stringify(synthesis, null, 2));
  }

  return synthesis;
}

/**
 * CLI entry point
 */
async function main() {
  const cliArgs = process.argv.slice(2);

  if (cliArgs.length === 0) {
    console.error('Usage: node ai-consensus-disagreement.js <prompt> [options]');
    console.error('Example: node ai-consensus-disagreement.js "What is the meaning of life?" --verbose');
    process.exit(1);
  }

  const prompt = cliArgs[0];
  const verbose = cliArgs.includes('--verbose');
  const modelsArg = cliArgs.find(arg => arg.startsWith('--models='));
  const models = modelsArg
    ? modelsArg.split('=')[1].split(',')
    : DEFAULT_MODELS;

  try {
    const result = await runConsensusWorkflow(prompt, {
      models,
      config: DEFAULT_CONFIG,
      verbose
    });

    // Output JSON result
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error('Workflow error:', error.message);
    process.exit(1);
  }
}

// Named exports
export {
  runConsensusWorkflow,
  fetchModelResponse,
  calculateConsensusScore,
  detectDisagreements,
  detectStrongDisagreement,
  synthesizeResults,
  calculateSimilarity,
  normalizeText
};

// Default export
export default runConsensusWorkflow;

// Run if executed directly
const isMainModule = process.argv[1] && fs.realpathSync(process.argv[1]) === fs.realpathSync(fileURLToPath(import.meta.url));
if (isMainModule) {
  main();
}
