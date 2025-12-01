# Architecture Documentation

## System Overview
The Robust Data Processor is an event-driven architecture designed for scalability and reliability.

### Components

1. **API Service (Cloud Run)**
   - **Responsibility**: Ingest data, validate input, normalize format, publish to Pub/Sub.
   - **Scalability**: Auto-scales based on request volume (Cloud Run).
   - **Reliability**: Returns 202 Accepted immediately to decouple ingestion from processing.

2. **Pub/Sub (Message Queue)**
   - **Responsibility**: Buffer messages between API and Worker.
   - **Reliability**: Guarantees at-least-once delivery. Handles bursts of traffic.

3. **Worker Service (Cloud Run)**
   - **Responsibility**: Receive messages via Push subscription, simulate processing, redact sensitive data, write to Firestore.
   - **Scalability**: Auto-scales based on queue depth/latency.
   - **Failure Recovery**: Returns 500 on failure to trigger Pub/Sub retry mechanism with exponential backoff.

4. **Firestore (NoSQL Database)**
   - **Responsibility**: Store processed logs.
   - **Multi-Tenancy**: Data is stored in a hierarchical structure: `tenants/{tenant_id}/processed_logs/{log_id}`.

### System Diagram
```mermaid
graph LR
    Client[Client/User] -->|POST /ingest| API[API Service\n(Cloud Run)]
    API -->|Publish| PubSub[Pub/Sub Topic\n(log-processing)]
    PubSub -->|Push| Worker[Worker Service\n(Cloud Run)]
    Worker -->|Write| DB[(Firestore DB)]
    
    subgraph Google Cloud
    API
    PubSub
    Worker
    DB
    end
```

## Data Flow
1. Client sends POST request to `/ingest`.
2. API validates and publishes message to `log-processing` topic.
3. API returns 202 Accepted.
4. Pub/Sub pushes message to Worker Service.
5. Worker decodes message, simulates processing (sleep), redacts text.
6. Worker writes result to Firestore.
7. Worker returns 200 OK to acknowledge message.

## Scalability & Performance
- **Asynchronous Processing**: Heavy processing is offloaded to the worker, allowing the API to remain responsive.
- **Serverless**: Cloud Run scales to zero when unused and scales up to handle thousands of concurrent requests.
- **Firestore**: Handles high write rates and provides strong consistency.

## Failure Scenarios
- **API Failure**: Load balancer retries or client receives error.
- **Worker Failure**: Pub/Sub retries delivery until success or dead-letter queue (if configured).
- **Database Failure**: Worker fails to write, returns 500, Pub/Sub retries.
