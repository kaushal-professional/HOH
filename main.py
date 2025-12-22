"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

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

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
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

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
Base.metadata.create_all(bind=engine)
logger.info("Database tables created successfully")

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
