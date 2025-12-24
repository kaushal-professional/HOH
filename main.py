"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import asyncio
import httpx
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.routers import api_router

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format=settings.log_format,
)
logger = logging.getLogger(__name__)

# Suppress uvicorn warnings for invalid HTTP requests
logging.getLogger("uvicorn.error").setLevel(logging.ERROR)

# Background task to keep Render service alive
async def send_health_check():
    """Send health check to Render service every 5 minutes"""
    health_url = "https://hoh-jfr9.onrender.com/health"

    while True:
        try:
            await asyncio.sleep(300)  # Wait 5 minutes (300 seconds)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(health_url)
                if response.status_code == 200:
                    logger.info(f"✅ Health check successful: {health_url}")
                else:
                    logger.warning(f"⚠️  Health check returned {response.status_code}: {health_url}")
        except Exception as e:
            logger.error(f"❌ Health check failed: {str(e)}")

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the background health check task
    task = asyncio.create_task(send_health_check())
    logger.info("🚀 Background health check task started")

    yield

    # Shutdown: Cancel the background task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("🛑 Background health check task stopped")

# Create FastAPI app with lifespan
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# Add middleware to handle invalid requests
@app.middleware("http")
async def block_invalid_requests(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        # Silently drop invalid HTTP requests
        logger.debug(f"Invalid request blocked: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Invalid request"}
        )

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables (with error handling)
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
except Exception as e:
    logger.error(f"Failed to create database tables: {str(e)}")
    logger.warning("Application will start but database operations may fail")
    logger.warning("Please check your database connection settings")

# Include API router
app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    """Root endpoint for health check."""
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.ENVIRONMENT
    }

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level="error",  # Suppress invalid HTTP warnings
        access_log=False,   # Disable access logs to reduce noise
    )
