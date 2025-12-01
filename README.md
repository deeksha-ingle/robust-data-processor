# Robust Data Processor

A multi-tenant, event-driven data ingestion pipeline deployed on Google Cloud Platform.

## Overview
This system is designed to handle high-throughput data ingestion (1000+ RPM), process it asynchronously, and store it securely with tenant isolation. It uses Cloud Run for compute, Pub/Sub for messaging, and Firestore for storage.

## Architecture
[Client] -> [API Service] -> [Pub/Sub] -> [Worker Service] -> [Firestore]

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

## Prerequisites
- Google Cloud Platform account
- `gcloud` CLI installed and configured
- Python 3.11+
- Docker (for deployment builds)

## Local Development

1. **Setup Environment**
   ```bash
   ./scripts/setup_local.sh
   source venv/bin/activate
   ```

2. **Run Services Locally**
   This starts the API, Worker, and local emulators for Pub/Sub and Firestore.
   ```bash
   ./scripts/run_local.sh
   ```

3. **Test Endpoints**
   ```bash
   ./scripts/test_endpoints.sh
   ```

## Testing
Run unit and integration tests:
```bash
pytest tests/
```

Run stress test (requires services running):
```bash
python tests/stress_test.py http://localhost:8080 --rpm 1000
```

## Deployment to GCP

1. **Deploy**
   ```bash
   ./scripts/deploy_gcp.sh <YOUR_PROJECT_ID>
   ```

2. **Verify**
   The script will output the API URL. You can use `scripts/test_endpoints.sh <API_URL>` to verify.

## Troubleshooting
- **Emulator Issues**: Ensure you have Java installed for Cloud emulators.
- **Permissions**: Ensure your gcloud user has permissions to create Cloud Run services and IAM roles.

## Multi-Tenancy
Data is isolated in Firestore under `tenants/{tenant_id}/processed_logs`. Each tenant's data is strictly separated by path.

## Crash Simulation & Resilience
The system is designed to survive worker crashes and heavy load:
1.  **Decoupling**: The API does not process data; it only pushes to Pub/Sub. If the Worker crashes, the API keeps accepting requests (202 Accepted).
2.  **Retries**: If a Worker instance crashes or fails to process a message (simulated by a 500 error), Pub/Sub automatically retries delivery.
3.  **Statelessness**: Cloud Run instances are stateless. If one crashes, a new one is spun up immediately to take its place.
