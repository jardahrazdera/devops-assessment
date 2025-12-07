from fastapi import FastAPI, HTTPException, Request
from prometheus_fastapi_instrumentator import Instrumentator
import logging
from datetime import datetime, UTC
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import uuid
import json
import redis
from pythonjsonlogger.json import JsonFormatter
from contextvars import ContextVar

# Context variable for request ID
request_id_context: ContextVar[str] = ContextVar("request_id", default=None)

# Configure JSON structured logging
class CustomJsonFormatter(JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.now(UTC).isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        # Add request_id if available
        request_id = request_id_context.get()
        if request_id:
            log_record['request_id'] = request_id

# Setup JSON logging
log_handler = logging.StreamHandler()
formatter = CustomJsonFormatter('%(timestamp)s %(level)s %(name)s %(message)s')
log_handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

app = FastAPI(
    title="DevOps Assessment API",
    description="Demo application for DevOps technical assessment",
    version="1.0.0"
)

# Request ID middleware for distributed tracing
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Add unique request ID to each request for tracing"""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request_id_context.set(request_id)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "")
db_conn = None

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = None

def get_redis_connection():
    """Get Redis connection with retry logic"""
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            redis_client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            redis_client = None
    return redis_client

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
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "devops-assessment-api"
    }

@app.get("/data")
async def get_data():
    """Retrieve all stored data from PostgreSQL with Redis caching"""
    CACHE_KEY = "data:all"
    CACHE_TTL = 60  # Cache for 60 seconds

    # Try to get from cache first
    redis_conn = get_redis_connection()
    if redis_conn:
        try:
            cached_data = redis_conn.get(CACHE_KEY)
            if cached_data:
                logger.info("GET /data - Cache HIT")
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Redis read error: {e}")

    # Cache miss - fetch from database
    logger.info("GET /data - Cache MISS, fetching from database")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, content, timestamp FROM data_items ORDER BY id")
            items = cur.fetchall()

        result = {
            "count": len(items),
            "data": [dict(item) for item in items]
        }

        # Cache the result
        if redis_conn:
            try:
                redis_conn.setex(CACHE_KEY, CACHE_TTL, json.dumps(result, default=str))
                logger.info(f"GET /data - Cached {len(items)} items for {CACHE_TTL}s")
            except Exception as e:
                logger.warning(f"Redis write error: {e}")

        return result
    except Exception as e:
        logger.error(f"GET /data - Error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/data")
async def create_data(item: dict):
    """Store new data item in PostgreSQL and invalidate cache"""
    CACHE_KEY = "data:all"

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

        # Invalidate cache after successful write
        redis_conn = get_redis_connection()
        if redis_conn:
            try:
                redis_conn.delete(CACHE_KEY)
                logger.info("POST /data - Cache invalidated")
            except Exception as e:
                logger.warning(f"Redis delete error: {e}")

        data_entry = dict(result)
        logger.info(f"POST /data - Created item with ID {data_entry['id']}")
        return data_entry
    except Exception as e:
        conn.rollback()
        logger.error(f"POST /data - Error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
