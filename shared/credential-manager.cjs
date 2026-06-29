/**
 * Credential Manager - Secure API credential handling
 */

const fs = require('fs');
const path = require('path');

class CredentialManager {
  constructor() {
    this.credentials = new Map();
    this.loadCredentials();
  }

  loadCredentials() {
    // Priority 1: Environment variables
    const providers = [
      'ANTHROPIC_API_KEY',
      'OPENAI_API_KEY', 
      'GOOGLE_API_KEY',
      'GROQ_API_KEY',
      'DEEPINFRA_API_KEY',
      'TOGETHER_API_KEY',
      'MISTRAL_API_KEY',
      'COHERE_API_KEY',
      'AI21_API_KEY'
    ];

    providers.forEach(envVar => {
      if (process.env[envVar]) {
        const provider = envVar.replace('_API_KEY', '').toLowerCase();
        this.credentials.set(provider, process.env[envVar]);
      }
    });

    // Priority 2: Config file (if exists)
    const configPath = path.join(process.env.HOME, '.claude', 'credentials.json');
    if (fs.existsSync(configPath)) {
      try {
        const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
        Object.entries(config).forEach(([provider, key]) => {
          if (!this.credentials.has(provider)) {
            this.credentials.set(provider, key);
          }
        });
      } catch (error) {
        console.error('Failed to load credentials config:', error.message);
      }
    }
  }

  getCredentialForProvider(provider, worker = null) {
    // Normalize provider name
    const normalized = provider.toLowerCase().replace(/-/g, '_');
    
    // Check if we have credentials
    if (this.credentials.has(normalized)) {
      return this.credentials.get(normalized);
    }
    
    // Check alternate names
    const alternates = {
      'anthropic': 'anthropic',
      'claude': 'anthropic',
      'openai': 'openai',
      'gpt': 'openai',
      'google': 'google',
      'gemini': 'google',
      'groq': 'groq',
      'deepinfra': 'deepinfra',
      'together': 'together',
      'mistral': 'mistral',
      'cohere': 'cohere',
      'ai21': 'ai21'
    };
    
    const alternate = alternates[normalized];
    if (alternate && this.credentials.has(alternate)) {
      return this.credentials.get(alternate);
    }
    
    throw new Error(`No credentials found for provider: ${provider}`);
  }

  validateCredentials() {
    const results = {};
    
    for (const [provider, key] of this.credentials.entries()) {
      results[provider] = {
        configured: true,
        valid: key && key.length > 10,
        masked: key ? key.slice(0, 8) + '...' : null
      };
    }
    
    return results;
  }

  getAvailableProviders() {
    return Array.from(this.credentials.keys());
  }
}

// Singleton instance
let instance = null;

function getCredentialManager() {
  if (!instance) {
    instance = new CredentialManager();
  }
  return instance;
}

module.exports = {
  CredentialManager,
  getCredentialManager
};
