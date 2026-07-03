const VectorStoreBase = require('./vector-store-base');
const { Pool } = require('pg');

/**
 * PostgreSQL + pgvector implementation
 * Performance: 0.4ms queries, 2-6x faster than ChromaDB
 */
class PostgresVectorStore extends VectorStoreBase {
  constructor(config = {}) {
    super(config);

    this.pool = new Pool({
      host: config.host || 'laptop-01',
      user: config.user || 'sfloess',
      database: config.database || 'learning',
      password: config.password,
      max: config.poolSize || 20,
      idleTimeoutMillis: config.idleTimeout || 30000,
      connectionTimeoutMillis: config.connectionTimeout || 2000,
    });

    this.defaultCollection = config.defaultCollection || 'documents';
    this.defaultDimensions = config.dimensions || 384;
    this.defaultDistanceMetric = config.distanceMetric || 'cosine'; // cosine, l2, inner_product
  }

  async initialize() {
    if (this.initialized) return;

    try {
      const client = await this.pool.connect();

      try {
        await client.query('CREATE EXTENSION IF NOT EXISTS vector');

        await client.query(`
          CREATE SCHEMA IF NOT EXISTS vector_store
        `);

        await this._ensureCollection(this.defaultCollection, client);

        this.initialized = true;
      } finally {
        client.release();
      }
    } catch (error) {
      throw new Error(`Failed to initialize PostgresVectorStore: ${error.message}`);
    }
  }

  async close() {
    await this.pool.end();
    this.initialized = false;
  }

  async _ensureCollection(name, client = null) {
    const shouldRelease = !client;
    if (!client) client = await this.pool.connect();

    try {
      const tableName = `vector_store.${name}`;

      await client.query(`
        CREATE TABLE IF NOT EXISTS ${tableName} (
          id TEXT PRIMARY KEY,
          embedding vector(${this.defaultDimensions}),
          metadata JSONB DEFAULT '{}'::jsonb,
          document TEXT,
          created_at TIMESTAMP DEFAULT NOW(),
          updated_at TIMESTAMP DEFAULT NOW()
        )
      `);

      const operator = this._getDistanceOperator();
      const indexExists = await client.query(`
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'vector_store'
        AND tablename = $1
        AND indexname = $2
      `, [name, `${name}_embedding_idx`]);

      if (indexExists.rows.length === 0) {
        await client.query(`
          CREATE INDEX ${name}_embedding_idx
          ON ${tableName}
          USING hnsw (embedding ${operator})
        `);
      }

      await client.query(`
        CREATE INDEX IF NOT EXISTS ${name}_metadata_idx
        ON ${tableName}
        USING gin (metadata)
      `);

    } finally {
      if (shouldRelease) client.release();
    }
  }

  _getDistanceOperator() {
    const operators = {
      cosine: 'vector_cosine_ops',
      l2: 'vector_l2_ops',
      inner_product: 'vector_ip_ops'
    };
    return operators[this.defaultDistanceMetric] || operators.cosine;
  }

  _getDistanceFunction() {
    const functions = {
      cosine: '<=>',
      l2: '<->',
      inner_product: '<#>'
    };
    return functions[this.defaultDistanceMetric] || functions.cosine;
  }

  async addDocument({ id, embedding, metadata = {}, document, collection }) {
    const coll = collection || this.defaultCollection;
    await this._ensureCollection(coll);

    const tableName = `vector_store.${coll}`;
    const embeddingStr = `[${embedding.join(',')}]`;

    await this.pool.query(`
      INSERT INTO ${tableName} (id, embedding, metadata, document)
      VALUES ($1, $2::vector, $3::jsonb, $4)
      ON CONFLICT (id) DO UPDATE SET
        embedding = EXCLUDED.embedding,
        metadata = EXCLUDED.metadata,
        document = EXCLUDED.document,
        updated_at = NOW()
    `, [id, embeddingStr, JSON.stringify(metadata), document]);

    return id;
  }

  async addDocuments(documents, collection) {
    const coll = collection || this.defaultCollection;
    await this._ensureCollection(coll);

    const client = await this.pool.connect();
    const ids = [];

    try {
      await client.query('BEGIN');

      for (const doc of documents) {
        const id = await this.addDocument({
          id: doc.id,
          embedding: doc.embedding,
          metadata: doc.metadata,
          document: doc.document,
          collection: coll
        });
        ids.push(id);
      }

      await client.query('COMMIT');
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }

    return ids;
  }

  async query({ embedding, limit = 10, filter, collection }) {
    const coll = collection || this.defaultCollection;
    const tableName = `vector_store.${coll}`;
    const embeddingStr = `[${embedding.join(',')}]`;
    const distanceFn = this._getDistanceFunction();

    let query = `
      SELECT
        id,
        embedding::text as embedding,
        metadata,
        document,
        embedding ${distanceFn} $1::vector as distance
      FROM ${tableName}
    `;

    const params = [embeddingStr];
    let paramIdx = 2;

    if (filter && Object.keys(filter).length > 0) {
      const conditions = [];
      for (const [key, value] of Object.entries(filter)) {
        conditions.push(`metadata->>'${key}' = $${paramIdx}`);
        params.push(String(value));
        paramIdx++;
      }
      query += ` WHERE ${conditions.join(' AND ')}`;
    }

    query += ` ORDER BY distance ASC LIMIT $${paramIdx}`;
    params.push(limit);

    const result = await this.pool.query(query, params);

    return result.rows.map(row => ({
      id: row.id,
      embedding: this._parseEmbedding(row.embedding),
      metadata: row.metadata,
      document: row.document,
      distance: parseFloat(row.distance)
    }));
  }

