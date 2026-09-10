import sqlite3
import json
from pathlib import Path
from typing import Dict, Any
from src.config import get_settings, PROJECT_ROOT
from src.observability import logger

class PreflightValidationError(Exception):
    """Structured preflight environment validation error."""
    def __init__(self, error_type: str, message: str):
        self.error_type = error_type
        self.message = message
        super().__init__(f"[{error_type}] {message}")

def validate_and_initialize_environment(auto_init: bool = True) -> Dict[str, Any]:
    """Preflight validator checking paths, policy documents, SQLite schema/records, and FAISS index."""
    settings = get_settings()
    
    raw_policies_dir = settings.get_raw_policies_dir()
    db_path = settings.get_db_path()
    faiss_index_path = settings.get_faiss_index_path()
    faiss_metadata_path = settings.get_faiss_metadata_path()
    eval_dataset_path = settings.get_eval_dataset_path()

    # 1. Policy Document Validation
    policy_files = [raw_policies_dir / "procurement_policy.md", raw_policies_dir / "vendor_sla_terms.md"]
    policies_valid = raw_policies_dir.exists() and all(f.exists() and f.stat().st_size > 0 for f in policy_files)
    
    if not policies_valid:
        if auto_init:
            logger.info("Policy documents missing. Auto-creating policy files...")
            from scripts.generate_synthetic_data import create_policy_documents
            create_policy_documents()
            policies_valid = raw_policies_dir.exists() and all(f.exists() and f.stat().st_size > 0 for f in policy_files)
        
        if not policies_valid:
            raise PreflightValidationError("DATA_PATH_ERROR", f"Policy documents missing at {raw_policies_dir}")

    # 2. SQLite Database & Schema Validation
    db_valid = False
    if db_path.exists() and db_path.stat().st_size > 0:
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            
            required_tables = {"inventory", "suppliers", "purchase_orders"}
            if required_tables.issubset(tables):
                cursor.execute("SELECT COUNT(*) FROM inventory")
                inv_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM suppliers")
                sup_count = cursor.fetchone()[0]
                if inv_count > 0 and sup_count > 0:
                    db_valid = True
            conn.close()
        except Exception as e:
            logger.warning(f"Database validation check failed: {e}")
            db_valid = False

    if not db_valid:
        if auto_init:
            logger.info("SQLite database missing or schema incomplete. Building synthetic database...")
            from scripts.generate_synthetic_data import create_sqlite_database
            create_sqlite_database()
            
            # Re-verify
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM inventory")
            inv_count = cursor.fetchone()[0]
            conn.close()
            db_valid = (inv_count > 0)

        if not db_valid:
            raise PreflightValidationError("DATABASE_SCHEMA_ERROR", f"SQLite database at {db_path} missing required tables (inventory, suppliers, purchase_orders)")

    # 3. FAISS Vector Store Validation
    faiss_valid = (faiss_metadata_path.exists() and faiss_metadata_path.stat().st_size > 0)
    if faiss_valid:
        with open(faiss_metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            if not metadata or len(metadata) == 0:
                faiss_valid = False

    if not faiss_valid:
        if auto_init:
            logger.info("FAISS vector index missing or empty. Building FAISS index from policy documents...")
            from src.rag.indexer import FAISSIndexer
            from src.llm.embeddings import EmbeddingClient
            indexer = FAISSIndexer(index_dir=str(faiss_metadata_path.parent))
            indexer.build_index_from_documents(docs_dir=str(raw_policies_dir), embedding_fn=EmbeddingClient().get_embeddings)
            faiss_valid = faiss_metadata_path.exists() and faiss_metadata_path.stat().st_size > 0

        if not faiss_valid:
            raise PreflightValidationError("RAG_INDEX_ERROR", f"FAISS index or metadata at {faiss_metadata_path} missing or empty.")

    # 4. Evaluation Dataset Validation
    if not eval_dataset_path.exists() or eval_dataset_path.stat().st_size == 0:
        if auto_init:
            logger.info("Evaluation dataset missing. Regenerating eval_dataset.json...")
            from scripts.generate_synthetic_data import create_eval_dataset
            create_eval_dataset()

        if not eval_dataset_path.exists():
            raise PreflightValidationError("DATA_PATH_ERROR", f"Evaluation dataset missing at {eval_dataset_path}")

    return {
        "status": "VALID",
        "project_root": str(PROJECT_ROOT),
        "raw_policies_dir": str(raw_policies_dir),
        "db_path": str(db_path),
        "faiss_metadata_path": str(faiss_metadata_path),
        "eval_dataset_path": str(eval_dataset_path)
    }
