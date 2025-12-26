"""
Name Streamer API - FastAPI Async Cloud Run Service
FIXED VERSION: Returns JSON response compatible with Dialogflow CX OpenAPI Tools

Dialogflow CX OpenAPI tools expect standard JSON responses, not SSE streaming.
This version returns a proper JSON response with the name repeated 5 times.

Author: Yash Kavaiya - Gen AI Guru
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Name Streamer API",
    description="Greeting service that returns a name 5 times - Compatible with Dialogflow CX",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Pydantic Models
# =============================================================================

class GreetingRequest(BaseModel):
    """Request model for greeting."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="The name to use in the greeting"
    )
    include_emoji: bool = Field(
        default=True,
        description="Whether to include emojis in greeting"
    )

    @validator('name')
    def validate_name(cls, v):
        """Validate and clean the name."""
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty or whitespace only")
        return cleaned


class GreetingResponse(BaseModel):
    """Response model for greeting - Dialogflow CX compatible."""
    success: bool
    name: str
    greetings: list[str]
    formatted_greeting: str  # Single string with all greetings for easy display
    total_count: int
    message: str


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    code: str
    details: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    service: str
    version: str
    timestamp: str


# =============================================================================
# Greeting Generation Logic
# =============================================================================

EMOJIS = ["🎉", "✨", "🌟", "💫", "🎊"]


def generate_greeting(name: str, index: int, include_emoji: bool = True) -> str:
    """Generate a single greeting message."""
    if include_emoji:
        emoji = EMOJIS[index % len(EMOJIS)]
        return f"{emoji} Hello {name}!"
    return f"Hello {name}!"


def generate_all_greetings(name: str, include_emoji: bool = True) -> dict:
    """
    Generate all 5 greetings at once.
    Returns a dictionary with greetings list and formatted string.
    """
    greetings = [
        generate_greeting(name, i, include_emoji)
        for i in range(5)
    ]
    
    # Create formatted string for easy display in Dialogflow
    formatted = "\n".join(greetings)
    
    return {
        "greetings": greetings,
        "formatted_greeting": formatted
    }


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Health check endpoint for Cloud Run."""
    return HealthResponse(
        status="healthy",
        service="name-streamer-api",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat() + "Z"
    )


@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Name Streamer API",
        "version": "1.0.0",
        "description": "Greeting service for Dialogflow CX Playbooks",
        "endpoints": {
            "stream_greeting": "POST /stream-greeting",
            "get_greeting": "GET /greeting?name=<name>",
            "health": "GET /health",
            "docs": "GET /docs"
        }
    }


@app.post("/stream-greeting", response_model=GreetingResponse, tags=["Greeting"])
async def stream_greeting(request: GreetingRequest) -> GreetingResponse:
    """
    Generate a personalized greeting with name repeated 5 times.
    
    This endpoint returns a JSON response compatible with Dialogflow CX OpenAPI tools.
    The response includes both an array of greetings and a formatted string.
    
    Args:
        request: GreetingRequest containing the name
        
    Returns:
        GreetingResponse with all 5 greetings in JSON format
    """
    logger.info(f"Received greeting request for: {request.name}")
    
    try:
        # Generate all greetings
        result = generate_all_greetings(request.name, request.include_emoji)
        
        response = GreetingResponse(
            success=True,
            name=request.name,
            greetings=result["greetings"],
            formatted_greeting=result["formatted_greeting"],
            total_count=5,
            message=f"Successfully generated 5 greetings for {request.name}"
        )
        
        logger.info(f"Generated greetings for: {request.name}")
        return response
        
    except Exception as e:
        logger.error(f"Error generating greeting: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to generate greeting",
                "code": "SERVER_ERROR",
                "details": str(e)
            }
        )


@app.get("/greeting", response_model=GreetingResponse, tags=["Greeting"])
async def get_greeting(
    name: str = Query(
        ...,
        min_length=1,
        max_length=100,
        description="The name to use in the greeting"
    ),
    include_emoji: bool = Query(
        default=True,
        description="Whether to include emojis"
    )
) -> GreetingResponse:
    """
    Get a greeting response via GET request.
    
    Alternative endpoint using query parameters instead of request body.
    Also compatible with Dialogflow CX OpenAPI tools.
    
    Args:
        name: The name to greet
        include_emoji: Whether to include emojis
        
    Returns:
        GreetingResponse with all 5 greetings
    """
    logger.info(f"Received GET greeting request for: {name}")
    
    cleaned_name = name.strip()
    if not cleaned_name:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Name cannot be empty",
                "code": "INVALID_REQUEST"
            }
        )
    
    # Generate all greetings
    result = generate_all_greetings(cleaned_name, include_emoji)
    
    return GreetingResponse(
        success=True,
        name=cleaned_name,
        greetings=result["greetings"],
        formatted_greeting=result["formatted_greeting"],
        total_count=5,
        message=f"Successfully generated 5 greetings for {cleaned_name}"
    )


# =============================================================================
# Error Handlers
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": str(exc.detail) if isinstance(exc.detail, str) else exc.detail.get("error", "Unknown error"),
            "code": exc.detail.get("code", "HTTP_ERROR") if isinstance(exc.detail, dict) else "HTTP_ERROR"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler for unexpected errors."""
    logger.error(f"Unexpected error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "An unexpected error occurred",
            "code": "SERVER_ERROR",
            "details": str(exc)
        }
    )


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    import os
    
    # Get port from environment variable (Cloud Run sets PORT)
    port = int(os.environ.get("PORT", 8080))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
