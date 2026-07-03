/**
 * Advanced Filter Builder
 *
 * SQL WHERE clause builder for PostgreSQL JSON operators.
 * Supports: AND/OR/NOT, ranges, metadata filtering, vector similarity.
 *
 * Designed for workflow storage and monitoring tables with JSONB metadata columns.
 * All generated queries use parameterized statements ($1, $2, ...) for safety.
 *
 * Created: 2026-07-03
 */

/**
 * Advanced Filter Builder Class
 *
 * Composable SQL WHERE clause generation with parameter safety.
 * Handles complex nested conditions with AND/OR/NOT logic.
 *
 * Example:
 *   const filter = new AdvancedFilter('workflow.worker_results')
 *     .where('outcome', '=', 'success')
 *     .where('confidence', '>', 0.8)
 *     .where('metadata', '@>', { retried: true })
 *     .or([
 *       { field: 'model', op: '=', value: 'opus' },
 *       { field: 'model', op: '=', value: 'sonnet' }
 *     ])
 *     .build();
 *   // => { sql: "outcome = $1 AND confidence > $2 AND metadata @> $3 AND (model = $4 OR model = $5)",
 *   //      params: ['success', 0.8, { retried: true }, 'opus', 'sonnet'] }
 */
class AdvancedFilter {
  constructor(tableName = null) {
    this.tableName = tableName;
    this.conditions = [];
    this.params = [];
    this.paramIndex = 1;
  }

  /**
   * Add a simple WHERE condition
   *
   * @param {string} field - Column name (e.g., 'outcome', 'metadata.key')
   * @param {string} op - Operator: '=', '!=', '>', '>=', '<', '<=', 'IN', 'NOT IN',
   *                      'LIKE', 'ILIKE', '@>', '<@', '@@', 'CONTAINS', 'STARTS_WITH'
   * @param {any} value - Value to compare (scalar, array for IN/NOT IN, object for @>/<@)
   * @returns {AdvancedFilter} this (for chaining)
   *
   * Examples:
   *   .where('outcome', '=', 'success')
   *   .where('confidence', '>', 0.8)
   *   .where('model', 'IN', ['opus', 'sonnet', 'haiku'])
   *   .where('metadata', '@>', { retry_count: 1 })  // JSON containment
   *   .where('task_description', 'ILIKE', '%firmware%')
   */
  where(field, op, value) {
    if (!field || !op) {
      throw new Error('where() requires field and operator');
    }

    const fieldName = this._normalizeField(field);
    const clause = this._buildCondition(fieldName, op, value);

    this.conditions.push(clause);
    return this;
  }

  /**
   * Add an AND group of conditions
   * Useful for grouping multiple conditions with AND
   *
   * @param {Array<Object>} conditions - Array of { field, op, value }
   * @returns {AdvancedFilter} this (for chaining)
   *
   * Example:
   *   .and([
   *     { field: 'outcome', op: '=', value: 'success' },
   *     { field: 'confidence', op: '>', value: 0.8 }
   *   ])
   */
  and(conditions) {
    if (!Array.isArray(conditions) || conditions.length === 0) {
      return this;
    }

    const clauses = conditions
      .map(cond => this._buildCondition(
        this._normalizeField(cond.field),
        cond.op,
        cond.value
      ));

    const combined = '(' + clauses.join(' AND ') + ')';
    this.conditions.push(combined);
    return this;
  }

  /**
   * Add an OR group of conditions
   * Useful for alternative conditions
   *
   * @param {Array<Object>} conditions - Array of { field, op, value }
   * @returns {AdvancedFilter} this (for chaining)
   *
   * Example:
   *   .or([
   *     { field: 'model', op: '=', value: 'opus' },
   *     { field: 'model', op: '=', value: 'sonnet' }
   *   ])
   */
  or(conditions) {
    if (!Array.isArray(conditions) || conditions.length === 0) {
      return this;
    }

    const clauses = conditions
      .map(cond => this._buildCondition(
        this._normalizeField(cond.field),
        cond.op,
        cond.value
      ));

    const combined = '(' + clauses.join(' OR ') + ')';
    this.conditions.push(combined);
    return this;
  }

