from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
import logging
from datetime import datetime

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DevOps Assessment API",
    description="Demo application for DevOps technical assessment",
    version="1.0.0"
)

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

# In-memory storage (simple but functional)
data_store = []

@app.get("/health")
async def health_check():
    """Health check endpoint for k8s probes"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "devops-assessment-api"
    }

@app.get("/data")
async def get_data():
    """Retrieve all stored data"""
    logger.info(f"GET /data - Retrieved {len(data_store)} items")
    return {
        "count": len(data_store),
        "data": data_store
    }

@app.post("/data")
async def create_data(item: dict):
    """Store new data item"""
    if not item:
        raise HTTPException(status_code=400, detail="Empty data not allowed")

    data_entry = {
        "id": len(data_store) + 1,
        "content": item,
        "timestamp": datetime.utcnow().isoformat()
    }
    data_store.append(data_entry)

    logger.info(f"POST /data - Created item with ID {data_entry['id']}")
    return data_entry
