#!/usr/bin/env node
/**
 * Multi-Provider LLM Generator with Automatic Fallback
 * Rotates across ALL providers to avoid rate limits
 */

const fs = require('fs');
const path = require('path');

// Load provider configurations
const MODELS_CONFIG = JSON.parse(
  fs.readFileSync(path.join(__dirname, '../config/multi-provider-models.json'), 'utf8')
);

class MultiProviderGenerator {
  constructor() {
    // All FREE models with high limits
    this.providers = [
      // Google Gemini (FREE tier: 1,500 requests/day)
      {
        name: 'google-gemini-flash',
        url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent',
        key: process.env.GOOGLE_API_KEY,
        priority: 1
      },
      // Cloudflare (FREE tier: 10,000 requests/day)
      {
        name: 'cloudflare-llama',
        url: 'https://api.cloudflare.com/client/v4/accounts/c38a4493830b64dceec5f528043bd3ac/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast',
        key: 'cfat_G7QETtzyQC6MGMBCPkwXhoIgfRydoqi937WC2PTP74cceced',
        priority: 2
      },
      // OpenAI GPT-4o-mini (Paid but cheap: $0.15/1M input tokens)
      {
        name: 'openai-gpt4o-mini',
        url: 'https://api.openai.com/v1/chat/completions',
        key: process.env.OPENAI_API_KEY,
        priority: 3
      },
      // Anthropic Claude Haiku (Paid but cheap: $0.25/1M input tokens)
      {
        name: 'anthropic-haiku',
        url: 'https://api.anthropic.com/v1/messages',
        key: process.env.ANTHROPIC_API_KEY,
        priority: 4
      },
      // Mistral (FREE tier available)
      {
        name: 'mistral-small',
        url: 'https://api.mistral.ai/v1/chat/completions',
        key: process.env.MISTRAL_API_KEY,
        priority: 5
      }
    ];

    this.currentIndex = 0;
    this.requestCounts = {};
    this.failedProviders = new Set();
  }

  async generate(prompt, maxTokens = 512) {
    const maxAttempts = this.providers.length;
    let attempts = 0;

    while (attempts < maxAttempts) {
      const provider = this.providers[this.currentIndex];

      // Skip if provider failed recently
      if (this.failedProviders.has(provider.name)) {
        this.currentIndex = (this.currentIndex + 1) % this.providers.length;
        attempts++;
        continue;
      }

      try {
        const result = await this._callProvider(provider, prompt, maxTokens);

        // Success! Track usage and rotate
        this.requestCounts[provider.name] = (this.requestCounts[provider.name] || 0) + 1;
        this.currentIndex = (this.currentIndex + 1) % this.providers.length;

        return result;

      } catch (error) {
        console.error(`Provider ${provider.name} failed: ${error.message}`);

        // Rate limit or error - mark as failed and try next
        if (error.message.includes('429') || error.message.includes('rate limit')) {
          this.failedProviders.add(provider.name);
          console.log(`⚠️  ${provider.name} rate limited, moving to next provider`);
        }

        this.currentIndex = (this.currentIndex + 1) % this.providers.length;
        attempts++;
      }
    }

    throw new Error('All providers failed or rate limited');
  }

  async _callProvider(provider, prompt, maxTokens) {
    if (!provider.key) {
      throw new Error(`No API key for ${provider.name}`);
    }

    switch (provider.name) {
      case 'google-gemini-flash':
        return await this._callGemini(provider, prompt, maxTokens);

      case 'cloudflare-llama':
        return await this._callCloudflare(provider, prompt, maxTokens);

      case 'openai-gpt4o-mini':
        return await this._callOpenAI(provider, prompt, maxTokens);

      case 'anthropic-haiku':
        return await this._callAnthropic(provider, prompt, maxTokens);

      case 'mistral-small':
        return await this._callMistral(provider, prompt, maxTokens);

      default:
        throw new Error(`Unknown provider: ${provider.name}`);
    }
  }

  async _callGemini(provider, prompt, maxTokens) {
    const response = await fetch(`${provider.url}?key=${provider.key}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: { maxOutputTokens: maxTokens }
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    return data.candidates[0].content.parts[0].text;
  }

  async _callCloudflare(provider, prompt, maxTokens) {
    const response = await fetch(provider.url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${provider.key}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        messages: [{ role: 'user', content: prompt }],
        max_tokens: maxTokens
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    return data.result.response;
  }

  async _callOpenAI(provider, prompt, maxTokens) {
    const response = await fetch(provider.url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${provider.key}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        messages: [{ role: 'user', content: prompt }],
        max_tokens: maxTokens
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    return data.choices[0].message.content;
  }

  async _callAnthropic(provider, prompt, maxTokens) {
    const response = await fetch(provider.url, {
      method: 'POST',
      headers: {
        'x-api-key': provider.key,
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: 'claude-haiku-4',
        max_tokens: maxTokens,
        messages: [{ role: 'user', content: prompt }]
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    return data.content[0].text;
  }

  async _callMistral(provider, prompt, maxTokens) {
    const response = await fetch(provider.url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${provider.key}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: 'mistral-small-latest',
        messages: [{ role: 'user', content: prompt }],
        max_tokens: maxTokens
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    return data.choices[0].message.content;
  }

  getStats() {
    return {
      totalRequests: Object.values(this.requestCounts).reduce((a, b) => a + b, 0),
      byProvider: this.requestCounts,
      failedProviders: Array.from(this.failedProviders)
    };
  }
}

// CLI usage
if (require.main === module) {
  const generator = new MultiProviderGenerator();
  const prompt = process.argv[2] || 'Explain quantum computing in 2 sentences.';

  generator.generate(prompt, 100)
    .then(result => {
      console.log('Result:', result);
      console.log('\nStats:', generator.getStats());
    })
    .catch(err => console.error('Error:', err));
}

module.exports = { MultiProviderGenerator };
