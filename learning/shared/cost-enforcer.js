#!/usr/bin/env node
/**
 * Cost Enforcer - Hard Budget Controls
 *
 * Implements strict daily, monthly, and per-session budget limits with enforcement.
 * Tracks costs in SQLite database at ~/.claude/learning/db/costs.db
 *
 * FEATURES:
 * - Daily budget cap ($50/day, configurable)
 * - Monthly budget cap ($1000/month, configurable)
 * - Per-session cap ($25/session, configurable)
 * - Persistent tracking in SQLite
 * - Hard rejection of API calls when budget exceeded
 * - Automatic daily counter reset at midnight
 * - Approaching-limit alerts
 * - Cost reporting and analytics
 */

const fs = require('fs')
const path = require('path')
const sqlite3 = require('sqlite3').verbose()
const os = require('os')

// ============================================================================
// CONFIGURATION
// ============================================================================

const CONFIG = {
  db_path: path.join(process.env.HOME || os.homedir(), '.claude/learning/db/costs.db'),
  daily_limit_dollars: 50.00,
  monthly_limit_dollars: 1000.00,
  session_limit_dollars: 25.00,
  warn_threshold_percent: 80,
  critical_threshold_percent: 95,
  timezone_offset: process.env.TZ_OFFSET || 0, // hours from UTC
}

// ============================================================================
// MODEL PRICING
// ============================================================================

const PRICING = {
  'claude-opus': { input: 0.015, output: 0.075 },
  'claude-sonnet': { input: 0.003, output: 0.015 },
  'claude-haiku': { input: 0.00025, output: 0.00125 },
  'gpt-4o': { input: 0.005, output: 0.015 },
  'gemini-2.0-flash': { input: 0.075, output: 0.3 }, // per 1M tokens
  'fable': { input: 0.0001, output: 0.0004 },
  // Aliases for backward compatibility
  'opus': { input: 0.015, output: 0.075 },
  'sonnet': { input: 0.003, output: 0.015 },
  'haiku': { input: 0.00025, output: 0.00125 },
}

// ============================================================================
// DATABASE INITIALIZATION
// ============================================================================

class CostDatabase {
  constructor(dbPath) {
    this.dbPath = dbPath
    this.db = null
  }

  async init() {
    return new Promise((resolve, reject) => {
      // Ensure directory exists
      const dir = path.dirname(this.dbPath)
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true })
      }

