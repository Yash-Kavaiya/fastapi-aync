"""
Name Streamer API - FastAPI Async Cloud Run Service with SSE Streaming

This service provides streaming greetings that repeat a user's name 5 times
using Server-Sent Events (SSE) for real-time response delivery.

Author: Yash Kavaiya - Gen AI Guru
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
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
    description="Streaming greeting service that returns a name 5 times via SSE",
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
    """Request model for streaming greeting."""
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
    """Response model for non-streaming greeting."""
    success: bool
    name: str
    greetings: list[str]
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


async def generate_streaming_greetings(
    name: str,
    include_emoji: bool = True,
    delay: float = 0.5
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted greeting messages.
    
    Streams the name 5 times with configurable delay between each greeting.
    
    Args:
        name: The name to greet
        include_emoji: Whether to include emojis
        delay: Delay in seconds between each greeting
        
    Yields:
        SSE-formatted event strings
    """
    logger.info(f"Starting streaming greetings for: {name}")
    
    # Stream 5 greetings
    for i in range(5):
        greeting = generate_greeting(name, i, include_emoji)
        
        # Format as Server-Sent Event
        event_data = {
            "event": "greeting",
            "id": i + 1,
            "data": greeting
        }
        
        # SSE format: event: type\ndata: content\nid: number\n\n
        sse_message = f"event: greeting\nid: {i + 1}\ndata: {json.dumps(event_data)}\n\n"
        
        logger.info(f"Streaming greeting {i + 1}/5: {greeting}")
        yield sse_message
        
        # Add delay between greetings for visible streaming effect
        await asyncio.sleep(delay)
    
    # Send completion event
    completion_data = {
        "event": "complete",
        "data": f"Successfully streamed 5 greetings for {name}",
        "total_count": 5
    }
    yield f"event: complete\ndata: {json.dumps(completion_data)}\n\n"
    
    logger.info(f"Completed streaming greetings for: {name}")


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
        "description": "Streaming greeting service for Dialogflow CX Playbooks",
        "endpoints": {
            "stream_greeting": "POST /stream-greeting",
            "get_greeting": "GET /greeting?name=<name>",
            "health": "GET /health",
            "docs": "GET /docs"
        }
    }


@app.post("/stream-greeting", tags=["Greeting"])
async def stream_greeting(request: GreetingRequest):
    """
    Stream a personalized greeting via Server-Sent Events.
    
    Returns the user's name 5 times in a streaming response format.
    Each greeting is delivered as a separate SSE event with a small delay.
    
    Args:
        request: GreetingRequest containing the name
        
    Returns:
        StreamingResponse with text/event-stream content type
    """
    logger.info(f"Received streaming greeting request for: {request.name}")
    
    try:
        return StreamingResponse(
            generate_streaming_greetings(
                name=request.name,
                include_emoji=request.include_emoji,
                delay=0.5  # 500ms between each greeting
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )
    except Exception as e:
        logger.error(f"Error generating streaming greeting: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Failed to generate streaming greeting",
                code="SERVER_ERROR",
                details=str(e)
            ).dict()
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
    Get a non-streaming greeting response.
    
    Returns all 5 greetings at once in a JSON response.
    Use this endpoint for simpler integrations that don't need streaming.
    
    Args:
        name: The name to greet
        include_emoji: Whether to include emojis
        
    Returns:
        GreetingResponse with all 5 greetings
    """
    logger.info(f"Received non-streaming greeting request for: {name}")
    
    cleaned_name = name.strip()
    if not cleaned_name:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="Name cannot be empty",
                code="INVALID_REQUEST"
            ).dict()
        )
    
    # Generate all 5 greetings
    greetings = [
        generate_greeting(cleaned_name, i, include_emoji)
        for i in range(5)
    ]
    
    return GreetingResponse(
        success=True,
        name=cleaned_name,
        greetings=greetings,
        total_count=5,
        message=f"Successfully generated 5 greetings for {cleaned_name}"
    )


# =============================================================================
# Alternative Streaming Endpoints (for different client needs)
# =============================================================================

@app.post("/stream-greeting-simple", tags=["Greeting"])
async def stream_greeting_simple(request: GreetingRequest):
    """
    Simple streaming endpoint that returns plain text chunks.
    
    Alternative to SSE for clients that prefer simpler streaming.
    """
    async def generate_simple():
        for i in range(5):
            greeting = generate_greeting(request.name, i, request.include_emoji)
            yield f"{greeting}\n"
            await asyncio.sleep(0.5)
        yield f"\n--- All 5 greetings for {request.name} complete! ---\n"
    
    return StreamingResponse(
        generate_simple(),
        media_type="text/plain",
        headers={"X-Accel-Buffering": "no"}
    )


@app.post("/stream-greeting-json", tags=["Greeting"])
async def stream_greeting_json(request: GreetingRequest):
    """
    JSON streaming endpoint using newline-delimited JSON (NDJSON).
    
    Each line is a valid JSON object for easy parsing.
    """
    async def generate_ndjson():
        for i in range(5):
            greeting = generate_greeting(request.name, i, request.include_emoji)
            data = {
                "index": i + 1,
                "greeting": greeting,
                "name": request.name,
                "is_last": i == 4
            }
            yield json.dumps(data) + "\n"
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        generate_ndjson(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no"}
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
    
    # Get port from environment variable (Cloud Run sets PORT)
    import os
    port = int(os.environ.get("PORT", 8080))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,  # Disable reload in production
        log_level="info"
    )
