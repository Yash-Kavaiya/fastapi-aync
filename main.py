"""
FastAPI Cloud Run Backend - Production Ready
============================================
Comprehensive async API with streaming, SSE, WebSocket, and OpenAPI tool specs.
Author: Gen AI Guru
"""

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import httpx
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, EmailStr, validator
from sse_starlette.sse import EventSourceResponse

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================
class Settings:
    """Application settings from environment variables."""
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "FastAPI Cloud Run Backend")
    VERSION: str = os.getenv("VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    API_KEY: str = os.getenv("API_KEY", "your-secret-api-key")
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    PORT: int = int(os.getenv("PORT", "8080"))

settings = Settings()

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class StatusEnum(str, Enum):
    """Status enumeration for various operations."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Health status")
    timestamp: str = Field(..., description="Current timestamp")
    version: str = Field(..., description="API version")
    
class UserCreate(BaseModel):
    """User creation request model."""
    name: str = Field(..., min_length=2, max_length=100, description="User's full name")
    email: EmailStr = Field(..., description="User's email address")
    age: Optional[int] = Field(None, ge=0, le=150, description="User's age")
    tags: List[str] = Field(default_factory=list, description="User tags")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "age": 30,
                "tags": ["developer", "ai-enthusiast"]
            }
        }

class UserResponse(BaseModel):
    """User response model."""
    id: str = Field(..., description="Unique user ID")
    name: str = Field(..., description="User's full name")
    email: str = Field(..., description="User's email")
    age: Optional[int] = Field(None, description="User's age")
    tags: List[str] = Field(default_factory=list)
    created_at: str = Field(..., description="Creation timestamp")

class ChatMessage(BaseModel):
    """Chat message model for streaming responses."""
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    
class ChatRequest(BaseModel):
    """Chat request model."""
    messages: List[ChatMessage] = Field(..., description="Conversation history")
    stream: bool = Field(default=False, description="Enable streaming response")
    max_tokens: int = Field(default=1024, ge=1, le=4096, description="Maximum tokens")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")

class TaskCreate(BaseModel):
    """Background task creation model."""
    task_type: str = Field(..., description="Type of task to execute")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Task payload")
    priority: int = Field(default=1, ge=1, le=10, description="Task priority")

class TaskResponse(BaseModel):
    """Background task response model."""
    task_id: str = Field(..., description="Unique task ID")
    status: StatusEnum = Field(..., description="Task status")
    created_at: str = Field(..., description="Task creation time")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result if completed")

# OpenAPI Tool Specification Models
class ToolParameter(BaseModel):
    """Tool parameter specification for OpenAPI."""
    type: str = Field(..., description="Parameter type")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(default=True, description="Is parameter required")
    enum: Optional[List[str]] = Field(None, description="Enum values if applicable")

class ToolSpec(BaseModel):
    """Tool specification for AI agents."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: Dict[str, ToolParameter] = Field(..., description="Tool parameters")
    
class ToolExecutionRequest(BaseModel):
    """Tool execution request model."""
    tool_name: str = Field(..., description="Name of tool to execute")
    parameters: Dict[str, Any] = Field(..., description="Tool parameters")

class ToolExecutionResponse(BaseModel):
    """Tool execution response model."""
    tool_name: str
    success: bool
    result: Any
    execution_time_ms: float

# ============================================================================
# IN-MEMORY STORAGE (Replace with database in production)
# ============================================================================
users_db: Dict[str, UserResponse] = {}
tasks_db: Dict[str, TaskResponse] = {}
websocket_connections: List[WebSocket] = []

# ============================================================================
# SECURITY
# ============================================================================
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

async def verify_api_key(api_key: Optional[str] = Depends(api_key_header)) -> str:
    """Verify API key for protected endpoints."""
    if api_key is None or api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key

async def verify_bearer_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> str:
    """Verify Bearer token for protected endpoints."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    # In production, validate JWT token here
    return credentials.credentials

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    logger.info(f"🚀 Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"📍 Running on port {settings.PORT}")
    
    # Initialize resources (database connections, etc.)
    yield
    
    # Shutdown
    logger.info("👋 Shutting down application...")
    # Cleanup resources

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
## FastAPI Cloud Run Backend

A comprehensive, production-ready FastAPI backend designed for Google Cloud Run.

### Features
- 🚀 **Async/Await** - Full async support for high performance
- 📡 **Streaming** - Server-Sent Events and streaming responses
- 🔌 **WebSocket** - Real-time bidirectional communication
- 🛠️ **OpenAPI Tools** - AI agent tool specifications
- 🔐 **Security** - API Key and Bearer token authentication
- 📊 **Background Tasks** - Async task processing
- 🏥 **Health Checks** - Kubernetes-ready health endpoints
    """,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "Health", "description": "Health check endpoints"},
        {"name": "Users", "description": "User management operations"},
        {"name": "Chat", "description": "Chat and streaming endpoints"},
        {"name": "SSE", "description": "Server-Sent Events endpoints"},
        {"name": "WebSocket", "description": "WebSocket real-time endpoints"},
        {"name": "Tasks", "description": "Background task operations"},
        {"name": "Tools", "description": "OpenAPI tool specifications for AI agents"},
        {"name": "Files", "description": "File upload and download operations"},
    ],
)

