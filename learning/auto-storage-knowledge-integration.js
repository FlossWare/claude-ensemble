/**
 * Auto-Storage Knowledge Integration
 *
 * Extends auto-storage-integration.js to use knowledge system (PostgreSQL + pgvector)
 * instead of custom chunking and embedding.
 *
 * Benefits:
 * - Semantic chunking via tools/semantic_chunker.py
 * - Provenance tracking
 * - Unified knowledge base
 * - Fast HNSW similarity search (0.4ms)
 *
 * Integration points:
 * - storeWorkflowCompletion() → store result + learnings
 * - storeMemoryUpdate() → store memory file content
 * - storeConversationChunk() → store conversation turns
 */

import { getKnowledgeSystem, isAvailable } from '../shared/knowledge-system-adapter.js';

class AutoStorageKnowledge {
  constructor() {
    if (!isAvailable()) {
      console.warn('⚠️  Knowledge system not available - falling back to legacy storage');
      this.available = false;
      return;
    }

    this.ks = getKnowledgeSystem();
    this.available = true;
  }

  /**
   * Store workflow result with semantic chunking
   */
  async storeWorkflowResult(workflowResult) {
    if (!this.available) return null;

    const {
      workflow_id,
      workflow_name,
      result,
    } = workflowResult;

    const content = result.text || result.summary || '';
    if (!content.trim()) return null;

    return this.ks.storeKnowledge({
      content,
      source: workflow_id,
      source_type: 'workflow_result',
      metadata: {
        workflow_name,
        task_id: workflowResult.task_id,
        run_id: workflowResult.run_id,
        outcome: workflowResult.outcome,
        duration_ms: workflowResult.duration_ms,
        input_tokens: workflowResult.input_tokens,
        output_tokens: workflowResult.output_tokens,
        cost_usd: workflowResult.cost_usd,
        timestamp: new Date().toISOString(),
      },
      actor: 'auto-storage',
    });
  }

  /**
   * Store workflow learnings
   */
  async storeWorkflowLearnings(workflowId, learnings) {
    if (!this.available || !learnings || learnings.length === 0) return [];

    const stored = [];
    for (const learning of learnings) {
      try {
        const content = [
          `Learning: ${learning.description}`,
          `Actionable Insight: ${learning.actionable_insight}`,
          learning.context ? `Context: ${learning.context}` : '',
        ].filter(Boolean).join('\n\n');

        const entryId = await this.ks.storeKnowledge({
          content,
          source: workflowId,
          source_type: 'workflow_learning',
          metadata: {
            description: learning.description,
            actionable_insight: learning.actionable_insight,
            importance: learning.importance,
            categories: learning.categories,
            timestamp: new Date().toISOString(),
          },
          actor: 'auto-storage',
        });

        stored.push(entryId);
      } catch (err) {
        console.error(`Failed to store learning: ${err.message}`);
      }
    }

    return stored;
  }

  /**
   * Store memory file update
   */
  async storeMemoryUpdate(memoryFilePath, content, metadata) {
    if (!this.available) return null;

    return this.ks.storeKnowledge({
      content,
      source: memoryFilePath,
      source_type: 'memory',
      metadata: {
        ...metadata,
        file_path: memoryFilePath,
        timestamp: new Date().toISOString(),
      },
      actor: 'auto-storage',
    });
  }

  /**
   * Store conversation chunk
   */
  async storeConversationChunk(conversationData) {
    if (!this.available) return null;

    const {
      session_id,
      turn_number,
      user_message,
      assistant_response,
      tools_used,
      timestamp,
    } = conversationData;

    const content = `User: ${user_message}\n\nAssistant: ${assistant_response}`;

    return this.ks.storeKnowledge({
      content,
      source: `${session_id}-turn-${turn_number}`,
      source_type: 'conversation',
      metadata: {
        session_id,
        turn_number,
        tools_used,
        timestamp: timestamp || new Date().toISOString(),
      },
      actor: 'auto-storage',
    });
  }

  /**
   * Search stored knowledge
   */
  async search(query, options = {}) {
    if (!this.available) {
      throw new Error('Knowledge system not available');
    }

    return this.ks.semanticSearch(query, options);
  }

  /**
   * Get statistics
   */
  async getStats() {
    if (!this.available) {
      return { available: false };
    }

    const stats = await this.ks.getStats();
    return { ...stats, available: true };
  }
}

// Singleton
let _instance = null;

export function getAutoStorageKnowledge() {
  if (!_instance) {
    _instance = new AutoStorageKnowledge();
  }
  return _instance;
}

export default {
  getAutoStorageKnowledge,
  AutoStorageKnowledge,
};
