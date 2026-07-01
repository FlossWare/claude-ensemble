-- Migration: Update Cohere models to current versions
-- Date: 2026-07-01
-- Reason: command-r was deprecated Sept 2025

UPDATE api_models 
SET enabled = false, notes = 'Deprecated Sept 2025'
WHERE model_name = 'command-r' AND provider = 'cohere';

INSERT INTO api_models (model_name, provider, tier, cost_input_per_1k, cost_output_per_1k, enabled, notes)
VALUES 
  ('command-r-plus-08-2024', 'cohere', 'high', 0.003, 0.015, true, 'Current command-r-plus (Aug 2024)'),
  ('command-r-08-2024', 'cohere', 'medium', 0.0005, 0.0015, true, 'Current command-r (Aug 2024)')
ON CONFLICT (model_name) DO UPDATE SET
  enabled = true,
  notes = EXCLUDED.notes;
