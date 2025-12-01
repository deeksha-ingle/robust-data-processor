import pytest
from unittest.mock import MagicMock, patch
import sys
import os
import json
import base64

# Mock google.cloud.firestore before importing main
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.firestore"] = MagicMock()

# Add worker directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'worker'))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@pytest.fixture
def mock_firestore():
    with patch("main.db") as mock:
        yield mock

def create_pubsub_message(data: dict) -> dict:
    data_str = json.dumps(data)
    data_b64 = base64.b64encode(data_str.encode("utf-8")).decode("utf-8")
    return {
        "message": {
            "data": data_b64,
            "messageId": "123",
            "publishTime": "2023-01-01T00:00:00Z"
        },
        "subscription": "projects/test/subscriptions/test-sub"
    }

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "worker"}

def test_process_message_success(mock_firestore):
    data = {
        "tenant_id": "test-tenant",
        "log_id": "log-123",
        "text": "Call me at 555-0199",
        "source": "test"
    }
    payload = create_pubsub_message(data)
    
    # Mock document reference chain
    mock_doc_ref = MagicMock()
    mock_firestore.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref
    
    response = client.post("/", json=payload)
    
    assert response.status_code == 200
    
    # Verify Firestore write
    mock_doc_ref.set.assert_called_once()
    call_args = mock_doc_ref.set.call_args[0][0]
    assert call_args["original_text"] == "Call me at 555-0199"
    assert call_args["modified_data"] == "Call me at [REDACTED]"
    assert call_args["log_id"] == "log-123"

def test_process_message_invalid_payload(mock_firestore):
    # Invalid base64
    payload = {
        "message": {
            "data": "invalid-base64",
        },
        "subscription": "sub"
    }
    response = client.post("/", json=payload)
    # Should ack (200) to stop retry of bad data
    assert response.status_code == 200
    mock_firestore.collection.assert_not_called()

def test_process_message_missing_fields(mock_firestore):
    data = {
        "tenant_id": "test-tenant",
        # Missing log_id and text
    }
    payload = create_pubsub_message(data)
    response = client.post("/", json=payload)
    # Should ack (200) to stop retry
    assert response.status_code == 200
    mock_firestore.collection.assert_not_called()
