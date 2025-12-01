#!/bin/bash

# setup_local.sh
# Sets up the local development environment.

set -e

echo "Setting up local environment..."

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 could not be found."
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements-dev.txt
pip install -r api/requirements.txt
pip install -r worker/requirements.txt

# Create .env file if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    # Set default values for local dev
    sed -i 's/GCP_PROJECT=your-project-id/GCP_PROJECT=local-project/g' .env
    sed -i 's/PUBSUB_TOPIC=log-processing/PUBSUB_TOPIC=log-processing/g' .env
fi

echo "Setup complete. Run 'source venv/bin/activate' to activate the virtual environment."
