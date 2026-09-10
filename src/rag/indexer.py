import os
import json
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

try:
    import faiss
except ImportError:
    faiss = None

from src.config import get_settings
from src.observability import logger

def simple_chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    """Simple character/word chunking utility for text documents."""
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end]
        chunks.append(chunk.strip())
        if end == text_len:
            break
        start += (chunk_size - chunk_overlap)
        
    return [c for c in chunks if c]

class FAISSIndexer:
    """Builds and manages the FAISS vector index over synthetic policy documents."""

    def __init__(self, index_dir: Optional[str] = None):
        settings = get_settings()
        if index_dir:
            p = Path(index_dir)
            self.index_dir = p if p.is_absolute() else (settings.get_faiss_metadata_path().parent)
        else:
            self.index_dir = settings.get_faiss_metadata_path().parent

        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.index_dir / "index.faiss"
        self.metadata_file = self.index_dir / "metadata.json"
        
    def build_index_from_documents(self, docs_dir: Optional[str] = None, embedding_fn=None) -> Dict[str, Any]:
        settings = get_settings()
        if docs_dir:
            p = Path(docs_dir)
            docs_path = p if p.is_absolute() else settings.get_raw_policies_dir()
        else:
            docs_path = settings.get_raw_policies_dir()

        all_chunks = []
        metadata = []
        
        if not docs_path.exists():
            logger.error(f"Documents directory {docs_path} does not exist.")
            return {"status": "ERROR", "chunks_indexed": 0}

        for file_path in docs_path.glob("*.md"):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                chunks = simple_chunk_text(content)
                for idx, chunk in enumerate(chunks):
                    all_chunks.append(chunk)
                    metadata.append({
                        "doc_id": file_path.stem,
                        "file_name": file_path.name,
                        "chunk_index": idx,
                        "content": chunk
                    })

        if not all_chunks:
            logger.warning("No document chunks found to index.")
            return {"status": "EMPTY", "chunks_indexed": 0}

        # Generate embeddings
        if embedding_fn:
            embeddings = embedding_fn(all_chunks)
        else:
            embeddings = self._generate_deterministic_embeddings(all_chunks)

        embeddings_np = np.array(embeddings, dtype=np.float32)
        dimension = embeddings_np.shape[1]

        if faiss is not None:
            index = faiss.IndexFlatL2(dimension)
            index.add(embeddings_np)
            faiss.write_index(index, str(self.index_file))
        else:
            np.save(str(self.index_file) + ".npy", embeddings_np)

        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Successfully indexed {len(all_chunks)} chunks into FAISS index at {self.index_dir}")
        return {"status": "SUCCESS", "chunks_indexed": len(all_chunks), "dimension": dimension}

    def _generate_deterministic_embeddings(self, texts: List[str], dim: int = 1536) -> List[List[float]]:
        """Generates deterministic synthetic float vectors for testing vector search offline."""
        embeddings = []
        for text in texts:
            seed = sum(ord(c) for c in text) % 10000
            rng = np.random.RandomState(seed)
            vec = rng.randn(dim)
            norm = np.linalg.norm(vec)
            vec = vec / norm if norm > 0 else vec
            embeddings.append(vec.tolist())
        return embeddings
