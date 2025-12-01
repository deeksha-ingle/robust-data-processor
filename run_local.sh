#!/bin/bash

# run_local.sh
# Runs the services locally using emulators.

set -e

# Function to kill background processes on exit
cleanup() {
    echo "Stopping services..."
    kill $(jobs -p) 2>/dev/null
}
trap cleanup EXIT

# Check for gcloud
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud CLI not found. Please install Google Cloud SDK."
    exit 1
fi

echo "Starting Firestore Emulator..."
gcloud emulators firestore start --host-port=localhost:8082 --quiet &
FIRESTORE_PID=$!
export FIRESTORE_EMULATOR_HOST=localhost:8082
export GCLOUD_PROJECT=local-project

# Wait for Firestore emulator to start
sleep 5

echo "Starting Pub/Sub Emulator..."
gcloud emulators pubsub start --host-port=localhost:8085 --quiet &
PUBSUB_PID=$!
export PUBSUB_EMULATOR_HOST=localhost:8085
export PUBSUB_PROJECT_ID=local-project

# Wait for Pub/Sub emulator to start
sleep 5

# Create Topic and Subscription
echo "Creating Pub/Sub topic and subscription..."
python3 -c "
from google.cloud import pubsub_v1
import os

project_id = 'local-project'
topic_id = 'log-processing'
subscription_id = 'log-processing-sub'

publisher = pubsub_v1.PublisherClient(client_options={'api_endpoint': 'localhost:8085'})
subscriber = pubsub_v1.SubscriberClient(client_options={'api_endpoint': 'localhost:8085'})

topic_path = publisher.topic_path(project_id, topic_id)
subscription_path = subscriber.subscription_path(project_id, subscription_id)

try:
    publisher.create_topic(request={'name': topic_path})
    print(f'Topic {topic_path} created.')
except Exception:
    print('Topic already exists.')

try:
    # For local dev, we use pull or push. 
    # To simulate push locally is hard without a proxy. 
    # So for local dev, we might need to modify worker to pull or just use pull subscription in a separate script to forward to worker.
    # OR we can just run the worker and have a separate script that pulls and posts to worker.
    # Simpler: Just use Pull for local verification in a test script, OR
    # Use a push subscription with a local endpoint (requires ngrok or similar if not on same network, but localhost should work if emulator supports it).
    # The Pub/Sub emulator DOES support push subscriptions to localhost.
    
    push_config = pubsub_v1.types.PushConfig(push_endpoint='http://localhost:8081/')
    subscriber.create_subscription(request={'name': subscription_path, 'topic': topic_path, 'push_config': push_config})
    print(f'Subscription {subscription_path} created.')
except Exception as e:
    print(f'Subscription creation failed (might exist): {e}')
"

echo "Starting API Service on port 8080..."
cd api
uvicorn main:app --host 0.0.0.0 --port 8080 &
API_PID=$!
cd ..

echo "Starting Worker Service on port 8081..."
cd worker
uvicorn main:app --host 0.0.0.0 --port 8081 &
WORKER_PID=$!
cd ..

echo "Services running. Press Ctrl+C to stop."
echo "API: http://localhost:8080"
echo "Worker: http://localhost:8081"

wait
