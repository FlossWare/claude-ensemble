/**
 * Shared Fleet Topology Configuration
 *
 * Single source of truth for fleet node definitions.
 * Used by: fleet-activity-collector.js, fleet-prometheus-exporter.js
 */

export const FLEET_NODES = [
  {
    hostname: 'laptop-01',
    roles: ['coordinator', 'development'],
    architecture: 'x86_64',
    models: ['local']
  },
  {
    hostname: 'server-01',
    roles: ['worker', 'heavy'],
    architecture: 'x86_64',
    models: ['llama-70b', 'qwen-coder-32b']
  },
  {
    hostname: 'server-02',
    roles: ['worker'],
    architecture: 'x86_64',
    models: ['mistral-7b', 'phi-3']
  },
  {
    hostname: 'server-03',
    roles: ['worker', 'code-specialist'],
    architecture: 'x86_64',
    models: ['deepseek-coder-33b']
  },
  {
    hostname: 'aio-01',
    roles: ['worker'],
    architecture: 'x86_64',
    models: ['cerebras-120b']
  },
  {
    hostname: 'pi-02',
    roles: ['brain', 'monitoring'],
    architecture: 'aarch64',
    models: []
  }
];
