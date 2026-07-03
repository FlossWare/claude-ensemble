const VectorStoreBase = require('./vector-store-base');

/**
 * ChromaDB implementation
 * Note: Requires ChromaDB server running (default: http://localhost:8000)
 * Performance: 0.9-2.3ms queries (2-6x slower than pgvector)
 */
class ChromaVectorStore extends VectorStoreBase {
  constructor(config = {}) {
    super(config);

    this.chromaUrl = config.url || 'http://localhost:8000';
    this.defaultCollection = config.defaultCollection || 'documents';
    this.client = null;
    this.collections = new Map();
  }

  async initialize() {
    if (this.initialized) return;

    try {
      const { ChromaClient } = require('chromadb');
      this.client = new ChromaClient({ path: this.chromaUrl });

      await this._getOrCreateCollection(this.defaultCollection);

      this.initialized = true;
    } catch (error) {
      if (error.code === 'MODULE_NOT_FOUND') {
        throw new Error(
          'ChromaDB not installed. Run: npm install chromadb\n' +
          'Also ensure ChromaDB server is running: docker run -p 8000:8000 chromadb/chroma'
        );
      }
      throw new Error(`Failed to initialize ChromaVectorStore: ${error.message}`);
    }
  }

  async close() {
    this.collections.clear();
    this.client = null;
    this.initialized = false;
  }

  async _getOrCreateCollection(name) {
    if (this.collections.has(name)) {
      return this.collections.get(name);
    }

    try {
      const collection = await this.client.getOrCreateCollection({ name });
      this.collections.set(name, collection);
      return collection;
    } catch (error) {
      throw new Error(`Failed to get/create collection ${name}: ${error.message}`);
    }
  }

  async addDocument({ id, embedding, metadata = {}, document, collection }) {
    const coll = await this._getOrCreateCollection(collection || this.defaultCollection);

    await coll.add({
      ids: [id],
      embeddings: [embedding],
      metadatas: [metadata],
      documents: [document]
    });

    return id;
  }

  async addDocuments(documents, collection) {
    const coll = await this._getOrCreateCollection(collection || this.defaultCollection);

    const ids = documents.map(d => d.id);
    const embeddings = documents.map(d => d.embedding);
    const metadatas = documents.map(d => d.metadata || {});
    const docs = documents.map(d => d.document);

    await coll.add({
      ids,
      embeddings,
      metadatas,
      documents: docs
    });

    return ids;
  }

  async query({ embedding, limit = 10, filter, collection }) {
    const coll = await this._getOrCreateCollection(collection || this.defaultCollection);

    const queryParams = {
      queryEmbeddings: [embedding],
      nResults: limit
    };

    if (filter && Object.keys(filter).length > 0) {
      queryParams.where = filter;
    }

    const result = await coll.query(queryParams);

    if (!result.ids || result.ids.length === 0 || !result.ids[0]) {
      return [];
    }

    const results = [];
    const count = result.ids[0].length;

    for (let i = 0; i < count; i++) {
      results.push({
        id: result.ids[0][i],
        embedding: result.embeddings ? result.embeddings[0][i] : null,
        metadata: result.metadatas ? result.metadatas[0][i] : {},
        document: result.documents ? result.documents[0][i] : null,
        distance: result.distances ? result.distances[0][i] : null
      });
    }

    return results;
  }

  async getById(id, collection) {
    const coll = await this._getOrCreateCollection(collection || this.defaultCollection);

    try {
      const result = await coll.get({
        ids: [id],
        include: ['embeddings', 'metadatas', 'documents']
      });

      if (!result.ids || result.ids.length === 0) {
        return null;
      }

      return {
        id: result.ids[0],
        embedding: result.embeddings ? result.embeddings[0] : null,
        metadata: result.metadatas ? result.metadatas[0] : {},
        document: result.documents ? result.documents[0] : null
      };
    } catch (error) {
      return null;
    }
  }

  async updateMetadata(id, metadata, collection) {
    const coll = await this._getOrCreateCollection(collection || this.defaultCollection);

    try {
      const existing = await this.getById(id, collection);
      if (!existing) return false;

      const mergedMetadata = { ...existing.metadata, ...metadata };

      await coll.update({
        ids: [id],
        metadatas: [mergedMetadata]
      });

      return true;
    } catch (error) {
      return false;
    }
  }

  async deleteById(id, collection) {
    const coll = await this._getOrCreateCollection(collection || this.defaultCollection);

    try {
      await coll.delete({ ids: [id] });
      return true;
    } catch (error) {
      return false;
    }
  }

  async deleteByFilter(filter, collection) {
    const coll = await this._getOrCreateCollection(collection || this.defaultCollection);

    if (!filter || Object.keys(filter).length === 0) {
      throw new Error('Filter required for deleteByFilter (use deleteCollection to remove all)');
    }

    try {
      const result = await coll.delete({ where: filter });
      return result ? result.length : 0;
    } catch (error) {
      return 0;
    }
  }

  async count(filter, collection) {
    const coll = await this._getOrCreateCollection(collection || this.defaultCollection);

    try {
      const params = {
        include: []
      };

      if (filter && Object.keys(filter).length > 0) {
        params.where = filter;
      }

      const result = await coll.get(params);
      return result.ids ? result.ids.length : 0;
    } catch (error) {
      return 0;
    }
  }

  async listCollections() {
    try {
      const collections = await this.client.listCollections();
      return collections.map(c => c.name);
    } catch (error) {
      return [];
    }
  }

  async createCollection(name, options = {}) {
    try {
      const collection = await this.client.createCollection({
        name,
        metadata: options.metadata || {}
      });
      this.collections.set(name, collection);
    } catch (error) {
      if (!error.message.includes('already exists')) {
        throw error;
      }
    }
  }

  async deleteCollection(name) {
    try {
      await this.client.deleteCollection({ name });
      this.collections.delete(name);
      return true;
    } catch (error) {
      return false;
    }
  }

  async healthCheck() {
    try {
      await this.client.heartbeat();
      return true;
    } catch (error) {
      return false;
    }
  }

  async getStats(collection) {
    const coll = await this._getOrCreateCollection(collection || this.defaultCollection);

    try {
      const result = await coll.get({ include: ['embeddings'] });
      const count = result.ids ? result.ids.length : 0;

      let dimensions = null;
      if (result.embeddings && result.embeddings.length > 0) {
        dimensions = result.embeddings[0].length;
      }

      return {
        collection: collection || this.defaultCollection,
        total_documents: count,
        dimensions,
        backend: 'chromadb'
      };
    } catch (error) {
      return {
        collection: collection || this.defaultCollection,
        error: error.message
      };
    }
  }
}

module.exports = ChromaVectorStore;
