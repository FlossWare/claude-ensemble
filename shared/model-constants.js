/**
 * Shared Model Constants
 *
 * Centralized model lists to avoid duplication across orchestrator and workflows.
 * Single source of truth for default model configurations.
 */

/**
 * Default models for non-proprietary work (6 models for maximum quality)
 * Includes diverse providers: Anthropic (4) + OpenAI (1) + Google (1)
 */
export const DEFAULT_MODELS = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];

/**
 * Anthropic-only models for Red Hat proprietary compliance (3 models)
 * Restricted to Anthropic family to meet Red Hat AI compliance requirements
 */
export const ANTHROPIC_MODELS = ['opus', 'sonnet', 'haiku'];

/**
 * Single model fallback (used when count=1)
 */
export const DEFAULT_SINGLE_MODEL = 'sonnet';
