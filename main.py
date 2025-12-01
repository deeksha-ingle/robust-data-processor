import os
import json
import base64
import time
import logging
import datetime
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel
from google.cloud import firestore
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
app = FastAPI(title="Data Processing Worker")

# Initialize Firestore client
PROJECT_ID = os.getenv("GCP_PROJECT")

# Check if running in emulator (handled automatically by google-cloud-firestore if env var is set)
# But we explicitly check to log it
if os.getenv("FIRESTORE_EMULATOR_HOST"):
    logger.info(f"Using Firestore Emulator at {os.getenv('FIRESTORE_EMULATOR_HOST')}", extra={"correlation_id": "system"})

if PROJECT_ID:
    db = firestore.Client(project=PROJECT_ID)
else:
    logger.warning("GCP_PROJECT not set. Firestore operations might fail if not using emulator default project.")
    # Fallback for emulator if project not set
    db = firestore.Client()

class PubSubMessage(BaseModel):
    """
    Pydantic model for Pub/Sub push message.
    """
    message: Dict[str, Any]
    subscription: str

def get_correlation_id(log_id: str) -> Dict[str, str]:
    """Helper to add correlation_id to log records."""
    return {"correlation_id": log_id}

def process_text(text: str) -> str:
    """
    Simulates heavy processing and performs redaction.
    """
    # Simulate heavy processing: 0.05s per character
    sleep_time = len(text) * 0.05
    # Cap sleep time to avoid timeouts during simple tests, or keep as requested?
    # Requirement: "Simulate heavy processing (0.05s per character sleep)"
    # We'll stick to requirement but maybe cap at 10s for safety in non-async worker context if needed,
    # but here we are async so it's fine to block the thread if we were using sync sleep, 
    # but we should use asyncio.sleep if we want to be truly async. 
    # However, standard time.sleep blocks the event loop. 
    # For a CPU bound simulation, blocking is 'correct' to simulate load, 
    # but for sleep it just pauses. 
    # Let's use time.sleep as requested to strictly follow "time.sleep(len(text) * 0.05)"
    time.sleep(sleep_time)
    
    # Redaction
    return text.replace("555-0199", "[REDACTED]")

@app.get("/")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok", "service": "worker"}

@app.post("/", status_code=status.HTTP_200_OK)
async def receive_message(request: Request):
    """
    Receives Pub/Sub push messages.
    """
    try:
        # Parse incoming request
        body = await request.json()
        
        # Validate structure (Pub/Sub push format)
        if "message" not in body:
            msg = "Invalid Pub/Sub message format"
            logger.error(msg, extra={"correlation_id": "unknown"})
            # Return 400 to Pub/Sub (will not retry usually, depending on config)
            # But for Pub/Sub push, 200/201/202/204 = ack, others = nack (retry)
            # If it's invalid format, we should probably Ack to stop retries?
            # Let's return 400 which is a Nack, but maybe we want to Ack bad messages to drop them.
            # For now, let's return 400.
            raise HTTPException(status_code=400, detail=msg)

        pubsub_message = body["message"]
        data_base64 = pubsub_message.get("data")
        
        if not data_base64:
            logger.error("Missing data field in message", extra={"correlation_id": "unknown"})
            raise HTTPException(status_code=400, detail="Missing data field")

        # Decode message
        try:
            data_str = base64.b64decode(data_base64).decode("utf-8")
            data = json.loads(data_str)
        except Exception as e:
            logger.error(f"Failed to decode message: {e}", extra={"correlation_id": "unknown"})
            # Ack to stop retry of bad data
            return Response(status_code=200)

        tenant_id = data.get("tenant_id")
        log_id = data.get("log_id")
        text = data.get("text")
        source = data.get("source")

        if not all([tenant_id, log_id, text]):
             logger.error("Missing required fields in payload", extra={"correlation_id": "unknown"})
             return Response(status_code=200) # Ack bad data

        correlation_context = get_correlation_id(log_id)
        logger.info(f"Processing message for tenant {tenant_id}", extra=correlation_context)

        # Process data
        try:
            processed_text = process_text(text)
        except Exception as e:
             logger.error(f"Processing failed: {e}", extra=correlation_context)
             raise HTTPException(status_code=500, detail="Processing failed")

        # Store in Firestore
        try:
            doc_ref = db.collection("tenants").document(tenant_id).collection("processed_logs").document(log_id)
            doc_ref.set({
                "source": source,
                "original_text": text,
                "modified_data": processed_text,
                "processed_at": datetime.datetime.utcnow().isoformat(),
                "log_id": log_id
            })
            logger.info("Data stored in Firestore", extra=correlation_context)
        except Exception as e:
            logger.error(f"Firestore write failed: {e}", extra=correlation_context)
            # Return 500 to trigger Pub/Sub retry
            raise HTTPException(status_code=500, detail="Storage failed")

        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}", extra={"correlation_id": "unknown"})
        raise HTTPException(status_code=500, detail="Internal Server Error")
