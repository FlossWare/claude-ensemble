-- Transfer Learning Schema
-- Supports model bootstrapping and confidence decay

-- Transfer log: tracks transfer learning events
CREATE TABLE IF NOT EXISTS model_transfer_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  target_model TEXT NOT NULL,
  source_model TEXT NOT NULL,
  similarity_score REAL NOT NULL,  -- 0.0 to 1.0
  task_type TEXT,
  transfer_method TEXT DEFAULT 'similarity_weighted',  -- similarity_weighted, family_based, manual
  initial_confidence REAL NOT NULL,  -- Starting confidence (before decay)
  decay_rate REAL DEFAULT 0.1,  -- Exponential decay rate per day
  status TEXT DEFAULT 'active',  -- active, expired, superseded
  metadata TEXT,  -- JSON: { executionCount, avgQuality, expiredAt, supersededAt, etc. }
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transfer_target ON model_transfer_log(target_model, status);
CREATE INDEX IF NOT EXISTS idx_transfer_source ON model_transfer_log(source_model);
CREATE INDEX IF NOT EXISTS idx_transfer_task ON model_transfer_log(task_type);
CREATE INDEX IF NOT EXISTS idx_transfer_timestamp ON model_transfer_log(timestamp);

-- Calibration history: combined native + transferred calibration snapshots
CREATE TABLE IF NOT EXISTS calibration_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  model TEXT NOT NULL,
  task_type TEXT NOT NULL,
  calibration_source TEXT NOT NULL,  -- native, transferred, hybrid
  sample_count INTEGER DEFAULT 0,  -- Number of native samples
  transfer_count INTEGER DEFAULT 0,  -- Number of transfer sources
  avg_quality REAL,
  avg_confidence REAL,
  success_rate REAL,
  calibration_confidence REAL,  -- Overall confidence in this calibration
  transfer_sources TEXT,  -- JSON: [{ sourceModel, similarity, weight, ... }]
  native_blend_weight REAL,  -- Weight of native data in blend (0.0 to 1.0)
  metadata TEXT  -- JSON: additional context
);

CREATE INDEX IF NOT EXISTS idx_calibration_model ON calibration_history(model, task_type);
CREATE INDEX IF NOT EXISTS idx_calibration_source ON calibration_history(calibration_source);
CREATE INDEX IF NOT EXISTS idx_calibration_timestamp ON calibration_history(timestamp);

-- Model similarity cache: precomputed similarities between models
CREATE TABLE IF NOT EXISTS model_similarity_cache (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model1 TEXT NOT NULL,
  model2 TEXT NOT NULL,
  similarity_score REAL NOT NULL,
  similarity_components TEXT,  -- JSON: { provider, family, arch, taskType }
  task_type TEXT,  -- NULL for general similarity
  computed_at TEXT NOT NULL,
  execution_count1 INTEGER,  -- Sample size for model1
  execution_count2 INTEGER,  -- Sample size for model2
  UNIQUE(model1, model2, task_type)
);

CREATE INDEX IF NOT EXISTS idx_similarity_models ON model_similarity_cache(model1, model2);
CREATE INDEX IF NOT EXISTS idx_similarity_score ON model_similarity_cache(similarity_score);

-- Transfer validation results: track accuracy of transfers
CREATE TABLE IF NOT EXISTS transfer_validation (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  target_model TEXT NOT NULL,
  task_type TEXT NOT NULL,
  native_samples INTEGER NOT NULL,
  transfer_sources TEXT,  -- JSON array of source models
  native_avg_quality REAL,
  transferred_avg_quality REAL,
  native_avg_confidence REAL,
  transferred_avg_confidence REAL,
  native_success_rate REAL,
  transferred_success_rate REAL,
  quality_error REAL,  -- abs(native - transferred)
  confidence_error REAL,
  success_error REAL,
  transfer_quality REAL,  -- Overall quality score
  assessment TEXT  -- excellent, good, fair, poor
);

CREATE INDEX IF NOT EXISTS idx_validation_model ON transfer_validation(target_model, task_type);
CREATE INDEX IF NOT EXISTS idx_validation_quality ON transfer_validation(transfer_quality);
CREATE INDEX IF NOT EXISTS idx_validation_timestamp ON transfer_validation(timestamp);

-- Model family taxonomy: explicit model relationships
CREATE TABLE IF NOT EXISTS model_taxonomy (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model TEXT UNIQUE NOT NULL,
  provider TEXT NOT NULL,  -- anthropic, openai, google, meta, mistral, etc.
  family TEXT NOT NULL,  -- claude-4, gpt-4, gemini-1.5, etc.
  architecture TEXT,  -- opus, sonnet, haiku, turbo, pro, flash, etc.
  version TEXT,  -- Specific version identifier
  release_date TEXT,
  capabilities TEXT,  -- JSON: { context_window, multimodal, tools, etc. }
  metadata TEXT  -- JSON: additional info
);

CREATE INDEX IF NOT EXISTS idx_taxonomy_provider ON model_taxonomy(provider);
CREATE INDEX IF NOT EXISTS idx_taxonomy_family ON model_taxonomy(family);
CREATE INDEX IF NOT EXISTS idx_taxonomy_arch ON model_taxonomy(architecture);

-- Transfer decay schedule: precomputed decay values for performance
CREATE TABLE IF NOT EXISTS transfer_decay_schedule (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  transfer_id INTEGER NOT NULL REFERENCES model_transfer_log(id),
  days_elapsed INTEGER NOT NULL,
  decayed_confidence REAL NOT NULL,
  is_expired INTEGER DEFAULT 0,  -- 1 if below MIN_TRANSFER_CONFIDENCE
  computed_at TEXT NOT NULL,
  UNIQUE(transfer_id, days_elapsed)
);

CREATE INDEX IF NOT EXISTS idx_decay_transfer ON transfer_decay_schedule(transfer_id);
CREATE INDEX IF NOT EXISTS idx_decay_expired ON transfer_decay_schedule(is_expired);
