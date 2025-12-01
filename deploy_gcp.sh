#!/bin/bash

# deploy_gcp.sh
# Deploys the application to Google Cloud Platform.

set -e

if [ -z "$1" ]; then
    echo "Usage: ./deploy_gcp.sh <PROJECT_ID>"
    exit 1
fi

PROJECT_ID=$1
REGION="us-central1"
TOPIC_NAME="log-processing"
REPO_NAME="robust-data-processor"

echo "Deploying to GCP Project: $PROJECT_ID"

# Set project
gcloud config set project $PROJECT_ID

# Enable APIs
echo "Enabling APIs..."
gcloud services enable run.googleapis.com \
    pubsub.googleapis.com \
    firestore.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com

# Create Artifact Registry Repo
echo "Creating Artifact Registry repository..."
gcloud artifacts repositories create $REPO_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="Docker repository" || echo "Repository likely exists"

# Build and Push Images
echo "Building and pushing images..."
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/api:latest api/
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/worker:latest worker/

# Create Firestore Database (if not exists)
echo "Creating Firestore database..."
# Note: This might fail if database already exists, which is fine.
gcloud firestore databases create --location=$REGION || echo "Firestore database might already exist"

# Create Pub/Sub Topic
echo "Creating Pub/Sub topic..."
gcloud pubsub topics create $TOPIC_NAME || echo "Topic likely exists"

# Deploy Worker Service
echo "Deploying Worker Service..."
gcloud run deploy worker-service \
    --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/worker:latest \
    --region $REGION \
    --no-allow-unauthenticated \
    --set-env-vars GCP_PROJECT=$PROJECT_ID,LOG_LEVEL=INFO

# Get Worker URL
WORKER_URL=$(gcloud run services describe worker-service --region $REGION --format 'value(status.url)')
echo "Worker URL: $WORKER_URL"

# Create Service Account for Pub/Sub subscription
echo "Creating Service Account for Pub/Sub..."
gcloud iam service-accounts create pubsub-invoker \
    --display-name "Pub/Sub Invoker" || echo "Service account likely exists"

SERVICE_ACCOUNT_EMAIL="pubsub-invoker@$PROJECT_ID.iam.gserviceaccount.com"

# Grant permission to invoke Worker
echo "Granting permissions..."
gcloud run services add-iam-policy-binding worker-service \
    --region $REGION \
    --member=serviceAccount:$SERVICE_ACCOUNT_EMAIL \
    --role=roles/run.invoker

# Create Pub/Sub Subscription
echo "Creating Pub/Sub subscription..."
gcloud pubsub subscriptions create worker-subscription \
    --topic $TOPIC_NAME \
    --push-endpoint=$WORKER_URL \
    --push-auth-service-account=$SERVICE_ACCOUNT_EMAIL \
    --ack-deadline=600 || echo "Subscription likely exists"

# Deploy API Service
echo "Deploying API Service..."
gcloud run deploy api-service \
    --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/api:latest \
    --region $REGION \
    --allow-unauthenticated \
    --set-env-vars GCP_PROJECT=$PROJECT_ID,PUBSUB_TOPIC=$TOPIC_NAME,LOG_LEVEL=INFO

# Get API URL
API_URL=$(gcloud run services describe api-service --region $REGION --format 'value(status.url)')

echo "Deployment Complete!"
echo "API URL: $API_URL"
echo "Test with: curl -X POST $API_URL/ingest -H 'Content-Type: application/json' -d '{\"tenant_id\": \"test\", \"log_id\": \"1\", \"text\": \"hello\"}'"