# ============================================================================
# MIDDLEWARE
# ============================================================================
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(process_time)
    
    logger.info(f"Request {request_id}: {request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)")
    return response

# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================
@app.get("/", tags=["Health"], response_model=HealthResponse)
async def root():
    """Root endpoint - basic health check."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version=settings.VERSION,
    )

@app.get("/health", tags=["Health"], response_model=HealthResponse)
async def health_check():
    """Health check endpoint for Cloud Run."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version=settings.VERSION,
    )

@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe for Kubernetes/Cloud Run."""
    # Check database connections, external services, etc.
    return {"status": "ready", "checks": {"database": "ok", "cache": "ok"}}

@app.get("/live", tags=["Health"])
async def liveness_check():
    """Liveness probe for Kubernetes/Cloud Run."""
    return {"status": "alive"}

# ============================================================================
# USER CRUD ENDPOINTS
# ============================================================================
@app.post("/users", tags=["Users"], response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, api_key: str = Depends(verify_api_key)):
    """Create a new user."""
    user_id = str(uuid.uuid4())
    user_response = UserResponse(
        id=user_id,
        name=user.name,
        email=user.email,
        age=user.age,
        tags=user.tags,
        created_at=datetime.utcnow().isoformat(),
    )
    users_db[user_id] = user_response
    logger.info(f"Created user: {user_id}")
    return user_response

@app.get("/users", tags=["Users"], response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum records to return"),
    api_key: str = Depends(verify_api_key),
):
    """List all users with pagination."""
    users = list(users_db.values())
    return users[skip : skip + limit]

@app.get("/users/{user_id}", tags=["Users"], response_model=UserResponse)
async def get_user(
    user_id: str = Path(..., description="User ID"),
    api_key: str = Depends(verify_api_key),
):
    """Get a specific user by ID."""
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return users_db[user_id]

@app.put("/users/{user_id}", tags=["Users"], response_model=UserResponse)
async def update_user(
    user_id: str,
    user: UserCreate,
    api_key: str = Depends(verify_api_key),
):
    """Update an existing user."""
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    
    existing = users_db[user_id]
    updated = UserResponse(
        id=user_id,
        name=user.name,
        email=user.email,
        age=user.age,
        tags=user.tags,
        created_at=existing.created_at,
    )
    users_db[user_id] = updated
    return updated

@app.delete("/users/{user_id}", tags=["Users"], status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: str, api_key: str = Depends(verify_api_key)):
    """Delete a user."""
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    del users_db[user_id]
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# ============================================================================
# STREAMING CHAT ENDPOINTS
# ============================================================================
async def generate_stream_response(messages: List[ChatMessage]) -> AsyncGenerator[str, None]:
    """Generate streaming response chunks."""
    response_text = f"I received {len(messages)} messages. Here's a streaming response: "
    words = response_text.split()
    
    for word in words:
        yield f"data: {json.dumps({'content': word + ' ', 'done': False})}\n\n"
        await asyncio.sleep(0.1)
    
    # Simulate more complex streaming
    for i in range(5):
        chunk = f"Processing chunk {i+1}... "
        yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
        await asyncio.sleep(0.2)
    
    yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"

@app.post("/chat", tags=["Chat"])
async def chat_completion(request: ChatRequest):
    """
    Chat completion endpoint with optional streaming.
    
    When stream=True, returns Server-Sent Events stream.
    When stream=False, returns complete response as JSON.
    """
    if request.stream:
        return StreamingResponse(
            generate_stream_response(request.messages),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    
    # Non-streaming response
    return {
        "id": str(uuid.uuid4()),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "fastapi-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"Processed {len(request.messages)} messages with temp={request.temperature}",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": sum(len(m.content.split()) for m in request.messages),
            "completion_tokens": 20,
            "total_tokens": sum(len(m.content.split()) for m in request.messages) + 20,
        },
    }

@app.post("/chat/stream", tags=["Chat"])
async def chat_stream(request: ChatRequest):
    """Dedicated streaming chat endpoint."""
    async def event_generator():
        for i in range(10):
            data = {
                "id": f"chunk-{i}",
                "delta": {"content": f"Word{i} "},
                "index": i,
                "finish_reason": None if i < 9 else "stop",
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.15)
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )

# ============================================================================
# SERVER-SENT EVENTS (SSE) ENDPOINTS
# ============================================================================
@app.get("/sse/events", tags=["SSE"])
async def sse_events(request: Request):
    """
    Server-Sent Events endpoint for real-time updates.
    
    Clients can subscribe to receive continuous updates.
    """
    async def event_stream():
        counter = 0
        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected")
                break
            
            event_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "counter": counter,
                "message": f"Event #{counter}",
                "data": {"value": counter * 10},
            }
            
            yield {
                "event": "update",
                "id": str(counter),
                "data": json.dumps(event_data),
            }
            
            counter += 1
            await asyncio.sleep(2)
    
    return EventSourceResponse(event_stream())

@app.get("/sse/notifications", tags=["SSE"])
async def sse_notifications(
    request: Request,
    user_id: str = Query(..., description="User ID to receive notifications"),
):
    """SSE endpoint for user-specific notifications."""
    async def notification_stream():
        notification_types = ["info", "warning", "success", "error"]
        counter = 0
        
        while True:
            if await request.is_disconnected():
                break
            
            notification = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "type": notification_types[counter % len(notification_types)],
                "title": f"Notification #{counter}",
                "message": f"This is a {notification_types[counter % len(notification_types)]} notification",
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            yield {
                "event": "notification",
                "id": notification["id"],
                "data": json.dumps(notification),
            }
            
            counter += 1
            await asyncio.sleep(3)
    
    return EventSourceResponse(notification_stream())

@app.get("/sse/progress/{task_id}", tags=["SSE"])
async def sse_task_progress(request: Request, task_id: str):
    """SSE endpoint to stream task progress updates."""
    async def progress_stream():
        for progress in range(0, 101, 10):
            if await request.is_disconnected():
                break
            
            yield {
                "event": "progress",
                "id": str(progress),
                "data": json.dumps({
                    "task_id": task_id,
                    "progress": progress,
                    "status": "completed" if progress == 100 else "processing",
                    "message": f"Task {progress}% complete",
                }),
            }
            await asyncio.sleep(0.5)
    
    return EventSourceResponse(progress_stream())

# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================
class ConnectionManager:
    """WebSocket connection manager."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connected: {client_id}")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket disconnected: {client_id}")
    
    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)
    
    async def broadcast(self, message: str, exclude: Optional[str] = None):
        for client_id, connection in self.active_connections.items():
            if client_id != exclude:
                await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time bidirectional communication.
    
    Supports:
    - Personal messages
    - Broadcast messages
    - Ping/pong for connection health
    """
    await manager.connect(websocket, client_id)
    
    # Send welcome message
    await websocket.send_json({
        "type": "connection",
        "status": "connected",
        "client_id": client_id,
        "timestamp": datetime.utcnow().isoformat(),
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type", "message")
            
            if message_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
            
            elif message_type == "broadcast":
                await manager.broadcast(
                    json.dumps({
                        "type": "broadcast",
                        "from": client_id,
                        "content": data.get("content"),
                        "timestamp": datetime.utcnow().isoformat(),
                    }),
                    exclude=client_id,
                )
            
            elif message_type == "message":
                # Echo back the message with processing
                response = {
                    "type": "response",
                    "original": data.get("content"),
                    "processed": f"Received: {data.get('content', '')}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                await websocket.send_json(response)
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}",
                })
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        await manager.broadcast(
            json.dumps({
                "type": "system",
                "message": f"Client {client_id} disconnected",
            })
        )

@app.websocket("/ws/chat/{room_id}")
async def websocket_chat_room(websocket: WebSocket, room_id: str):
    """WebSocket chat room endpoint."""
    client_id = str(uuid.uuid4())
    await manager.connect(websocket, f"{room_id}:{client_id}")
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Broadcast to all clients in the same room
            for conn_id, conn in manager.active_connections.items():
                if conn_id.startswith(f"{room_id}:"):
                    await conn.send_json({
                        "room_id": room_id,
                        "sender_id": client_id,
                        "content": data.get("content"),
                        "timestamp": datetime.utcnow().isoformat(),
                    })
    
    except WebSocketDisconnect:
        manager.disconnect(f"{room_id}:{client_id}")

# ============================================================================
# BACKGROUND TASKS ENDPOINTS
# ============================================================================
async def process_background_task(task_id: str, task_type: str, payload: Dict):
    """Background task processor."""
    logger.info(f"Starting background task: {task_id}")
    
    # Update task status to processing
    if task_id in tasks_db:
        tasks_db[task_id].status = StatusEnum.PROCESSING
    
    # Simulate processing
    await asyncio.sleep(5)
    
    # Complete the task
    if task_id in tasks_db:
        tasks_db[task_id].status = StatusEnum.COMPLETED
        tasks_db[task_id].result = {
            "task_type": task_type,
            "processed_payload": payload,
            "completed_at": datetime.utcnow().isoformat(),
        }
    
    logger.info(f"Completed background task: {task_id}")

@app.post("/tasks", tags=["Tasks"], response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_task(
    task: TaskCreate,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key),
):
    """Create a background task for async processing."""
    task_id = str(uuid.uuid4())
    task_response = TaskResponse(
        task_id=task_id,
        status=StatusEnum.PENDING,
        created_at=datetime.utcnow().isoformat(),
        result=None,
    )
    tasks_db[task_id] = task_response
    
    # Add background task
    background_tasks.add_task(
        process_background_task,
        task_id,
        task.task_type,
        task.payload,
    )
    
    return task_response

@app.get("/tasks/{task_id}", tags=["Tasks"], response_model=TaskResponse)
async def get_task(task_id: str, api_key: str = Depends(verify_api_key)):
    """Get task status and result."""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks_db[task_id]

@app.get("/tasks", tags=["Tasks"], response_model=List[TaskResponse])
async def list_tasks(
    status_filter: Optional[StatusEnum] = Query(None, description="Filter by status"),
    api_key: str = Depends(verify_api_key),
):
    """List all tasks with optional status filter."""
    tasks = list(tasks_db.values())
    if status_filter:
        tasks = [t for t in tasks if t.status == status_filter]
    return tasks

# ============================================================================
# OPENAPI TOOL SPECIFICATIONS FOR AI AGENTS
# ============================================================================

# Define available tools
AVAILABLE_TOOLS: Dict[str, ToolSpec] = {
    "search_database": ToolSpec(
        name="search_database",
        description="Search the database for records matching the query criteria",
        parameters={
            "query": ToolParameter(
                type="string",
                description="Search query string",
                required=True,
            ),
            "table": ToolParameter(
                type="string",
                description="Table to search in",
                required=True,
                enum=["users", "products", "orders", "transactions"],
            ),
            "limit": ToolParameter(
                type="integer",
                description="Maximum number of results to return",
                required=False,
            ),
        },
    ),
    "send_email": ToolSpec(
        name="send_email",
        description="Send an email to specified recipients",
        parameters={
            "to": ToolParameter(
                type="string",
                description="Recipient email address",
                required=True,
            ),
            "subject": ToolParameter(
                type="string",
                description="Email subject line",
                required=True,
            ),
            "body": ToolParameter(
                type="string",
                description="Email body content",
                required=True,
            ),
            "html": ToolParameter(
                type="boolean",
                description="Whether the body is HTML formatted",
                required=False,
            ),
        },
    ),
    "create_calendar_event": ToolSpec(
        name="create_calendar_event",
        description="Create a new calendar event",
        parameters={
            "title": ToolParameter(
                type="string",
                description="Event title",
                required=True,
            ),
            "start_time": ToolParameter(
                type="string",
                description="Event start time in ISO 8601 format",
                required=True,
            ),
            "end_time": ToolParameter(
                type="string",
                description="Event end time in ISO 8601 format",
                required=True,
            ),
            "attendees": ToolParameter(
                type="array",
                description="List of attendee email addresses",
                required=False,
            ),
            "description": ToolParameter(
                type="string",
                description="Event description",
                required=False,
            ),
        },
    ),
    "get_weather": ToolSpec(
        name="get_weather",
        description="Get current weather information for a location",
        parameters={
            "location": ToolParameter(
                type="string",
                description="City name or coordinates",
                required=True,
            ),
            "units": ToolParameter(
                type="string",
                description="Temperature units",
                required=False,
                enum=["celsius", "fahrenheit"],
            ),
        },
    ),
    "execute_code": ToolSpec(
        name="execute_code",
        description="Execute code in a sandboxed environment",
        parameters={
            "code": ToolParameter(
                type="string",
                description="Code to execute",
                required=True,
            ),
            "language": ToolParameter(
                type="string",
                description="Programming language",
                required=True,
                enum=["python", "javascript", "bash"],
            ),
            "timeout": ToolParameter(
                type="integer",
                description="Execution timeout in seconds",
                required=False,
            ),
        },
    ),
    "query_knowledge_base": ToolSpec(
        name="query_knowledge_base",
        description="Query the knowledge base for relevant information",
        parameters={
            "query": ToolParameter(
                type="string",
                description="Natural language query",
                required=True,
            ),
            "top_k": ToolParameter(
                type="integer",
                description="Number of results to return",
                required=False,
            ),
            "filters": ToolParameter(
                type="object",
                description="Metadata filters for the search",
                required=False,
            ),
        },
    ),
}

@app.get("/tools", tags=["Tools"], response_model=Dict[str, ToolSpec])
async def list_tools():
    """
    List all available tools with their specifications.
    
    Returns OpenAPI-compatible tool definitions for AI agent integration.
    """
    return AVAILABLE_TOOLS

@app.get("/tools/{tool_name}", tags=["Tools"], response_model=ToolSpec)
async def get_tool_spec(tool_name: str):
    """Get specification for a specific tool."""
    if tool_name not in AVAILABLE_TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    return AVAILABLE_TOOLS[tool_name]

@app.get("/tools/openapi/schema", tags=["Tools"])
async def get_openapi_tools_schema():
    """
    Get OpenAPI-formatted tools schema for AI agent integration.
    
    This schema is compatible with:
    - OpenAI Function Calling
    - Claude Tool Use
    - Google Gemini Function Calling
    - LangChain Tools
    """
    openapi_tools = []
    
    for tool_name, tool_spec in AVAILABLE_TOOLS.items():
        properties = {}
        required = []
        
        for param_name, param in tool_spec.parameters.items():
            prop = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param_name] = prop
            
            if param.required:
                required.append(param_name)
        
        openapi_tool = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_spec.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
        openapi_tools.append(openapi_tool)
    
    return {"tools": openapi_tools}

@app.post("/tools/execute", tags=["Tools"], response_model=ToolExecutionResponse)
async def execute_tool(
    request: ToolExecutionRequest,
    api_key: str = Depends(verify_api_key),
):
    """
    Execute a tool with the provided parameters.
    
    This endpoint processes tool calls from AI agents.
    """
    start_time = time.time()
    
    if request.tool_name not in AVAILABLE_TOOLS:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{request.tool_name}' not found",
        )
    
    tool_spec = AVAILABLE_TOOLS[request.tool_name]
    
    # Validate required parameters
    for param_name, param in tool_spec.parameters.items():
        if param.required and param_name not in request.parameters:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required parameter: {param_name}",
            )
    
    # Simulate tool execution
    await asyncio.sleep(0.1)  # Simulate processing time
    
    # Mock results based on tool type
    mock_results = {
        "search_database": {"records": [{"id": 1, "name": "Sample Record"}], "total": 1},
        "send_email": {"message_id": str(uuid.uuid4()), "status": "sent"},
        "create_calendar_event": {"event_id": str(uuid.uuid4()), "status": "created"},
        "get_weather": {"temperature": 22, "condition": "sunny", "humidity": 45},
        "execute_code": {"output": "Hello, World!", "exit_code": 0},
        "query_knowledge_base": {"results": [{"text": "Sample knowledge", "score": 0.95}]},
    }
    
    execution_time = (time.time() - start_time) * 1000
    
    return ToolExecutionResponse(
        tool_name=request.tool_name,
        success=True,
        result=mock_results.get(request.tool_name, {"status": "completed"}),
        execution_time_ms=round(execution_time, 2),
    )

# ============================================================================
# FILE UPLOAD/DOWNLOAD ENDPOINTS
# ============================================================================
@app.post("/files/upload", tags=["Files"])
async def upload_file(
    file: UploadFile = File(...),
    description: str = Form(None),
    api_key: str = Depends(verify_api_key),
):
    """Upload a file with optional description."""
    content = await file.read()
    file_id = str(uuid.uuid4())
    
    return {
        "file_id": file_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "description": description,
        "uploaded_at": datetime.utcnow().isoformat(),
    }

@app.post("/files/upload/multiple", tags=["Files"])
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    api_key: str = Depends(verify_api_key),
):
    """Upload multiple files at once."""
    results = []
    for file in files:
        content = await file.read()
        results.append({
            "file_id": str(uuid.uuid4()),
            "filename": file.filename,
            "content_type": file.content_type,
            "size_bytes": len(content),
        })
    return {"files": results, "total": len(results)}

# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================
@app.get("/echo", tags=["Utilities"])
async def echo(
    message: str = Query(..., description="Message to echo"),
    delay: float = Query(0, ge=0, le=10, description="Response delay in seconds"),
):
    """Echo endpoint with optional delay for testing."""
    if delay > 0:
        await asyncio.sleep(delay)
    return {"echo": message, "delay": delay, "timestamp": datetime.utcnow().isoformat()}

@app.post("/webhook", tags=["Utilities"])
async def webhook_receiver(request: Request):
    """Generic webhook receiver for testing integrations."""
    body = await request.body()
    headers = dict(request.headers)
    
    return {
        "received": True,
        "method": request.method,
        "path": str(request.url.path),
        "headers": headers,
        "body_size": len(body),
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.get("/redirect", tags=["Utilities"])
async def redirect_example(url: str = Query(..., description="URL to redirect to")):
    """Redirect to specified URL."""
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)

# ============================================================================
# ERROR HANDLERS
# ============================================================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "path": str(request.url.path),
                "timestamp": datetime.utcnow().isoformat(),
            }
        },
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "path": str(request.url.path),
                "timestamp": datetime.utcnow().isoformat(),
            }
        },
    )

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
        access_log=True,
    )