import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Mock google.cloud.pubsub_v1 before importing main
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.pubsub_v1"] = MagicMock()

# Add api directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@pytest.fixture
def mock_publisher():
    with patch("main.publisher") as mock:
        yield mock

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}

def test_ingest_json_valid(mock_publisher):
    payload = {
        "tenant_id": "test-tenant",
        "log_id": "log-123",
        "text": "sample log"
    }
    response = client.post("/ingest", json=payload)
    assert response.status_code == 202
    assert response.json()["log_id"] == "log-123"
    mock_publisher.publish.assert_called_once()

def test_ingest_json_invalid_missing_field(mock_publisher):
    payload = {
        "tenant_id": "test-tenant",
        # Missing log_id and text
    }
    response = client.post("/ingest", json=payload)
    assert response.status_code == 400
    mock_publisher.publish.assert_not_called()

def test_ingest_text_valid(mock_publisher):
    headers = {"X-Tenant-ID": "test-tenant", "Content-Type": "text/plain"}
    response = client.post("/ingest", content="raw text log", headers=headers)
    assert response.status_code == 202
    assert "log_id" in response.json()
    mock_publisher.publish.assert_called_once()

def test_ingest_text_missing_header(mock_publisher):
    headers = {"Content-Type": "text/plain"}
    response = client.post("/ingest", content="raw text log", headers=headers)
    assert response.status_code == 400
    mock_publisher.publish.assert_not_called()
