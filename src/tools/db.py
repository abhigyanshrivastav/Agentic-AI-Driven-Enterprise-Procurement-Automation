import sqlite3
from pathlib import Path
from typing import Any, List, Dict, Tuple
from src.config import get_settings
from src.observability.validator import validate_and_initialize_environment, PreflightValidationError

def get_db_connection() -> sqlite3.Connection:
    settings = get_settings()
    db_path = settings.get_db_path()

    # Preflight check and schema verification
    if not db_path.exists() or db_path.stat().st_size == 0:
        validate_and_initialize_environment(auto_init=True)
        
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        conn.close()
        return results
    except sqlite3.OperationalError as e:
        raise PreflightValidationError("DATABASE_SCHEMA_ERROR", f"SQLite query execution failed: {e}")

def execute_statement(sql: str, params: Tuple = ()) -> int:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected
    except sqlite3.OperationalError as e:
        raise PreflightValidationError("DATABASE_SCHEMA_ERROR", f"SQLite statement execution failed: {e}")
