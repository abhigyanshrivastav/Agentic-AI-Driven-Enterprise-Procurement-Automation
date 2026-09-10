import random
from locust import HttpUser, task, between

QUERIES = [
    {"query": "What is the spending limit for Level 1 procurement agents?", "mode": "E0"},
    {"query": "What is the return policy window for Apex Office Logistics?", "mode": "E1"},
    {"query": "Check current inventory stock level for SKU-1001.", "mode": "E2"},
    {"query": "Create a purchase order for 2 units of SKU-1002 from supplier SUP-102.", "mode": "E3"},
    {"query": "Create a purchase order for 50 units of SKU-1001 (unit price $870.00) from SUP-101 as procurement_agent.", "mode": "E3"}
]

class ProcurementAgentUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def query_endpoint(self):
        item = random.choice(QUERIES)
        payload = {
            "query": item["query"],
            "experiment_mode": item["mode"],
            "user_role": "procurement_agent"
        }
        self.client.post("/api/v1/query", json=payload, headers={"Content-Type": "application/json"})
