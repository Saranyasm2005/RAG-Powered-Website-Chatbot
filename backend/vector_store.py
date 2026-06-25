import os
import json
import numpy as np
from typing import List, Dict, Any, Tuple

class VectorStore:
    def __init__(self):
        self.metadata: List[Dict[str, Any]] = []
        self.embeddings: np.ndarray = np.empty((0, 0))

    def add_chunks(self, chunks: List[Dict[str, Any]], embeddings_list: List[List[float]]):
        if not chunks or not embeddings_list:
            return

        new_embeddings = np.array(embeddings_list, dtype=np.float32)

        if self.embeddings.size == 0:
            self.embeddings = new_embeddings
        else:
            # Ensure dimensions match
            if self.embeddings.shape[1] != new_embeddings.shape[1]:
                raise ValueError("Embedding dimension mismatch.")
            self.embeddings = np.vstack([self.embeddings, new_embeddings])

        self.metadata.extend(chunks)

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        if self.embeddings.size == 0:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        
        # Calculate cosine similarity: (A . B) / (||A|| * ||B||)
        dot_products = np.dot(self.embeddings, q_vec)
        norms_embeddings = np.linalg.norm(self.embeddings, axis=1)
        norm_query = np.linalg.norm(q_vec)

        # Avoid division by zero
        norms_embeddings[norms_embeddings == 0] = 1e-10
        if norm_query == 0:
            norm_query = 1e-10

        similarities = dot_products / (norms_embeddings * norm_query)

        # Get top K indices sorted descending
        top_k = min(top_k, len(similarities))
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            results.append((self.metadata[idx], float(similarities[idx])))

        return results

    def save(self, data_dir: str):
        os.makedirs(data_dir, exist_ok=True)
        
        # Save metadata
        metadata_path = os.path.join(data_dir, "vector_store.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

        # Save embeddings NumPy array
        embeddings_path = os.path.join(data_dir, "embeddings.npy")
        np.save(embeddings_path, self.embeddings)

    def load(self, data_dir: str):
        metadata_path = os.path.join(data_dir, "vector_store.json")
        embeddings_path = os.path.join(data_dir, "embeddings.npy")

        if os.path.exists(metadata_path) and os.path.exists(embeddings_path):
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                self.embeddings = np.load(embeddings_path)
            except Exception as e:
                print(f"Error loading vector store: {e}")
                self.metadata = []
                self.embeddings = np.empty((0, 0))
        else:
            self.metadata = []
            self.embeddings = np.empty((0, 0))

    def clear(self):
        self.metadata = []
        self.embeddings = np.empty((0, 0))

    def get_document_count(self) -> int:
        unique_urls = set(item.get("url") for item in self.metadata if "url" in item)
        return len(unique_urls)

    def get_chunk_count(self) -> int:
        return len(self.metadata)
