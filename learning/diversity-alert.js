#!/usr/bin/env node

const { Pool } = require('pg');
const fs = require('fs');

// Local PostgreSQL via Unix socket
const pool = new Pool({
  host: '/run/postgresql',  // Unix socket for peer auth
  database: 'learning',
  max: 1,
  idleTimeoutMillis: 3000,
});

const CRISIS_THRESHOLD = 80; // If any model exceeds this percentage
const HEALTHY_MIN = 15;      // Healthy distribution: all models between 15-40%
const HEALTHY_MAX = 40;

const CRISIS_LOG = '/tmp/diversity-crisis.log';
const OK_LOG = '/tmp/diversity-ok.log';

async function checkDiversity() {
  try {
    // Query all requests (or use ORDER BY timestamp DESC + LIMIT if needed)
    const result = await pool.query(`
      SELECT model, COUNT(*) as count
      FROM monitoring.execution_summary
      WHERE model IS NOT NULL
      GROUP BY model
      ORDER BY count DESC
    `);

    if (!result.rows || result.rows.length === 0) {
      console.error('No execution data found');
      process.exit(0);
    }

    // Calculate total and percentages
    const totalRequests = result.rows.reduce((sum, row) => sum + parseInt(row.count), 0);

    const distribution = result.rows.map(row => ({
      model: row.model,
      count: parseInt(row.count),
      percentage: (parseInt(row.count) / totalRequests) * 100
    }));

    // Sort by percentage descending
    distribution.sort((a, b) => b.percentage - a.percentage);

    // Check for crisis (any model > 80%)
    const crisisModel = distribution.find(d => d.percentage > CRISIS_THRESHOLD);

    if (crisisModel) {
      const timestamp = new Date().toISOString();
      const message = `[${timestamp}] DIVERSITY CRISIS: ${crisisModel.model} at ${crisisModel.percentage.toFixed(1)}% (threshold: ${CRISIS_THRESHOLD}%)\n` +
                     `Distribution: ${distribution.map(d => `${d.model}=${d.percentage.toFixed(1)}%`).join(', ')}\n`;

      console.error(message);
      fs.appendFileSync(CRISIS_LOG, message);
      process.exit(1);
    }

    // Check for healthy distribution (all models 15-40%)
    const allHealthy = distribution.every(d => d.percentage >= HEALTHY_MIN && d.percentage <= HEALTHY_MAX);

    if (allHealthy) {
      const timestamp = new Date().toISOString();
      const message = `[${timestamp}] DIVERSITY OK: All models within ${HEALTHY_MIN}-${HEALTHY_MAX}%\n` +
                     `Distribution: ${distribution.map(d => `${d.model}=${d.percentage.toFixed(1)}%`).join(', ')}\n`;

      console.log(message);
      fs.appendFileSync(OK_LOG, message);
      process.exit(0);
    }

    // Neither crisis nor perfect - log current state but exit OK
    const timestamp = new Date().toISOString();
    const message = `[${timestamp}] DIVERSITY ACCEPTABLE: ${distribution.map(d => `${d.model}=${d.percentage.toFixed(1)}%`).join(', ')}\n`;

    console.log(message);
    process.exit(0);

  } catch (error) {
    console.error('Error checking diversity:', error.message);
    console.error('Full error:', error);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

checkDiversity();