  /**
   * Add a NOT condition
   * Inverts the logic of a condition
   *
   * @param {string} field - Column name
   * @param {string} op - Operator
   * @param {any} value - Value to compare
   * @returns {AdvancedFilter} this (for chaining)
   *
   * Example:
   *   .not('outcome', '=', 'error')
   *   .not('model', 'IN', ['test-model'])
   */
  not(field, op, value) {
    const fieldName = this._normalizeField(field);
    const clause = this._buildCondition(fieldName, op, value);

    this.conditions.push('NOT (' + clause + ')');
    return this;
  }

  /**
   * Add a range condition
   * Useful for between/range queries
   *
   * @param {string} field - Column name
   * @param {number|Date} minValue - Minimum value (inclusive)
   * @param {number|Date} maxValue - Maximum value (inclusive)
   * @returns {AdvancedFilter} this (for chaining)
   *
   * Example:
   *   .range('duration_ms', 100, 5000)
   *   .range('created_at', new Date('2026-06-01'), new Date('2026-06-30'))
   */
  range(field, minValue, maxValue) {
    const fieldName = this._normalizeField(field);

    const minParam = '$' + (this.paramIndex++);
    const maxParam = '$' + (this.paramIndex++);

    this.params.push(minValue, maxValue);
    this.conditions.push(`${fieldName} >= ${minParam} AND ${fieldName} <= ${maxParam}`);

    return this;
  }

  /**
   * Filter by metadata JSON field
   * Supports nested key queries and partial matches
   *
   * @param {Object} metadataFilter - Metadata query object
   *   Examples:
   *     { retried: true }  -> metadata @> '{"retried": true}'
   *     { 'context_used': true, 'context_count': 3 }
   *     Nested: { 'config.model': 'opus' } -> metadata @> '{"config": {"model": "opus"}}'
   * @param {string} operator - '@>' (contains), '<@' (contained by), '@@' (text search)
   * @returns {AdvancedFilter} this (for chaining)
   *
   * Example:
   *   .metadata({ retried: true, outcome: 'success' })
   *   .metadata({ 'config.parallelism': 4 })
   */
  metadata(metadataFilter, operator = '@>') {
    if (!metadataFilter || typeof metadataFilter !== 'object') {
      throw new Error('metadata() requires an object filter');
    }

    // Convert flat nested keys to nested object structure
    const metadataObj = this._flattenToNested(metadataFilter);

    const param = '$' + (this.paramIndex++);
    this.params.push(metadataObj);

    const condition = `metadata ${operator} ${param}::jsonb`;
    this.conditions.push(condition);

    return this;
  }

  /**
   * Filter by text search in metadata
   * Uses PostgreSQL full-text search operators
   *
   * @param {string} searchText - Text to search for
   * @param {string} field - Metadata field to search (optional, searches all text if omitted)
   * @returns {AdvancedFilter} this (for chaining)
   *
   * Example:
   *   .fullTextSearch('firmware reverse engineering')
   *   .fullTextSearch('retry', 'description')
   */
  fullTextSearch(searchText, field = null) {
    if (!searchText || typeof searchText !== 'string') {
      throw new Error('fullTextSearch() requires a text string');
    }

    const param = '$' + (this.paramIndex++);
    this.params.push(searchText);

    let condition;
    if (field) {
      const fieldName = this._normalizeField(field);
      condition = `${fieldName}::text ILIKE '%' || ${param} || '%'`;
    } else {
      // Search across all text columns (implementation-specific)
      condition = `(outcome::text || model::text || task_assigned::text) ILIKE '%' || ${param} || '%'`;
    }

    this.conditions.push(condition);
    return this;
  }