      this.db = new sqlite3.Database(this.dbPath, (err) => {
        if (err) reject(err)
        else this._createTables().then(resolve).catch(reject)
      })
    })
  }

  async _createTables() {
    return new Promise((resolve, reject) => {
      this.db.serialize(() => {
        // Main cost tracking table
        this.db.run(`
          CREATE TABLE IF NOT EXISTS cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            date DATE,
            month TEXT,
            session_id TEXT,
            model TEXT NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            input_cost REAL DEFAULT 0,
            output_cost REAL DEFAULT 0,
            total_cost REAL DEFAULT 0,
            workflow_id TEXT,
            label TEXT,
            agent_id TEXT,
            rejected INTEGER DEFAULT 0,
            rejection_reason TEXT
          )
        `)

        // Daily aggregate table
        this.db.run(`
          CREATE TABLE IF NOT EXISTS daily_aggregates (
            date DATE PRIMARY KEY,
            total_cost REAL DEFAULT 0,
            call_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            rejected_calls INTEGER DEFAULT 0,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
          )
        `)

        // Monthly aggregate table
        this.db.run(`
          CREATE TABLE IF NOT EXISTS monthly_aggregates (
            month TEXT PRIMARY KEY,
            total_cost REAL DEFAULT 0,
            call_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            rejected_calls INTEGER DEFAULT 0,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
          )
        `)

        // Session tracking table
        this.db.run(`
          CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            ended_at DATETIME,
            total_cost REAL DEFAULT 0,
            call_count INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            rejected_calls INTEGER DEFAULT 0,
            agent_id TEXT,
            workflow_id TEXT
          )
        `)

        // Budget limits table (for easy override)
        this.db.run(`
          CREATE TABLE IF NOT EXISTS budget_limits (
            id TEXT PRIMARY KEY,
            daily_limit_dollars REAL DEFAULT 50.00,
            monthly_limit_dollars REAL DEFAULT 1000.00,
            session_limit_dollars REAL DEFAULT 25.00,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
          )
        `, (err) => {
          if (err) reject(err)
          else {
            // Initialize default limits if not present
            this.db.run(`
              INSERT OR IGNORE INTO budget_limits (id, daily_limit_dollars, monthly_limit_dollars, session_limit_dollars)
              VALUES ('default', ?, ?, ?)
            `, [CONFIG.daily_limit_dollars, CONFIG.monthly_limit_dollars, CONFIG.session_limit_dollars],
            (err) => {
              if (err) reject(err)
              else resolve()
            })
          }
        })
      })
    })
  }

  async close() {
    return new Promise((resolve, reject) => {
      if (this.db) {
        this.db.close((err) => {
          if (err) reject(err)
          else resolve()
        })
      } else {
        resolve()
      }
    })
  }

  run(sql, params = []) {
    return new Promise((resolve, reject) => {
      this.db.run(sql, params, function(err) {
        if (err) reject(err)
        else resolve(this)
      })
    })
  }

  get(sql, params = []) {
    return new Promise((resolve, reject) => {
      this.db.get(sql, params, (err, row) => {
        if (err) reject(err)
        else resolve(row)
      })
    })
  }

  all(sql, params = []) {
    return new Promise((resolve, reject) => {
      this.db.all(sql, params, (err, rows) => {
        if (err) reject(err)
        else resolve(rows || [])
      })
    })
  }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function getDateKey(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function getMonthKey(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
}

function calculateCost(model, inputTokens, outputTokens) {
  const pricing = PRICING[model] || PRICING[model.toLowerCase()] || PRICING.sonnet
  const inputCost = (inputTokens / 1000) * (pricing.input || 0)
  const outputCost = (outputTokens / 1000) * (pricing.output || 0)

  return {
    input_cost: inputCost,
    output_cost: outputCost,
    total_cost: inputCost + outputCost,
  }
}

function generateSessionId() {
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

// ============================================================================
// CORE ENFORCEMENT FUNCTIONS
// ============================================================================

class CostEnforcer {
  constructor(db) {
    this.db = db
    this.sessionId = null
    this.currentSessionCost = 0
  }

  async initialize(sessionId) {
    this.sessionId = sessionId || generateSessionId()

    // Create session record
    await this.db.run(`
      INSERT INTO sessions (id, agent_id, workflow_id)
      VALUES (?, ?, ?)
    `, [this.sessionId, process.env.AGENT_ID || 'unknown', process.env.WORKFLOW_ID || null])

    return this.sessionId
  }

  async getBudgetLimits() {
    const limits = await this.db.get(`
      SELECT daily_limit_dollars, monthly_limit_dollars, session_limit_dollars
      FROM budget_limits WHERE id = 'default'
    `)
    return limits || {
      daily_limit_dollars: CONFIG.daily_limit_dollars,
      monthly_limit_dollars: CONFIG.monthly_limit_dollars,
      session_limit_dollars: CONFIG.session_limit_dollars,
    }
  }

  async getDailySpent(date = new Date()) {
    const dateKey = getDateKey(date)
    const row = await this.db.get(`
      SELECT COALESCE(SUM(total_cost), 0) as total FROM cost_entries
      WHERE date = ? AND rejected = 0
    `, [dateKey])
    return row?.total || 0
  }

  async getMonthlySpent(date = new Date()) {
    const monthKey = getMonthKey(date)
    const row = await this.db.get(`
      SELECT COALESCE(SUM(total_cost), 0) as total FROM cost_entries
      WHERE month = ? AND rejected = 0
    `, [monthKey])
    return row?.total || 0
  }

  async getSessionSpent(sessionId) {
    const row = await this.db.get(`
      SELECT COALESCE(SUM(total_cost), 0) as total FROM cost_entries
      WHERE session_id = ? AND rejected = 0
    `, [sessionId])
    return row?.total || 0
  }

  async checkBudget(model, inputTokens, outputTokens, options = {}) {
    const limits = await this.getBudgetLimits()
    const cost = calculateCost(model, inputTokens, outputTokens)

    const today = new Date()
    const currentMonth = new Date()

    const [dailySpent, monthlySpent, sessionSpent] = await Promise.all([
      this.getDailySpent(today),
      this.getMonthlySpent(currentMonth),
      this.getSessionSpent(this.sessionId),
    ])

    const projectedDaily = dailySpent + cost.total_cost
    const projectedMonthly = monthlySpent + cost.total_cost
    const projectedSession = sessionSpent + cost.total_cost

    const result = {
      allowed: true,
      warnings: [],
      rejections: [],
      cost: cost.total_cost,
      daily: { spent: dailySpent, limit: limits.daily_limit_dollars, projected: projectedDaily },
      monthly: { spent: monthlySpent, limit: limits.monthly_limit_dollars, projected: projectedMonthly },
      session: { spent: sessionSpent, limit: limits.session_limit_dollars, projected: projectedSession },
    }

    // Check daily limit
    if (projectedDaily > limits.daily_limit_dollars) {
      result.allowed = false
      result.rejections.push(
        `DAILY_LIMIT_EXCEEDED: Would reach $${projectedDaily.toFixed(2)} / $${limits.daily_limit_dollars.toFixed(2)}`
      )
    } else if (projectedDaily > limits.daily_limit_dollars * (CONFIG.critical_threshold_percent / 100)) {
      result.warnings.push(
        `DAILY_CRITICAL: $${projectedDaily.toFixed(2)} (${((projectedDaily / limits.daily_limit_dollars) * 100).toFixed(1)}%)`
      )
    } else if (projectedDaily > limits.daily_limit_dollars * (CONFIG.warn_threshold_percent / 100)) {
      result.warnings.push(
        `DAILY_WARNING: $${projectedDaily.toFixed(2)} (${((projectedDaily / limits.daily_limit_dollars) * 100).toFixed(1)}%)`
      )
    }

    // Check monthly limit
    if (projectedMonthly > limits.monthly_limit_dollars) {
      result.allowed = false
      result.rejections.push(
        `MONTHLY_LIMIT_EXCEEDED: Would reach $${projectedMonthly.toFixed(2)} / $${limits.monthly_limit_dollars.toFixed(2)}`
      )
    } else if (projectedMonthly > limits.monthly_limit_dollars * (CONFIG.critical_threshold_percent / 100)) {
      result.warnings.push(
        `MONTHLY_CRITICAL: $${projectedMonthly.toFixed(2)} (${((projectedMonthly / limits.monthly_limit_dollars) * 100).toFixed(1)}%)`
      )
    } else if (projectedMonthly > limits.monthly_limit_dollars * (CONFIG.warn_threshold_percent / 100)) {
      result.warnings.push(
        `MONTHLY_WARNING: $${projectedMonthly.toFixed(2)} (${((projectedMonthly / limits.monthly_limit_dollars) * 100).toFixed(1)}%)`
      )
    }

    // Check session limit
    if (projectedSession > limits.session_limit_dollars) {
      result.allowed = false
      result.rejections.push(
        `SESSION_LIMIT_EXCEEDED: Would reach $${projectedSession.toFixed(2)} / $${limits.session_limit_dollars.toFixed(2)}`
      )
    } else if (projectedSession > limits.session_limit_dollars * (CONFIG.critical_threshold_percent / 100)) {
      result.warnings.push(
        `SESSION_CRITICAL: $${projectedSession.toFixed(2)} (${((projectedSession / limits.session_limit_dollars) * 100).toFixed(1)}%)`
      )
    } else if (projectedSession > limits.session_limit_dollars * (CONFIG.warn_threshold_percent / 100)) {
      result.warnings.push(
        `SESSION_WARNING: $${projectedSession.toFixed(2)} (${((projectedSession / limits.session_limit_dollars) * 100).toFixed(1)}%)`
      )
    }

    return result
  }

  async recordCost(model, inputTokens, outputTokens, options = {}) {
    const budgetCheck = await this.checkBudget(model, inputTokens, outputTokens, options)
    const cost = calculateCost(model, inputTokens, outputTokens)

    const today = new Date()
    const dateKey = getDateKey(today)
    const monthKey = getMonthKey(today)

    const entry = {
      date: dateKey,
      month: monthKey,
      session_id: this.sessionId,
      model,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      input_cost: cost.input_cost,
      output_cost: cost.output_cost,
      total_cost: cost.total_cost,
      workflow_id: options.workflow_id || null,
      label: options.label || null,
      agent_id: options.agent_id || process.env.AGENT_ID || 'unknown',
      rejected: budgetCheck.allowed ? 0 : 1,
      rejection_reason: budgetCheck.rejections.length > 0 ? budgetCheck.rejections.join('; ') : null,
    }

    // Record the cost entry
    await this.db.run(`
      INSERT INTO cost_entries
      (date, month, session_id, model, input_tokens, output_tokens, input_cost, output_cost, total_cost, workflow_id, label, agent_id, rejected, rejection_reason)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `, [entry.date, entry.month, entry.session_id, entry.model, entry.input_tokens, entry.output_tokens,
        entry.input_cost, entry.output_cost, entry.total_cost, entry.workflow_id, entry.label, entry.agent_id,
        entry.rejected, entry.rejection_reason])

    // Update session total
    if (!budgetCheck.allowed === false) {
      await this.db.run(`
        UPDATE sessions
        SET total_cost = total_cost + ?, call_count = call_count + 1, input_tokens = input_tokens + ?, output_tokens = output_tokens + ?
        WHERE id = ?
      `, [cost.total_cost, inputTokens, outputTokens, this.sessionId])
    } else {
      await this.db.run(`
        UPDATE sessions SET rejected_calls = rejected_calls + 1 WHERE id = ?
      `, [this.sessionId])
    }

    return {
      allowed: budgetCheck.allowed,
      cost,
      budgetCheck,
      entry,
    }
  }

  async getReport(options = {}) {
    const limits = await this.getBudgetLimits()
    const today = new Date()
    const thisMonth = new Date()

    const dateKey = getDateKey(today)
    const monthKey = getMonthKey(thisMonth)

    const [dailyData, monthlyData, sessionData, dailyDetails, monthlyDetails] = await Promise.all([
      this.db.get(`SELECT * FROM daily_aggregates WHERE date = ?`, [dateKey]),
      this.db.get(`SELECT * FROM monthly_aggregates WHERE month = ?`, [monthKey]),
      this.db.get(`SELECT * FROM sessions WHERE id = ?`, [this.sessionId]),
      this.db.all(`SELECT * FROM cost_entries WHERE date = ? ORDER BY timestamp DESC LIMIT 20`, [dateKey]),
      this.db.all(`SELECT * FROM cost_entries WHERE month = ? ORDER BY timestamp DESC LIMIT 50`, [monthKey]),
    ])

    return {
      session: {
        id: this.sessionId,
        total_cost: sessionData?.total_cost || 0,
        calls: sessionData?.call_count || 0,
        rejected: sessionData?.rejected_calls || 0,
        limit: limits.session_limit_dollars,
      },
      daily: {
        date: dateKey,
        total_cost: dailyData?.total_cost || 0,
        calls: dailyData?.call_count || 0,
        rejected: dailyData?.rejected_calls || 0,
        limit: limits.daily_limit_dollars,
        usage_percent: ((dailyData?.total_cost || 0) / limits.daily_limit_dollars * 100).toFixed(1),
      },
      monthly: {
        month: monthKey,
        total_cost: monthlyData?.total_cost || 0,
        calls: monthlyData?.call_count || 0,
        rejected: monthlyData?.rejected_calls || 0,
        limit: limits.monthly_limit_dollars,
        usage_percent: ((monthlyData?.total_cost || 0) / limits.monthly_limit_dollars * 100).toFixed(1),
      },
      recent_daily: dailyDetails.slice(0, 5),
      recent_monthly: monthlyDetails.slice(0, 10),
    }
  }

  async setBudgetLimits(daily, monthly, session) {
    await this.db.run(`
      UPDATE budget_limits
      SET daily_limit_dollars = ?, monthly_limit_dollars = ?, session_limit_dollars = ?
      WHERE id = 'default'
    `, [daily, monthly, session])

    CONFIG.daily_limit_dollars = daily
    CONFIG.monthly_limit_dollars = monthly
    CONFIG.session_limit_dollars = session

    return {
      daily: daily,
      monthly: monthly,
      session: session,
    }
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

module.exports = {
  CostDatabase,
  CostEnforcer,
  CONFIG,
  PRICING,
  getDateKey,
  getMonthKey,
  calculateCost,
  generateSessionId,
}

// ============================================================================
// CLI INTERFACE (for standalone usage)
// ============================================================================

if (require.main === module) {
  (async () => {
    const db = new CostDatabase(CONFIG.db_path)
    await db.init()

    const enforcer = new CostEnforcer(db)
    const sessionId = await enforcer.initialize()

    console.log(`Session ID: ${sessionId}`)
    console.log(`Database: ${CONFIG.db_path}`)

    // Example: Check budget before a hypothetical API call
    const check = await enforcer.checkBudget('claude-opus', 2000, 1000)
    console.log('\nBudget Check Result:')
    console.log(JSON.stringify(check, null, 2))

    // Example: Record a cost
    const record = await enforcer.recordCost('claude-opus', 2000, 1000, {
      workflow_id: 'test-workflow',
      label: 'test-call',
    })
    console.log('\nCost Record Result:')
    console.log(JSON.stringify(record, null, 2))

    // Example: Get report
    const report = await enforcer.getReport()
    console.log('\nCost Report:')
    console.log(JSON.stringify(report, null, 2))

    await db.close()
  })().catch(err => {
    console.error('Error:', err)
    process.exit(1)
  })
}
