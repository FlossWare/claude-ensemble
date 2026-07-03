/**
 * Auto-Storage Integration with Orchestration Queue
 *
 * Automatically stores ALL:
 * - Workflow results → PostgreSQL + vectorDB
 * - Memory updates → Embedded and indexed
 * - Conversation chunks → Session tracking
 * - GitLab issues → Searchable storage
 * - Session metadata → Comprehensive tracking
 *
 * With 197-field metadata for complete auditability
 */

const { getEnhancedOrchestrationQueue } = require('./enhanced-orchestration-adapter.js');
const { getWorkflowStorage } = require('../shared/workflow-storage-adapter.cjs');
const { chunkText: semanticChunkText } = require('../shared/semantic-chunker-adapter.cjs');
const { Pool } = require('pg');
const fs = require('fs').promises;
const path = require('path');

class AutoStorage {
  constructor() {
    this.queue = getEnhancedOrchestrationQueue();
    this.workflowStorage = getWorkflowStorage();
    this.pool = new Pool({
      host: 'laptop-01',
      user: 'sfloess',
      database: 'learning',
    });
  }

  /**
   * Auto-store workflow completion
   * Triggered when any workflow finishes
   */
  async storeWorkflowCompletion(workflowResult) {
    const {
      workflow_id,
      workflow_name,
      task_id,
      run_id,
      result,
      duration_ms,
      input_tokens,
      output_tokens,
      cost_usd,
      outcome
    } = workflowResult;

    // 1. Update orchestration queue
    await this.queue.completeTask(task_id, {
      outcome,
      result_path: result.output_path,
      result_summary: result.summary,
      actual_duration_ms: duration_ms,
      input_tokens,
      output_tokens,
      cost_usd
    });

    // 2. Store in workflow storage (existing system)
    await this.workflowStorage.storeExecution({
      workflow_id,
      workflow_name,
      task_description: result.task_description,
      total_workers: result.worker_count || 1,
      total_duration_ms: duration_ms,
      outcome
    });

    // 3. Chunk and embed result for semantic search
    if (result.text || result.summary) {
      await this.chunkAndEmbedText({
        source_type: 'workflow_result',
        source_id: workflow_id,
        text: result.text || result.summary,
        metadata: {
          workflow_name,
          task_id,
          run_id,
          outcome,
          timestamp: new Date().toISOString()
        }
      });
    }

    // 4. Extract and store learnings
    if (result.learnings && result.learnings.length > 0) {
      for (const learning of result.learnings) {
        await this.storeLearning(learning, workflow_id);
      }
    }

    console.log(`✅ Auto-stored workflow: ${workflow_id} (${outcome})`);
  }

  /**
   * Auto-store memory file updates
   * Triggered when memory/*.md files are written
   */
  async storeMemoryUpdate(memoryFilePath) {
    const content = await fs.readFile(memoryFilePath, 'utf-8');

    // Extract frontmatter
    const frontmatterMatch = content.match(/^---\n([\s\S]+?)\n---/);
    let metadata = {};
    let textContent = content;

    if (frontmatterMatch) {
      const yaml = frontmatterMatch[1];
      // Simple YAML parsing (name, description, type)
      const nameMatch = yaml.match(/name:\s*(.+)/);
      const descMatch = yaml.match(/description:\s*(.+)/);
      const typeMatch = yaml.match(/type:\s*(.+)/);

      if (nameMatch) metadata.name = nameMatch[1].trim();
      if (descMatch) metadata.description = descMatch[1].trim();
      if (typeMatch) metadata.type = typeMatch[1].trim();

      textContent = content.substring(frontmatterMatch[0].length);
    }

    // Chunk and embed memory content
    await this.chunkAndEmbedText({
      source_type: 'memory',
      source_id: path.basename(memoryFilePath, '.md'),
      text: textContent,
      metadata: {
        ...metadata,
        file_path: memoryFilePath,
        memory_type: metadata.type || 'unknown',
        timestamp: new Date().toISOString()
      }
    });

    console.log(`✅ Auto-stored memory: ${path.basename(memoryFilePath)}`);
  }

