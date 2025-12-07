from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import os

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

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "")
db_conn = None

def get_db_connection():
    """Get database connection with retry logic"""
    global db_conn
    if db_conn is None or db_conn.closed:
        try:
            db_conn = psycopg2.connect(DATABASE_URL)
            logger.info("Connected to PostgreSQL database")
            # Create table if it doesn't exist
            with db_conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS data_items (
                        id SERIAL PRIMARY KEY,
                        content JSONB NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                db_conn.commit()
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            db_conn = None
    return db_conn

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
    """Retrieve all stored data from PostgreSQL"""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, content, timestamp FROM data_items ORDER BY id")
            items = cur.fetchall()

        logger.info(f"GET /data - Retrieved {len(items)} items")
        return {
            "count": len(items),
            "data": [dict(item) for item in items]
        }
    except Exception as e:
        logger.error(f"GET /data - Error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/data")
async def create_data(item: dict):
    """Store new data item in PostgreSQL"""
    if not item:
        raise HTTPException(status_code=400, detail="Empty data not allowed")

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO data_items (content) VALUES (%s) RETURNING id, content, timestamp",
                (psycopg2.extras.Json(item),)
            )
            result = cur.fetchone()
            conn.commit()

        data_entry = dict(result)
        logger.info(f"POST /data - Created item with ID {data_entry['id']}")
        return data_entry
    except Exception as e:
        conn.rollback()
        logger.error(f"POST /data - Error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
