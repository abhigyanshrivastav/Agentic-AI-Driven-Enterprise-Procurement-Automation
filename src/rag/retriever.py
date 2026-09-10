import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from pydantic import BaseModel

try:
    import faiss
except ImportError:
    faiss = None

from src.config import get_settings
from src.llm.embeddings import EmbeddingClient
from src.observability import logger

class DocumentChunk(BaseModel):
    chunk_id: str
    content: str
    doc_id: str
    file_name: str
    score: float

class FAISSRetriever:
    """Retriever for performing vector similarity search over indexed policy documents."""

    def __init__(self, index_dir: Optional[str] = None, embedding_client: Optional[EmbeddingClient] = None):
        settings = get_settings()
        if index_dir:
            p = Path(index_dir)
            self.index_dir = p if p.is_absolute() else settings.get_faiss_metadata_path().parent
        else:
            self.index_dir = settings.get_faiss_metadata_path().parent

        self.index_file = self.index_dir / "index.faiss"
        self.metadata_file = self.index_dir / "metadata.json"
        self.embedding_client = embedding_client or EmbeddingClient()
        
        self.metadata: List[Dict[str, Any]] = []
        self.index = None
        self.numpy_embeddings = None
        self._load_index()

    def _load_index(self):
        if self.metadata_file.exists():
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)

        if faiss is not None and self.index_file.exists():
            self.index = faiss.read_index(str(self.index_file))
        elif Path(str(self.index_file) + ".npy").exists():
            self.numpy_embeddings = np.load(str(self.index_file) + ".npy")

    def retrieve(self, query: str, top_k: int = 3) -> List[DocumentChunk]:
        settings = get_settings()
        if not self.metadata or (self.index is None and self.numpy_embeddings is None and not self.metadata):
            logger.warning("No FAISS metadata found. Auto-building index...")
            from src.rag.indexer import FAISSIndexer
            indexer = FAISSIndexer(index_dir=str(self.index_dir))
            indexer.build_index_from_documents(docs_dir=str(settings.get_raw_policies_dir()), embedding_fn=self.embedding_client.get_embeddings)
            self._load_index()

        if not self.metadata:
            return []

        # Get query embedding
        query_vecs = self.embedding_client.get_embeddings([query])
        if not query_vecs:
            return []
        
        query_np = np.array(query_vecs, dtype=np.float32)
        query_dim = query_np.shape[1]

        # Check dimension mismatch against loaded index/embeddings
        index_dim = None
        if self.index is not None:
            index_dim = self.index.d
        elif self.numpy_embeddings is not None:
            index_dim = self.numpy_embeddings.shape[1]

        if index_dim is not None and index_dim != query_dim:
            logger.warning(f"FAISS index dimension mismatch (index: {index_dim}, query: {query_dim}). Auto-rebuilding index...")
            from src.rag.indexer import FAISSIndexer
            indexer = FAISSIndexer(index_dir=str(self.index_dir))
            indexer.build_index_from_documents(docs_dir=str(settings.get_raw_policies_dir()), embedding_fn=self.embedding_client.get_embeddings)
            self._load_index()

        top_k = min(top_k, len(self.metadata))
        results: List[DocumentChunk] = []

        if self.index is not None:
            distances, indices = self.index.search(query_np, top_k)
            for dist, idx in zip(distances[0], indices[0]):
                if idx < len(self.metadata) and idx >= 0:
                    meta = self.metadata[idx]
                    results.append(DocumentChunk(
                        chunk_id=f"{meta.get('doc_id')}_{meta.get('chunk_index')}",
                        content=meta.get("content", ""),
                        doc_id=meta.get("doc_id", ""),
                        file_name=meta.get("file_name", ""),
                        score=float(dist)
                    ))
        elif self.numpy_embeddings is not None:
            diffs = self.numpy_embeddings - query_np[0]
            dists = np.linalg.norm(diffs, axis=1)
            top_indices = np.argsort(dists)[:top_k]
            for idx in top_indices:
                meta = self.metadata[idx]
                results.append(DocumentChunk(
                    chunk_id=f"{meta.get('doc_id')}_{meta.get('chunk_index')}",
                    content=meta.get("content", ""),
                    doc_id=meta.get("doc_id", ""),
                    file_name=meta.get("file_name", ""),
                    score=float(dists[idx])
                ))
        else:
            for idx, meta in enumerate(self.metadata[:top_k]):
                results.append(DocumentChunk(
                    chunk_id=f"{meta.get('doc_id')}_{idx}",
                    content=meta.get("content", ""),
                    doc_id=meta.get("doc_id", ""),
                    file_name=meta.get("file_name", ""),
                    score=1.0
                ))

        return results
