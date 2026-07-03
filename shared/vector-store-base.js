/**
 * Abstract base class for vector store implementations
 * Defines the interface that all vector stores must implement
 */
class VectorStoreBase {
  constructor(config = {}) {
    if (new.target === VectorStoreBase) {
      throw new Error('VectorStoreBase is abstract and cannot be instantiated directly');
    }
    this.config = config;
    this.initialized = false;
  }

  /**
   * Initialize the vector store (connect, create tables/collections, etc.)
   * @returns {Promise<void>}
   */
  async initialize() {
    throw new Error('initialize() must be implemented by subclass');
  }

  /**
   * Close/cleanup resources
   * @returns {Promise<void>}
   */
  async close() {
    throw new Error('close() must be implemented by subclass');
  }

  /**
   * Add a single document with embedding
   * @param {Object} params
   * @param {string} params.id - Unique document ID
   * @param {Array<number>} params.embedding - Vector embedding
   * @param {Object} params.metadata - Document metadata
   * @param {string} params.document - Document content
   * @param {string} [params.collection] - Collection/table name
   * @returns {Promise<string>} - Document ID
   */
  async addDocument({ id, embedding, metadata, document, collection }) {
    throw new Error('addDocument() must be implemented by subclass');
  }

  /**
   * Add multiple documents with embeddings (batch operation)
   * @param {Array<Object>} documents - Array of document objects
   * @param {string} [collection] - Collection/table name
   * @returns {Promise<Array<string>>} - Array of document IDs
   */
  async addDocuments(documents, collection) {
    throw new Error('addDocuments() must be implemented by subclass');
  }

  /**
   * Query by vector similarity
   * @param {Object} params
   * @param {Array<number>} params.embedding - Query vector
   * @param {number} [params.limit=10] - Max results to return
   * @param {Object} [params.filter] - Metadata filters
   * @param {string} [params.collection] - Collection/table name
   * @returns {Promise<Array<Object>>} - Array of {id, embedding, metadata, document, distance}
   */
  async query({ embedding, limit = 10, filter, collection }) {
    throw new Error('query() must be implemented by subclass');
  }

  /**
   * Get document by ID
   * @param {string} id - Document ID
   * @param {string} [collection] - Collection/table name
   * @returns {Promise<Object|null>} - Document or null if not found
   */
  async getById(id, collection) {
    throw new Error('getById() must be implemented by subclass');
  }

  /**
   * Update document metadata
   * @param {string} id - Document ID
   * @param {Object} metadata - New metadata (merged with existing)
   * @param {string} [collection] - Collection/table name
   * @returns {Promise<boolean>} - Success status
   */
  async updateMetadata(id, metadata, collection) {
    throw new Error('updateMetadata() must be implemented by subclass');
  }

  /**
   * Delete document by ID
   * @param {string} id - Document ID
   * @param {string} [collection] - Collection/table name
   * @returns {Promise<boolean>} - Success status
   */
  async deleteById(id, collection) {
    throw new Error('deleteById() must be implemented by subclass');
  }

  /**
   * Delete all documents matching filter
   * @param {Object} filter - Metadata filters
   * @param {string} [collection] - Collection/table name
   * @returns {Promise<number>} - Number of documents deleted
   */
  async deleteByFilter(filter, collection) {
    throw new Error('deleteByFilter() must be implemented by subclass');
  }

  /**
   * Count documents in collection
   * @param {Object} [filter] - Optional metadata filters
   * @param {string} [collection] - Collection/table name
   * @returns {Promise<number>} - Document count
   */
  async count(filter, collection) {
    throw new Error('count() must be implemented by subclass');
  }

  /**
   * List all collections
   * @returns {Promise<Array<string>>} - Collection names
   */
  async listCollections() {
    throw new Error('listCollections() must be implemented by subclass');
  }

  /**
   * Create a new collection
   * @param {string} name - Collection name
   * @param {Object} [options] - Collection options (dimensions, distance metric, etc.)
   * @returns {Promise<void>}
   */
  async createCollection(name, options) {
    throw new Error('createCollection() must be implemented by subclass');
  }

  /**
   * Delete a collection
   * @param {string} name - Collection name
   * @returns {Promise<boolean>} - Success status
   */
  async deleteCollection(name) {
    throw new Error('deleteCollection() must be implemented by subclass');
  }

  /**
   * Health check
   * @returns {Promise<boolean>} - True if store is healthy
   */
  async healthCheck() {
    throw new Error('healthCheck() must be implemented by subclass');
  }

  /**
   * Get store statistics
   * @param {string} [collection] - Collection name
   * @returns {Promise<Object>} - Statistics object
   */
  async getStats(collection) {
    throw new Error('getStats() must be implemented by subclass');
  }
}

module.exports = VectorStoreBase;
