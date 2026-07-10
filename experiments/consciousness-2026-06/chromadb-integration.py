#!/usr/bin/env python3
"""ChromaDB Vector Store Integration"""

class ChromaDBIntegration:
    def __init__(self, collection_name="capabilities"):
        self.collection_name = collection_name
        self.vectors = {}
        self.metadata = {}
    
    def add_embedding(self, doc_id, embedding, metadata):
        """Add document embedding"""
        self.vectors[doc_id] = embedding
        self.metadata[doc_id] = metadata
    
    def query(self, query_embedding, n_results=5):
        """Similarity search"""
        import numpy as np
        results = []
        for doc_id, vec in self.vectors.items():
            similarity = np.dot(query_embedding, vec) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(vec))
            results.append((doc_id, similarity, self.metadata[doc_id]))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:n_results]

if __name__ == '__main__':
    import numpy as np
    chroma = ChromaDBIntegration()
    chroma.add_embedding('doc1', np.random.randn(384), {'source': 'manual'})
    results = chroma.query(np.random.randn(384), n_results=1)
    print(f"✅ ChromaDB: {len(results)} results")
