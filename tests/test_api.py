import pytest
from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_query_endpoint_e0():
    payload = {
        "query": "What is the spending limit for procurement agents?",
        "experiment_mode": "E0",
        "user_role": "procurement_agent"
    }
    response = client.post("/api/v1/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["experiment_mode"] == "E0"
    assert data["status"] == "COMPLETED"
    assert "metrics" in data
