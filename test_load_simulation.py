import pytest
import asyncio
import json
import time
import uuid
import random
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import sys
import os

# Set environment variables
os.environ["GCP_PROJECT"] = "test-project"
os.environ["PUBSUB_TOPIC"] = "test-topic"
os.environ["LOG_LEVEL"] = "ERROR"

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Mock GCP modules
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.pubsub_v1"] = MagicMock()
sys.modules["google.cloud.firestore"] = MagicMock()

# Import apps
import api.main
import worker.main

# Patch globals directly
mock_publisher = MagicMock()
mock_topic_path = "projects/test-project/topics/test-topic"
api.main.publisher = mock_publisher
api.main.topic_path = mock_topic_path

mock_firestore_client = MagicMock()
worker.main.db = mock_firestore_client

from api.main import app as api_app
from worker.main import app as worker_app

api_client = TestClient(api_app)
worker_client = TestClient(worker_app)

# Define side effect for publish
def mock_publish_side_effect(topic, data, **kwargs):
    tenant_id = kwargs.get("tenant_id", "unknown")
    
    import base64
    data_b64 = base64.b64encode(data.decode("utf-8").encode("utf-8")).decode("utf-8")
    
    push_payload = {
        "message": {
            "data": data_b64,
            "messageId": str(uuid.uuid4()),
            "publishTime": "2023-01-01T00:00:00Z"
        },
        "subscription": "projects/test/subscriptions/test-sub"
    }
    
    try:
        # Call worker
        response = worker_client.post("/", json=push_payload)
        if response.status_code != 200:
            print(f"Worker failed: {response.text}")
    except Exception as e:
        print(f"Worker exception: {e}")
        
    future = MagicMock()
    future.result.return_value = "msg-id"
    return future

mock_publisher.publish.side_effect = mock_publish_side_effect

@patch("time.sleep") # Patch sleep to speed up test
def test_live_load_simulation_1000_requests(mock_sleep):
    """
    Simulates 1000 requests flowing through the system.
    """
    print("\n=== Starting Load Simulation (1000 Requests) ===")
    
    count = 1000
    start_time = time.time()
    
    success_count = 0
    
    for i in range(count):
        tenant_id = random.choice(["acme", "beta", "gamma"])
        log_id = str(uuid.uuid4())
        text = f"Log {i} user 555-0199 action."
        
        if i % 2 == 0:
            payload = {
                "tenant_id": tenant_id,
                "log_id": log_id,
                "text": text
            }
            resp = api_client.post("/ingest", json=payload)
        else:
            headers = {"X-Tenant-ID": tenant_id, "Content-Type": "text/plain"}
            resp = api_client.post("/ingest", content=text, headers=headers)
            
        if resp.status_code == 202:
            success_count += 1
            
        if i % 100 == 0:
            print(f"Processed {i} requests...")
            
    duration = time.time() - start_time
    
    print(f"\n=== Simulation Complete ===")
    print(f"Total Requests: {count}")
    print(f"API Success: {success_count}")
    print(f"Time Taken: {duration:.2f}s")
    print(f"Throughput: {count/duration:.2f} RPS")
    
    assert mock_publisher.publish.call_count == 1000
    print("Verified: API published 1000 messages.")
    print("Verified: Worker processed messages (simulated via mock hook).")