  /**
   * Vector similarity search (pgvector)
   * Finds records with embedding vectors similar to the given vector
   *
   * @param {string} embeddingField - Column name (e.g., 'task_embedding', 'result_embedding')
   * @param {Array<number>} vector - Embedding vector to compare
   * @param {number} threshold - Similarity threshold (0-1, cosine distance)
   * @returns {AdvancedFilter} this (for chaining)
   *
   * Example:
   *   .vectorSimilarity('task_embedding', [0.1, 0.2, ..., 0.9], 0.8)
   */
  vectorSimilarity(embeddingField, vector, threshold = 0.8) {
    if (!embeddingField || !Array.isArray(vector) || vector.length === 0) {
      throw new Error('vectorSimilarity() requires field and non-empty vector');
    }

    if (threshold < 0 || threshold > 1) {
      throw new Error('vectorSimilarity() threshold must be between 0 and 1');
    }

    const vectorParam = '$' + (this.paramIndex++);
    const thresholdParam = '$' + (this.paramIndex++);

    this.params.push(vector, threshold);

    const fieldName = this._normalizeField(embeddingField);
    const condition = `(${fieldName} <=> ${vectorParam}::vector) <= ${thresholdParam}`;
    this.conditions.push(condition);

    return this;
  }

  /**
   * Add a custom raw SQL condition
   * Use sparingly - only when other methods don't suffice
   * IMPORTANT: Caller is responsible for SQL injection prevention
   *
   * @param {string} rawSql - Raw SQL condition (must be safe!)
   * @param {Array<any>} params - Parameters for the SQL (optional)
   * @returns {AdvancedFilter} this (for chaining)
   *
   * Example:
   *   .raw('confidence > $' + (paramIndex) + ' AND duration_ms < $' + (paramIndex+1),
   *        [0.8, 5000])
   */
  raw(rawSql, params = []) {
    if (!rawSql || typeof rawSql !== 'string') {
      throw new Error('raw() requires a SQL string');
    }

    this.conditions.push(rawSql);
    if (Array.isArray(params) && params.length > 0) {
      this.params.push(...params);
      this.paramIndex += params.length;
    }

    return this;
  }

  /**
   * Build the final WHERE clause
   *
   * @returns {Object} { sql, params, hasConditions }
   *   - sql: Complete WHERE clause (without WHERE keyword)
   *   - params: Array of parameters for parameterized query
   *   - hasConditions: Boolean indicating if any conditions were added
   *
   * Example:
   *   const { sql, params } = filter.build();
   *   const query = `SELECT * FROM table WHERE ${sql}`;
   *   client.query(query, params);
   */
  build() {
    if (this.conditions.length === 0) {
      return {
        sql: '',
        params: [],
        hasConditions: false
      };
    }

    return {
      sql: this.conditions.join(' AND '),
      params: this.params,
      hasConditions: true
    };
  }

  /**
   * Get full query with SELECT
   *
   * @param {string} selectClause - SELECT clause (default: '*')
   * @param {string} orderBy - ORDER BY clause (optional)
   * @param {number} limit - LIMIT clause (optional)
   * @param {number} offset - OFFSET clause (optional)
   * @returns {Object} { sql, params }
   *
   * Example:
   *   const { sql, params } = filter.buildQuery(
   *     'outcome, COUNT(*)',
   *     'outcome ASC',
   *     10
   *   );
   */
  buildQuery(selectClause = '*', orderBy = null, limit = null, offset = null) {
    if (!this.tableName) {
      throw new Error('buildQuery() requires tableName to be set in constructor');
    }

    let sql = `SELECT ${selectClause} FROM ${this.tableName}`;

    const { sql: whereSql, hasConditions } = this.build();
    if (hasConditions) {
      sql += ` WHERE ${whereSql}`;
    }

    if (orderBy) {
      sql += ` ORDER BY ${orderBy}`;
    }

    if (limit !== null) {
      sql += ` LIMIT ${limit}`;
    }

    if (offset !== null) {
      sql += ` OFFSET ${offset}`;
    }

    return {
      sql,
      params: this.params
    };
  }

