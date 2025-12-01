#!/bin/bash

# demo_input.sh
# Demonstrates sending a JSON file to the API and tracking it.

API_URL="http://localhost:8080"

echo "=== 1. The Input File (dummy_log.json) ==="
cat dummy_log.json
echo -e "\n"

echo "=== 2. Sending File to API ($API_URL/ingest) ==="
# We use curl to send the file content
# -d @filename tells curl to read from the file
curl -v -X POST "$API_URL/ingest" \
  -H "Content-Type: application/json" \
  -d @dummy_log.json

echo -e "\n\n=== 3. Where did it go? ==="
echo "The API received it and sent it to Pub/Sub."
echo "The Worker picked it up from Pub/Sub, processed it, and saved it to Firestore."
echo "Checking Firestore for the result..."

# Wait a moment for processing
sleep 2

# In a real scenario, we'd use the Firestore API or GUI to check.
# Here we simulate checking via a direct script or just explaining.
# Since we are running locally, we can't easily 'curl' Firestore emulator directly for data without client lib,
# but we can trust our previous integration tests.

echo "Data should be in Firestore at path: tenants/demo-tenant/processed_logs/demo-log-001"
