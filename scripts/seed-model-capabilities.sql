-- Manual seed: Top 10 models with known capabilities
-- Bootstrap the orchestrator while GA evolves better mappings

-- Code-focused models
INSERT INTO learning.model_capabilities
  (model_id, provider, code_generation, code_review, research, math_reasoning, general_qa, avg_latency_ms, test_count, notes)
VALUES
  ('qwen/qwen3-coder:free', 'openrouter', 0.85, 0.75, 0.60, 0.70, 0.75, 1800, 1, 'Manual seed - specialized code model'),
  ('cohere/north-mini-code:free', 'openrouter', 0.80, 0.70, 0.55, 0.65, 0.70, 1500, 1, 'Manual seed - code-focused'),

-- Reasoning models
  ('groq/llama-3.3-70b-versatile', 'groq', 0.75, 0.70, 0.80, 0.85, 0.80, 1200, 1, 'Manual seed - strong reasoning'),
  ('google/gemini-2.0-flash-exp:free', 'openrouter', 0.70, 0.75, 0.85, 0.80, 0.82, 1400, 1, 'Manual seed - research/analysis'),
  ('mistral/mistral-large-latest', 'mistral', 0.78, 0.80, 0.82, 0.83, 0.85, 1600, 1, 'Manual seed - general purpose strong'),

-- Fast models
  ('google/gemma-4-31b-it:free', 'openrouter', 0.72, 0.68, 0.75, 0.70, 0.78, 900, 1, 'Manual seed - fast general QA'),
  ('meta-llama/llama-3.3-70b-instruct:free', 'openrouter', 0.76, 0.72, 0.78, 0.82, 0.80, 1100, 1, 'Manual seed - balanced performance'),

-- Specialized
  ('nousresearch/hermes-3-llama-3.1-405b:free', 'openrouter', 0.82, 0.85, 0.80, 0.85, 0.83, 2200, 1, 'Manual seed - high quality, slower'),
  ('nvidia/nemotron-3-ultra-550b-a55b:free', 'openrouter', 0.80, 0.82, 0.83, 0.84, 0.82, 2500, 1, 'Manual seed - massive model'),
  ('deepseek/deepseek-chat', 'deepinfra', 0.74, 0.70, 0.72, 0.88, 0.75, 1700, 1, 'Manual seed - math reasoning specialist')

ON CONFLICT (model_id) DO UPDATE SET
  code_generation = EXCLUDED.code_generation,
  code_review = EXCLUDED.code_review,
  research = EXCLUDED.research,
  math_reasoning = EXCLUDED.math_reasoning,
  general_qa = EXCLUDED.general_qa,
  avg_latency_ms = EXCLUDED.avg_latency_ms,
  test_count = learning.model_capabilities.test_count + 1,
  notes = EXCLUDED.notes,
  last_tested = NOW();