  /**
   * Build DELETE query
   *
   * @returns {Object} { sql, params }
   *
   * Example:
   *   const { sql, params } = filter.buildDelete();
   *   client.query(sql, params);
   */
  buildDelete() {
    if (!this.tableName) {
      throw new Error('buildDelete() requires tableName to be set in constructor');
    }

    const { sql: whereSql, hasConditions } = this.build();

    if (!hasConditions) {
      throw new Error('buildDelete() refuses to delete without WHERE clause');
    }

    return {
      sql: `DELETE FROM ${this.tableName} WHERE ${whereSql}`,
      params: this.params
    };
  }

  /**
   * Build UPDATE query
   *
   * @param {Object} updateValues - { column: value, ... }
   * @returns {Object} { sql, params }
   *
   * Example:
   *   const { sql, params } = filter.buildUpdate({ outcome: 'success', updated_at: new Date() });
   *   client.query(sql, params);
   */
  buildUpdate(updateValues) {
    if (!this.tableName) {
      throw new Error('buildUpdate() requires tableName to be set in constructor');
    }

    if (!updateValues || typeof updateValues !== 'object') {
      throw new Error('buildUpdate() requires updateValues object');
    }

    const { sql: whereSql, hasConditions } = this.build();
    if (!hasConditions) {
      throw new Error('buildUpdate() refuses to update without WHERE clause');
    }

    const setClause = Object.keys(updateValues)
      .map((key, idx) => {
        const param = '$' + (this.params.length + idx + 1);
        return `${key} = ${param}`;
      })
      .join(', ');

    const updateParams = Object.values(updateValues);

    return {
      sql: `UPDATE ${this.tableName} SET ${setClause} WHERE ${whereSql}`,
      params: [...this.params, ...updateParams]
    };
  }

  /**
   * Reset the filter (clear all conditions)
   *
   * @returns {AdvancedFilter} this (for chaining)
   */
  reset() {
    this.conditions = [];
    this.params = [];
    this.paramIndex = 1;
    return this;
  }

  /**
   * Clone the filter
   * Useful for creating alternative filter paths without modifying original
   *
   * @returns {AdvancedFilter} New filter instance with copied state
   *
   * Example:
   *   const filter1 = new AdvancedFilter('table')
   *     .where('outcome', '=', 'success');
   *   const filter2 = filter1.clone()
   *     .where('confidence', '>', 0.8);
   *   // filter1 and filter2 are independent
   */
  clone() {
    const cloned = new AdvancedFilter(this.tableName);
    cloned.conditions = [...this.conditions];
    cloned.params = [...this.params];
    cloned.paramIndex = this.paramIndex;
    return cloned;
  }

  /**
   * Debug: Get current filter state
   *
   * @returns {Object} { conditions, params, paramIndex, sql }
   */
  debug() {
    const { sql } = this.build();
    return {
      conditions: this.conditions,
      params: this.params,
      paramIndex: this.paramIndex,
      sql
    };
  }

  // ==================== Private Methods ====================

  /**
   * Build a single condition clause
   * Handles different operators and value types
   *
   * @private
   */
  _buildCondition(field, op, value) {
    const upperOp = op.toUpperCase();

    if (upperOp === 'IN') {
      if (!Array.isArray(value) || value.length === 0) {
        throw new Error(`IN operator requires non-empty array, got: ${typeof value}`);
      }

      const placeholders = value.map(() => '$' + (this.paramIndex++)).join(', ');
      this.params.push(...value);
      return `${field} IN (${placeholders})`;

    } else if (upperOp === 'NOT IN') {
      if (!Array.isArray(value) || value.length === 0) {
        throw new Error(`NOT IN operator requires non-empty array`);
      }

      const placeholders = value.map(() => '$' + (this.paramIndex++)).join(', ');
      this.params.push(...value);
      return `${field} NOT IN (${placeholders})`;

    } else if (upperOp === 'LIKE' || upperOp === 'ILIKE') {
      const param = '$' + (this.paramIndex++);
      this.params.push(value);
      return `${field} ${upperOp} ${param}`;

    } else if (upperOp === '@>' || upperOp === '<@' || upperOp === '@@') {
      // JSON operators
      const param = '$' + (this.paramIndex++);
      const jsonValue = typeof value === 'string' ? value : value;
      this.params.push(jsonValue);
      return `${field} ${upperOp} ${param}::jsonb`;

    } else if (upperOp === 'CONTAINS' || upperOp === 'STARTS_WITH') {
      // Custom text operators
      const param = '$' + (this.paramIndex++);
      this.params.push(value);

      if (upperOp === 'CONTAINS') {
        return `${field}::text ILIKE '%' || ${param} || '%'`;
      } else {
        return `${field}::text ILIKE ${param} || '%'`;
      }

    } else if (upperOp === 'IS NULL') {
      return `${field} IS NULL`;

    } else if (upperOp === 'IS NOT NULL') {
      return `${field} IS NOT NULL`;

    } else {
      // Standard operators: =, !=, >, >=, <, <=, <>
      const param = '$' + (this.paramIndex++);
      this.params.push(value);
      return `${field} ${op} ${param}`;
    }
  }

