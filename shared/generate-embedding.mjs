#!/usr/bin/env node
/**
 * Generate embedding using Cloudflare Workers AI
 * Standalone utility that can be called from JavaScript
 */

import https from 'https';

const PERSONAL_CLOUDFLARE_ACCOUNT_ID = process.env.PERSONAL_CLOUDFLARE_ACCOUNT_ID || '';
const PERSONAL_CLOUDFLARE_API_KEY = process.env.PERSONAL_CLOUDFLARE_API_KEY || '';

export async function generateEmbedding(text) {
  if (!PERSONAL_CLOUDFLARE_ACCOUNT_ID || !PERSONAL_CLOUDFLARE_API_KEY) {
    throw new Error('Missing Cloudflare credentials');
  }

  const url = `https://api.cloudflare.com/client/v4/accounts/${PERSONAL_CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/baai/bge-small-en-v1.5`;

  // Truncate to first 2048 chars (~512 tokens)
  const truncated = text.substring(0, 2048);

  const payload = JSON.stringify({ text: truncated });

  return new Promise((resolve, reject) => {
    const options = {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${PERSONAL_CLOUDFLARE_API_KEY}`,
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    };

    const req = https.request(url, options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        try {
          const result = JSON.parse(data);

          if (res.statusCode !== 200) {
            reject(new Error(`API error ${res.statusCode}: ${data}`));
            return;
          }

          let embedding = result.result.data;

          // Cloudflare returns [[...]] - flatten it
          if (Array.isArray(embedding[0])) {
            embedding = embedding[0];
          }

          resolve(embedding);
        } catch (err) {
          reject(new Error(`Failed to parse response: ${err.message}`));
        }
      });
    });

    req.on('error', (err) => {
      reject(new Error(`Request failed: ${err.message}`));
    });

    req.write(payload);
    req.end();
  });
}

// CLI usage
if (import.meta.url === `file://${process.argv[1]}`) {
  const text = process.argv[2] || 'kubernetes networking';

  generateEmbedding(text)
    .then(embedding => {
      console.log(JSON.stringify(embedding));
    })
    .catch(err => {
      console.error('Error:', err.message);
      process.exit(1);
    });
}
