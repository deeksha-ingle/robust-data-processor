import os
import json
import logging
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Request, Response, status, Header
from pydantic import BaseModel
from google.cloud import pubsub_v1
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s", "correlation_id": "%(correlation_id)s"}',
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Data Ingestion API")

# Initialize Pub/Sub publisher
PROJECT_ID = os.getenv("GCP_PROJECT")
TOPIC_ID = os.getenv("PUBSUB_TOPIC")

# Check if running in emulator
if os.getenv("PUBSUB_EMULATOR_HOST"):
    publisher = pubsub_v1.PublisherClient(
        client_options={"api_endpoint": os.getenv("PUBSUB_EMULATOR_HOST")}
    )
else:
    publisher = pubsub_v1.PublisherClient()

if PROJECT_ID and TOPIC_ID:
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
else:
    logger.warning("GCP_PROJECT or PUBSUB_TOPIC not set. Pub/Sub publishing will fail.")
    topic_path = None

class LogPayload(BaseModel):
    """
    Pydantic model for JSON payload validation.
    """
    tenant_id: str
    log_id: str
    text: str

def get_correlation_id(log_id: str) -> Dict[str, str]:
    """Helper to add correlation_id to log records."""
    return {"correlation_id": log_id}

@app.get("/")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok", "service": "api"}

@app.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_log(
    request: Request,
    response: Response,
    x_tenant_id: Optional[str] = Header(None)
):
    """
    Ingests log data via JSON or text/plain.
    Normalizes data and publishes to Pub/Sub.
    """
    content_type = request.headers.get("content-type", "")
    
    normalized_data: Dict[str, Any] = {}
    
    try:
        if "application/json" in content_type:
            # Handle JSON payload
            try:
                payload = await request.json()
                # Validate using Pydantic
                log_data = LogPayload(**payload)
                normalized_data = {
                    "tenant_id": log_data.tenant_id,
                    "log_id": log_data.log_id,
                    "text": log_data.text,
                    "source": "json"
                }
            except Exception as e:
                logger.error(f"Invalid JSON payload: {str(e)}", extra={"correlation_id": "unknown"})
                raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
                
        elif "text/plain" in content_type:
            # Handle text payload
            if not x_tenant_id:
                logger.error("Missing X-Tenant-ID header for text payload", extra={"correlation_id": "unknown"})
                raise HTTPException(status_code=400, detail="X-Tenant-ID header required for text/plain")
            
            body = await request.body()
            text_content = body.decode("utf-8")
            # Generate a simple log_id if not provided (could be improved)
            import uuid
            log_id = str(uuid.uuid4())
            
            normalized_data = {
                "tenant_id": x_tenant_id,
                "log_id": log_id,
                "text": text_content,
                "source": "text"
            }
        else:
            raise HTTPException(status_code=400, detail="Unsupported Content-Type")

        # Log receipt
        logger.info(
            f"Received request for tenant {normalized_data['tenant_id']}", 
            extra=get_correlation_id(normalized_data['log_id'])
        )

        # Publish to Pub/Sub
        if topic_path:
            data_str = json.dumps(normalized_data)
            data_bytes = data_str.encode("utf-8")
            
            # Publish asynchronously
            future = publisher.publish(topic_path, data_bytes, tenant_id=normalized_data['tenant_id'])
            # We don't wait for the result to keep it non-blocking/fast for the client
            # In a real prod scenario, we might want to handle publish errors more robustly
            # or use a callback, but for high throughput 202, fire-and-forget is often acceptable
            # if we trust the infrastructure. 
            # However, to be 'robust', let's add a callback to log errors.
            
            def get_callback(f, data):
                def callback(f):
                    try:
                        f.result()
                        # Success logging is verbose for high throughput, maybe debug level
                        # logger.debug(f"Published message {data['log_id']}")
                    except Exception as e:
                        logger.error(f"Publishing failed for {data['log_id']}: {e}", extra=get_correlation_id(data['log_id']))
                return callback

            future.add_done_callback(get_callback(future, normalized_data))
            
            logger.info("Message published to Pub/Sub", extra=get_correlation_id(normalized_data['log_id']))
        else:
            logger.error("Pub/Sub topic not configured", extra=get_correlation_id(normalized_data['log_id']))
            raise HTTPException(status_code=500, detail="Server misconfiguration")

        return {"status": "accepted", "log_id": normalized_data["log_id"]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal error: {str(e)}", extra={"correlation_id": "unknown"})
        raise HTTPException(status_code=500, detail="Internal Server Error")
