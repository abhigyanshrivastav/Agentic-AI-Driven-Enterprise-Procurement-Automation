import os
import sqlite3
import pytest
from pathlib import Path
from src.config import get_settings, PROJECT_ROOT
from src.observability.validator import validate_and_initialize_environment, PreflightValidationError
from src.tools.db import execute_query, get_db_connection
from src.agent.graph import AgentOrchestrator

def test_canonical_project_root_resolution():
    settings = get_settings()
    assert PROJECT_ROOT.exists()
    assert settings.get_db_path().is_absolute()
    assert settings.get_raw_policies_dir().is_absolute()
    assert settings.get_faiss_metadata_path().is_absolute()
    assert settings.get_eval_dataset_path().is_absolute()

def test_cwd_independent_path_resolution(tmp_path):
    orig_cwd = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        info = validate_and_initialize_environment(auto_init=True)
        assert info["status"] == "VALID"
        assert Path(info["db_path"]).exists()
        assert Path(info["raw_policies_dir"]).exists()
    finally:
        os.chdir(orig_cwd)

def test_required_policy_files_exist():
    settings = get_settings()
    policies_dir = settings.get_raw_policies_dir()
    policy_file = policies_dir / "procurement_policy.md"
    vendor_file = policies_dir / "vendor_sla_terms.md"
    assert policy_file.exists() and policy_file.stat().st_size > 0
    assert vendor_file.exists() and vendor_file.stat().st_size > 0

def test_required_sqlite_tables_and_records():
    settings = get_settings()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert {"inventory", "suppliers", "purchase_orders"}.issubset(tables)

    cursor.execute("SELECT COUNT(*) FROM inventory")
    assert cursor.fetchone()[0] > 0
    cursor.execute("SELECT COUNT(*) FROM suppliers")
    assert cursor.fetchone()[0] > 0
    conn.close()

def test_sqlite_missing_table_error_classification():
    with pytest.raises(PreflightValidationError, match="DATABASE_SCHEMA_ERROR"):
        execute_query("SELECT * FROM non_existent_table_xyz")

def test_e1_rag_zero_context_failure_classification():
    orchestrator = AgentOrchestrator()
    state = orchestrator.run(query="What is the return policy for Apex?", experiment_mode="E1")
    assert len(state["retrieved_doc_ids"]) > 0
    assert state["status"] == "COMPLETED"

def test_e2_tool_database_execution_and_data_verification():
    orchestrator = AgentOrchestrator()
    state = orchestrator.run(query="Check stock quantity and cost for SKU-1001", experiment_mode="E2")
    assert state["status"] == "COMPLETED"
    assert len(state["executed_tool_calls"]) > 0
    assert state["executed_tool_calls"][0]["function"]["name"] == "check_inventory"
    assert state["tool_results"][0]["success"] is True
    assert "SKU-1001" in state["tool_results"][0]["message"]
