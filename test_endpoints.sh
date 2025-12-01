#!/bin/bash

# test_endpoints.sh
# Tests the API endpoints.

if [ -z "$1" ]; then
    API_URL="http://localhost:8080"
else
    API_URL=$1
fi

echo "Testing API at $API_URL"

# Test Health Check
echo "1. Testing Health Check..."
curl -s "$API_URL/" | grep "ok" && echo " - Health Check Passed" || echo " - Health Check Failed"

# Test JSON Ingestion
echo "2. Testing JSON Ingestion..."
RESPONSE=$(curl -s -X POST "$API_URL/ingest" \
    -H "Content-Type: application/json" \
    -d '{"tenant_id": "test-tenant", "log_id": "test-log-1", "text": "Hello JSON"}')
echo $RESPONSE | grep "accepted" && echo " - JSON Ingestion Passed" || echo " - JSON Ingestion Failed"

# Test Text Ingestion
echo "3. Testing Text Ingestion..."
RESPONSE=$(curl -s -X POST "$API_URL/ingest" \
    -H "Content-Type: text/plain" \
    -H "X-Tenant-ID: test-tenant" \
    -d "Hello Text")
echo $RESPONSE | grep "accepted" && echo " - Text Ingestion Passed" || echo " - Text Ingestion Failed"

echo "Done."
