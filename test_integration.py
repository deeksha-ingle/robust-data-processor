import pytest
import requests
import os
import time
import json
from google.cloud import firestore
from google.cloud import pubsub_v1

# Only run if integration flag is set or env vars are present indicating local dev environment
# For simplicity, we'll assume this runs against the local setup started by run_local.sh

API_URL = "http://localhost:8080"
WORKER_URL = "http://localhost:8081" # Not used directly, but good to know
PROJECT_ID = os.getenv("GCP_PROJECT", "test-project")

@pytest.mark.integration
def test_end_to_end_flow():
    """
    Sends a request to API and checks Firestore for the result.
    Requires local services to be running.
    """
    # Skip if services aren't running (simple check)
    try:
        requests.get(f"{API_URL}/")
    except requests.exceptions.ConnectionError:
        pytest.skip("Local API service not running")

    tenant_id = "integration-test-tenant"
    log_id = f"int-test-{int(time.time())}"
    text = "Integration test message 555-0199"
    
    # 1. Send Request to API
    payload = {
        "tenant_id": tenant_id,
        "log_id": log_id,
        "text": text
    }
    response = requests.post(f"{API_URL}/ingest", json=payload)
    assert response.status_code == 202
    
    # 2. Wait for Worker to Process (Poll Firestore)
    # Connect to Firestore (Emulator should be set in env)
    db = firestore.Client(project=PROJECT_ID)
    doc_ref = db.collection("tenants").document(tenant_id).collection("processed_logs").document(log_id)
    
    max_retries = 10
    for i in range(max_retries):
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            assert data["original_text"] == text
            assert data["modified_data"] == "Integration test message [REDACTED]"
            print(f"Integration test passed for {log_id}")
            return
        time.sleep(1)
        
    pytest.fail(f"Document {log_id} not found in Firestore after {max_retries} seconds")