  /**
   * Normalize field names
   * Handles table.column references and nested JSON paths
   *
   * @private
   */
  _normalizeField(field) {
    if (!field || typeof field !== 'string') {
      throw new Error(`Invalid field name: ${field}`);
    }

    // If already contains table prefix or special operators, return as-is
    if (field.includes('.') && !field.includes('metadata')) {
      return field;
    }

    // Handle metadata JSON paths: 'metadata.config.model' -> "metadata"->'config'->>'model'
    if (field.startsWith('metadata.')) {
      const parts = field.split('.');
      let jsonPath = '"' + parts[0] + '"';

      for (let i = 1; i < parts.length; i++) {
        if (i === parts.length - 1) {
          // Last part: use ->> for text extraction
          jsonPath += `->>'${parts[i]}'`;
        } else {
          // Intermediate parts: use -> for JSON access
          jsonPath += `->'${parts[i]}'`;
        }
      }

      return jsonPath;
    }

    return field;
  }

  /**
   * Convert flat dotted keys to nested object structure
   * Example: { 'config.model': 'opus' } -> { config: { model: 'opus' } }
   *
   * @private
   */
  _flattenToNested(flat) {
    const nested = {};

    for (const [key, value] of Object.entries(flat)) {
      if (key.includes('.')) {
        const parts = key.split('.');
        let current = nested;

        for (let i = 0; i < parts.length - 1; i++) {
          if (!current[parts[i]]) {
            current[parts[i]] = {};
          }
          current = current[parts[i]];
        }

        current[parts[parts.length - 1]] = value;
      } else {
        nested[key] = value;
      }
    }

    return nested;
  }
}

// ==================== Utility Functions ====================

/**
 * Create a new filter instance
 *
 * @param {string} tableName - Optional table name
 * @returns {AdvancedFilter} New filter instance
 *
 * Example:
 *   const filter = createFilter('workflow.worker_results');
 */
function createFilter(tableName = null) {
  return new AdvancedFilter(tableName);
}

/**
 * Helper: Build common workflow queries
 *
 * Common preset filters for typical workflow queries
 */
const presets = {
  /**
   * Filter successful workflows
   */
  successfulOnly: (tableName) => {
    return createFilter(tableName).where('outcome', '=', 'success');
  },

  /**
   * Filter high-confidence results
   */
  highConfidence: (tableName, threshold = 0.8) => {
    return createFilter(tableName).where('confidence', '>', threshold);
  },

  /**
   * Filter recent executions
   */
  recent: (tableName, hours = 24) => {
    const since = new Date();
    since.setHours(since.getHours() - hours);
    return createFilter(tableName)
      .where('created_at', '>', since);
  },

  /**
   * Filter by model
   */
  byModel: (tableName, models) => {
    const modelArray = Array.isArray(models) ? models : [models];
    return createFilter(tableName).where('model', 'IN', modelArray);
  },

  /**
   * Filter by cost range
   */
  byQuickest: (tableName, maxMs = 5000) => {
    return createFilter(tableName).where('duration_ms', '<', maxMs);
  }
};

// ==================== Export ====================

export {
  AdvancedFilter,
  createFilter,
  presets
};
