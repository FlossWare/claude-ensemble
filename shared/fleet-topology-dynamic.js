/**
 * Dynamic Fleet Topology Loader
 * Loads worker list from registry service instead of static config
 */

import http from 'http';

const REGISTRY_URL = 'http://aio-01:8001/workers?active_only=true';

/**
 * Fetch active workers from registry service
 * @returns {Promise<Array>} List of active worker nodes
 */
export async function loadFleetTopology() {
  return new Promise((resolve, reject) => {
    http.get(REGISTRY_URL, (res) => {
      let data = '';

      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const response = JSON.parse(data);

          // Convert to fleet-topology format
          const workers = response.workers.map(w => ({
            hostname: w.hostname,
            ip: w.ip_address,
            ssh_user: 'claude',
            roles: w.roles,
            capabilities: w.capabilities,
            cpu_cores: w.cpu_cores,
            ram_gb: w.ram_gb,
            architecture: w.architecture,
            last_seen: w.last_seen
          }));

          resolve(workers);
        } catch (err) {
          reject(new Error(`Failed to parse registry response: ${err.message}`));
        }
      });
    }).on('error', (err) => {
      // Fallback to static topology if registry unavailable
      console.warn('[fleet-topology-dynamic] Registry unavailable, using static fallback');
      import('./fleet-topology.js').then(mod => {
        resolve(mod.FLEET_NODES.filter(n => n.roles && n.roles.includes('worker')));
      });
    });
  });
}

/**
 * Get cached topology (5-minute TTL)
 */
let cachedTopology = null;
let cacheTimestamp = 0;
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

export async function getFleetTopology() {
  const now = Date.now();

  if (cachedTopology && (now - cacheTimestamp) < CACHE_TTL_MS) {
    return cachedTopology;
  }

  cachedTopology = await loadFleetTopology();
  cacheTimestamp = now;
  return cachedTopology;
}