  _parseEmbedding(embeddingText) {
    if (!embeddingText) return null;
    const cleaned = embeddingText.replace(/^\[|\]$/g, '');
    return cleaned.split(',').map(x => parseFloat(x));
  }

  async getById(id, collection) {
    const coll = collection || this.defaultCollection;
    const tableName = `vector_store.${coll}`;

    const result = await this.pool.query(`
      SELECT id, embedding::text as embedding, metadata, document
      FROM ${tableName}
      WHERE id = $1
    `, [id]);

    if (result.rows.length === 0) return null;

    const row = result.rows[0];
    return {
      id: row.id,
      embedding: this._parseEmbedding(row.embedding),
      metadata: row.metadata,
      document: row.document
    };
  }

  async updateMetadata(id, metadata, collection) {
    const coll = collection || this.defaultCollection;
    const tableName = `vector_store.${coll}`;

    const result = await this.pool.query(`
      UPDATE ${tableName}
      SET metadata = metadata || $2::jsonb,
          updated_at = NOW()
      WHERE id = $1
    `, [id, JSON.stringify(metadata)]);

    return result.rowCount > 0;
  }

  async deleteById(id, collection) {
    const coll = collection || this.defaultCollection;
    const tableName = `vector_store.${coll}`;

    const result = await this.pool.query(`
      DELETE FROM ${tableName} WHERE id = $1
    `, [id]);

    return result.rowCount > 0;
  }

  async deleteByFilter(filter, collection) {
    const coll = collection || this.defaultCollection;
    const tableName = `vector_store.${coll}`;

    if (!filter || Object.keys(filter).length === 0) {
      throw new Error('Filter required for deleteByFilter (use deleteCollection to remove all)');
    }

    const conditions = [];
    const params = [];
    let paramIdx = 1;

    for (const [key, value] of Object.entries(filter)) {
      conditions.push(`metadata->>'${key}' = $${paramIdx}`);
      params.push(String(value));
      paramIdx++;
    }

    const result = await this.pool.query(`
      DELETE FROM ${tableName}
      WHERE ${conditions.join(' AND ')}
    `, params);

    return result.rowCount;
  }

  async count(filter, collection) {
    const coll = collection || this.defaultCollection;
    const tableName = `vector_store.${coll}`;

    let query = `SELECT COUNT(*) as count FROM ${tableName}`;
    const params = [];

    if (filter && Object.keys(filter).length > 0) {
      const conditions = [];
      let paramIdx = 1;

      for (const [key, value] of Object.entries(filter)) {
        conditions.push(`metadata->>'${key}' = $${paramIdx}`);
        params.push(String(value));
        paramIdx++;
      }

      query += ` WHERE ${conditions.join(' AND ')}`;
    }

    const result = await this.pool.query(query, params);
    return parseInt(result.rows[0].count);
  }

  async listCollections() {
    const result = await this.pool.query(`
      SELECT tablename
      FROM pg_tables
      WHERE schemaname = 'vector_store'
      ORDER BY tablename
    `);

    return result.rows.map(row => row.tablename);
  }

  async createCollection(name, options = {}) {
    const dimensions = options.dimensions || this.defaultDimensions;
    const oldDimensions = this.defaultDimensions;

    this.defaultDimensions = dimensions;
    await this._ensureCollection(name);
    this.defaultDimensions = oldDimensions;
  }

  async deleteCollection(name) {
    const tableName = `vector_store.${name}`;

    await this.pool.query(`DROP TABLE IF EXISTS ${tableName} CASCADE`);
    return true;
  }

  async healthCheck() {
    try {
      const result = await this.pool.query('SELECT 1 as health');
      return result.rows.length > 0 && result.rows[0].health === 1;
    } catch (error) {
      return false;
    }
  }

  async getStats(collection) {
    const coll = collection || this.defaultCollection;
    const tableName = `vector_store.${coll}`;

    try {
      const countResult = await this.pool.query(`
        SELECT COUNT(*) as total FROM ${tableName}
      `);

      const sizeResult = await this.pool.query(`
        SELECT pg_size_pretty(pg_total_relation_size($1)) as size
      `, [`vector_store.${coll}`]);

      const dimensionResult = await this.pool.query(`
        SELECT vector_dims(embedding) as dimensions
        FROM ${tableName}
        LIMIT 1
      `);

      return {
        collection: coll,
        total_documents: parseInt(countResult.rows[0].total),
        disk_size: sizeResult.rows[0].size,
        dimensions: dimensionResult.rows.length > 0 ? dimensionResult.rows[0].dimensions : null,
        distance_metric: this.defaultDistanceMetric
      };
    } catch (error) {
      return {
        collection: coll,
        error: error.message
      };
    }
  }
}

module.exports = PostgresVectorStore;
