const PostgresVectorStore = require('./postgres-vector-store');
const ChromaVectorStore = require('./chroma-vector-store');

/**
 * Factory for creating vector store instances
 * Supports: postgres, chroma
 *
 * Usage:
 *   const store = VectorStoreFactory.create('postgres', { host: 'laptop-01' });
 *   await store.initialize();
 *   await store.addDocument({ id: '1', embedding: [...], document: 'text' });
 */
class VectorStoreFactory {
  static STORE_TYPES = {
    POSTGRES: 'postgres',
    CHROMA: 'chroma'
  };

  static DEFAULT_CONFIGS = {
    postgres: {
      host: 'laptop-01',
      user: 'sfloess',
      database: 'learning',
      defaultCollection: 'documents',
      dimensions: 384,
      distanceMetric: 'cosine',
      poolSize: 20
    },
    chroma: {
      url: 'http://localhost:8000',
      defaultCollection: 'documents'
    }
  };

  /**
   * Create a vector store instance
   * @param {string} type - Store type ('postgres' or 'chroma')
   * @param {Object} config - Configuration object (merged with defaults)
   * @returns {VectorStoreBase} - Initialized store instance
   */
  static create(type, config = {}) {
    const normalizedType = type.toLowerCase();

    if (!Object.values(VectorStoreFactory.STORE_TYPES).includes(normalizedType)) {
      throw new Error(
        `Unknown vector store type: ${type}. ` +
        `Supported types: ${Object.values(VectorStoreFactory.STORE_TYPES).join(', ')}`
      );
    }

    const defaultConfig = VectorStoreFactory.DEFAULT_CONFIGS[normalizedType] || {};
    const mergedConfig = { ...defaultConfig, ...config };

    switch (normalizedType) {
      case VectorStoreFactory.STORE_TYPES.POSTGRES:
        return new PostgresVectorStore(mergedConfig);

      case VectorStoreFactory.STORE_TYPES.CHROMA:
        return new ChromaVectorStore(mergedConfig);

      default:
        throw new Error(`Store type ${type} not implemented`);
    }
  }

  /**
   * Create store from environment variable
   * Reads VECTOR_STORE env var (default: postgres)
   * @param {Object} configOverrides - Config overrides
   * @returns {VectorStoreBase}
   */
  static createFromEnv(configOverrides = {}) {
    const storeType = process.env.VECTOR_STORE || VectorStoreFactory.STORE_TYPES.POSTGRES;
    return VectorStoreFactory.create(storeType, configOverrides);
  }

  /**
   * Auto-select best available store
   * Tries postgres first (faster), falls back to chroma
   * @param {Object} config - Config object
   * @returns {Promise<VectorStoreBase>} - Initialized store
   */
  static async createBestAvailable(config = {}) {
    const stores = [
      { type: VectorStoreFactory.STORE_TYPES.POSTGRES, priority: 1 },
      { type: VectorStoreFactory.STORE_TYPES.CHROMA, priority: 2 }
    ];

    for (const { type } of stores.sort((a, b) => a.priority - b.priority)) {
      try {
        const store = VectorStoreFactory.create(type, config);
        await store.initialize();

        const healthy = await store.healthCheck();
        if (healthy) {
          return store;
        }

        await store.close();
      } catch (error) {
        continue;
      }
    }

    throw new Error('No vector store available. Install postgres+pgvector or chromadb.');
  }

  /**
   * Create multiple stores (for redundancy/benchmarking)
   * @param {Array<{type: string, config: Object}>} specs - Store specifications
   * @returns {Promise<Array<VectorStoreBase>>} - Array of initialized stores
   */
  static async createMultiple(specs) {
    const stores = [];
    const errors = [];

    for (const spec of specs) {
      try {
        const store = VectorStoreFactory.create(spec.type, spec.config);
        await store.initialize();
        stores.push(store);
      } catch (error) {
        errors.push({ type: spec.type, error: error.message });
      }
    }

    if (stores.length === 0) {
      throw new Error(
        `Failed to create any stores:\n${errors.map(e => `- ${e.type}: ${e.error}`).join('\n')}`
      );
    }

    return stores;
  }

  /**
   * Benchmark store performance
   * @param {VectorStoreBase} store - Store to benchmark
   * @param {Object} options - Benchmark options
   * @returns {Promise<Object>} - Benchmark results
   */
  static async benchmark(store, options = {}) {
    const {
      numDocs = 100,
      dimensions = 384,
      queryRuns = 10
    } = options;

    if (!store.initialized) {
      await store.initialize();
    }

    const collection = `benchmark_${Date.now()}`;
    await store.createCollection(collection, { dimensions });

    const results = {
      insert: { times: [], avgMs: 0 },
      query: { times: [], avgMs: 0 },
      getById: { times: [], avgMs: 0 }
    };

    try {
      const documents = [];
      for (let i = 0; i < numDocs; i++) {
        documents.push({
          id: `doc_${i}`,
          embedding: Array.from({ length: dimensions }, () => Math.random()),
          metadata: { index: i, type: 'benchmark' },
          document: `Benchmark document ${i}`
        });
      }

      const insertStart = Date.now();
      await store.addDocuments(documents, collection);
      const insertTime = Date.now() - insertStart;
      results.insert.times.push(insertTime);
      results.insert.avgMs = insertTime / numDocs;

      const queryEmbedding = Array.from({ length: dimensions }, () => Math.random());
      for (let i = 0; i < queryRuns; i++) {
        const queryStart = Date.now();
        await store.query({ embedding: queryEmbedding, limit: 10, collection });
        const queryTime = Date.now() - queryStart;
        results.query.times.push(queryTime);
      }
      results.query.avgMs = results.query.times.reduce((a, b) => a + b, 0) / queryRuns;

      for (let i = 0; i < queryRuns; i++) {
        const getStart = Date.now();
        await store.getById(`doc_${i % numDocs}`, collection);
        const getTime = Date.now() - getStart;
        results.getById.times.push(getTime);
      }
      results.getById.avgMs = results.getById.times.reduce((a, b) => a + b, 0) / queryRuns;

    } finally {
      await store.deleteCollection(collection);
    }

    return results;
  }

  /**
   * Compare multiple stores
   * @param {Array<string>} storeTypes - Store types to compare
   * @param {Object} benchmarkOptions - Benchmark options
   * @returns {Promise<Object>} - Comparison results
   */
  static async compareStores(storeTypes, benchmarkOptions = {}) {
    const comparisons = {};

    for (const type of storeTypes) {
      try {
        const store = VectorStoreFactory.create(type);
        await store.initialize();

        const healthy = await store.healthCheck();
        if (!healthy) {
          comparisons[type] = { error: 'Health check failed' };
          await store.close();
          continue;
        }

        comparisons[type] = await VectorStoreFactory.benchmark(store, benchmarkOptions);
        await store.close();
      } catch (error) {
        comparisons[type] = { error: error.message };
      }
    }

    return comparisons;
  }
}

module.exports = VectorStoreFactory;
