/**
 * Shared Fleet Topology Configuration
 *
 * Single source of truth for fleet node definitions.
 * Used by: fleet-activity-collector.js, fleet-prometheus-exporter.js
 *
 * ARCHITECTURE: 8 API-only workers + 1 infrastructure orchestrator
 * - All workers use SSH user 'claude'
 * - No local models active (dormant, not deleted)
 * - Total: 44+ cores for parallel API calls
 */

export const FLEET_NODES = [
  // Infrastructure Orchestrator (NOT a worker)
  {
    hostname: 'aio-01',
    ip: '192.168.1.11',
    roles: ['orchestrator', 'infrastructure'],
    architecture: 'x86_64',
    models: [],
    services: ['postgresql-17:5433', 'neo4j', 'routing'],
    ssh_user: 'claude',
    notes: 'Infrastructure only - PostgreSQL + Neo4j + routing logic'
  },

  // Workers (8 total, API-only)
  {
    hostname: 'server-01',
    roles: ['worker', 'api-only'],
    architecture: 'x86_64',
    cpu_cores: 8,
    ram_gb: 'high',
    models: [],
    ssh_user: 'claude',
    notes: 'API-only, 8 cores, high RAM'
  },
  {
    hostname: 'server-02',
    roles: ['worker', 'api-only'],
    architecture: 'x86_64',
    cpu_cores: 8,
    ram_gb: 'high',
    models: [],
    ssh_user: 'claude',
    notes: 'API-only, 8 cores, high RAM'
  },
  {
    hostname: 'server-03',
    roles: ['worker', 'api-only'],
    architecture: 'x86_64',
    cpu_cores: 8,
    ram_gb: 'high',
    models: [],
    ssh_user: 'claude',
    notes: 'API-only, 8 cores, high RAM'
  },
  {
    hostname: 'laptop-01',
    roles: ['worker', 'api-only', 'development'],
    architecture: 'x86_64',
    cpu_cores: 8,
    ram_gb: 28,
    models: [],
    ssh_user: 'claude',
    notes: 'API-only, 8 cores, 28GB available RAM'
  },
  {
    hostname: 'pi-01',
    roles: ['worker', 'api-only', 'lightweight'],
    architecture: 'aarch64',
    cpu_cores: 4,
    ram_gb: 0.424,
    models: [],
    ssh_user: 'claude',
    notes: 'API-only, 4 cores, 424MB RAM (lightweight tasks)'
  },
  {
    hostname: 'pi-02',
    roles: ['worker', 'api-only', 'monitoring'],
    architecture: 'aarch64',
    cpu_cores: 4,
    ram_gb: 0.365,
    models: [],
    ssh_user: 'claude',
    notes: 'API-only, 4 cores, 365MB RAM (monitoring + lightweight tasks)'
  },
  {
    hostname: 'desktop-ap',
    roles: ['worker', 'api-only'],
    architecture: 'x86_64',
    cpu_cores: 'unknown',
    ram_gb: 'unknown',
    models: [],
    ssh_user: 'claude',
    notes: 'API-only, specs unknown (verify if needed)'
  },
  {
    hostname: 'server-ap',
    roles: ['worker', 'api-only'],
    architecture: 'x86_64',
    cpu_cores: 'unknown',
    ram_gb: 'unknown',
    models: [],
    ssh_user: 'claude',
    notes: 'API-only, specs unknown (verify if needed)'
  }
];

// Fleet capacity summary
export const FLEET_CAPACITY = {
  total_workers: 8,
  total_cores: '44+',
  architecture: 'API-only (all workers)',
  local_models_status: 'dormant (not deleted)',
  ssh_user: 'claude',
  orchestrator: 'aio-01 (infrastructure only, not a worker)'
};