  /**
   * Auto-store conversation chunks
   * Triggered periodically during long conversations
   */
  async storeConversationChunk(conversationData) {
    const {
      session_id,
      turn_number,
      user_message,
      assistant_response,
      tools_used,
      timestamp
    } = conversationData;

    // Store full conversation turn
    await this.pool.query(`
      INSERT INTO orchestration.conversation_history
      (session_id, turn_number, user_message, assistant_response, tools_used, timestamp)
      VALUES ($1, $2, $3, $4, $5, $6)
      ON CONFLICT (session_id, turn_number) DO UPDATE SET
        assistant_response = EXCLUDED.assistant_response,
        tools_used = EXCLUDED.tools_used
    `, [session_id, turn_number, user_message, assistant_response, JSON.stringify(tools_used), timestamp]);

    // Embed for semantic search
    const combinedText = `User: ${user_message}\n\nAssistant: ${assistant_response}`;
    await this.chunkAndEmbedText({
      source_type: 'conversation',
      source_id: `${session_id}-turn-${turn_number}`,
      text: combinedText,
      metadata: {
        session_id,
        turn_number,
        tools_used,
        timestamp
      }
    });

    console.log(`✅ Auto-stored conversation turn: ${session_id} #${turn_number}`);
  }

  /**
   * Auto-store GitLab issues
   * Triggered when issues are created
   */
  async storeGitLabIssue(issue) {
    const {
      issue_id,
      repository,
      title,
      description,
      labels,
      created_at,
      url
    } = issue;

    // Store issue
    await this.pool.query(`
      INSERT INTO orchestration.gitlab_issues
      (issue_id, repository, title, description, labels, created_at, url)
      VALUES ($1, $2, $3, $4, $5, $6, $7)
      ON CONFLICT (issue_id) DO UPDATE SET
        title = EXCLUDED.title,
        description = EXCLUDED.description,
        labels = EXCLUDED.labels
    `, [issue_id, repository, title, description, labels, created_at, url]);

    // Embed for semantic search
    await this.chunkAndEmbedText({
      source_type: 'gitlab_issue',
      source_id: issue_id,
      text: `${title}\n\n${description}`,
      metadata: {
        repository,
        labels,
        created_at,
        url
      }
    });

    console.log(`✅ Auto-stored GitLab issue: ${issue_id}`);
  }

  /**
   * Chunk and embed text with vector storage
   * Uses semantic chunking for texts >500 chars to preserve meaning boundaries
   */
  async chunkAndEmbedText({ source_type, source_id, text, metadata }) {
    if (!text || text.trim().length === 0) return;

    // Use semantic chunking for large texts, direct storage for small ones
    let chunks;
    if (text.length > 500) {
      const semanticChunks = semanticChunkText(text, { minChunkSize: 300, maxChunkSize: 1500, overlapSize: 100 });
      chunks = (semanticChunks && semanticChunks.length > 0)
        ? semanticChunks.map(c => c.content || c)
        : [text];
    } else {
      chunks = [text];
    }

    for (let i = 0; i < chunks.length; i++) {
      const chunk = chunks[i];
      if (!chunk || chunk.trim().length < 20) continue;

      // Generate embedding
      const embedding = await this.queue.generateEmbedding(chunk);
      if (!embedding) continue;

      // Store in auto_storage schema
      await this.pool.query(`
        INSERT INTO orchestration.auto_storage
        (source_type, source_id, chunk_index, text, embedding, metadata)
        VALUES ($1, $2, $3, $4, $5::vector, $6)
      `, [source_type, source_id, i, chunk, embedding, JSON.stringify({
        ...metadata,
        chunk_index: i,
        total_chunks: chunks.length,
        chunking_method: text.length > 500 ? 'semantic' : 'direct'
      })]);
    }
  }

  /**
   * Store extracted learning
   */
  async storeLearning(learning, source_workflow_id) {
    const { description, actionable_insight, importance, categories } = learning;

    await this.pool.query(`
      INSERT INTO workflow.learnings
      (workflow_execution_id, description, actionable_insight, importance, categories)
      SELECT id, $2, $3, $4, $5
      FROM workflow.executions
      WHERE workflow_id = $1
      LIMIT 1
    `, [source_workflow_id, description, actionable_insight, importance, categories]);
  }

  async close() {
    await this.queue.close();
    await this.pool.end();
  }
}

// Singleton
let instance = null;

function getAutoStorage() {
  if (!instance) {
    instance = new AutoStorage();
  }
  return instance;
}

module.exports = {
  AutoStorage,
  getAutoStorage
};
