from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, HTMLResponse
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import random
import hashlib
import base64
import uuid
from datetime import datetime
from typing import Optional

app = FastAPI(
    title="FastAPI Async Utilities",
    description="A collection of async utilities with SSE and streaming features",
    version="1.0.0"
)

# ==================== SSE (Server-Sent Events) ====================

async def event_generator():
    """Basic event generator for SSE."""
    for i in range(10):
        yield {"event": "message", "data": json.dumps({"count": i + 1, "timestamp": datetime.now().isoformat()})}
        await asyncio.sleep(1)
    yield {"event": "complete", "data": json.dumps({"message": "Stream completed"})}

@app.get("/events", tags=["SSE"])
async def events():
    """Basic SSE endpoint - streams 10 events with 1 second intervals."""
    return EventSourceResponse(event_generator())


async def live_clock_generator():
    """Generates live clock updates every second."""
    while True:
        yield {
            "event": "clock",
            "data": json.dumps({
                "time": datetime.now().strftime("%H:%M:%S"),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "timestamp": datetime.now().timestamp()
            })
        }
        await asyncio.sleep(1)

@app.get("/sse/clock", tags=["SSE"])
async def sse_clock():
    """Live clock SSE - streams current time every second (infinite stream)."""
    return EventSourceResponse(live_clock_generator())


async def stock_price_generator(symbol: str):
    """Simulates stock price updates."""
    base_price = random.uniform(100, 500)
    for _ in range(50):
        change = random.uniform(-5, 5)
        base_price = max(1, base_price + change)
        yield {
            "event": "price_update",
            "data": json.dumps({
                "symbol": symbol.upper(),
                "price": round(base_price, 2),
                "change": round(change, 2),
                "timestamp": datetime.now().isoformat()
            })
        }
        await asyncio.sleep(0.5)

@app.get("/sse/stock/{symbol}", tags=["SSE"])
async def sse_stock_prices(symbol: str):
    """Simulated stock price SSE - streams price updates for a symbol."""
    return EventSourceResponse(stock_price_generator(symbol))


async def progress_generator(total_steps: int):
    """Simulates a progress bar."""
    for step in range(1, total_steps + 1):
        progress = (step / total_steps) * 100
        yield {
            "event": "progress",
            "data": json.dumps({
                "step": step,
                "total": total_steps,
                "percent": round(progress, 1),
                "status": "completed" if step == total_steps else "in_progress"
            })
        }
        await asyncio.sleep(0.3)

@app.get("/sse/progress", tags=["SSE"])
async def sse_progress(steps: int = Query(default=20, ge=1, le=100)):
    """Progress bar SSE - simulates a task with progress updates."""
    return EventSourceResponse(progress_generator(steps))


# ==================== Streaming Responses ====================

async def generate_large_data(num_items: int):
    """Generates large JSON data in chunks."""
    yield "["
    for i in range(num_items):
        item = {
            "id": i + 1,
            "uuid": str(uuid.uuid4()),
            "data": f"Item {i + 1} data",
            "timestamp": datetime.now().isoformat()
        }
        if i > 0:
            yield ","
        yield json.dumps(item)
        await asyncio.sleep(0.01)  # Small delay to simulate processing
    yield "]"

@app.get("/stream/json", tags=["Streaming"])
async def stream_json(count: int = Query(default=100, ge=1, le=10000)):
    """Streams a large JSON array of items."""
    return StreamingResponse(
        generate_large_data(count),
        media_type="application/json"
    )


async def generate_csv_data(rows: int):
    """Generates CSV data row by row."""
    yield "id,name,email,score,created_at\n"
    for i in range(1, rows + 1):
        row = f"{i},User{i},user{i}@example.com,{random.randint(0, 100)},{datetime.now().isoformat()}\n"
        yield row
        await asyncio.sleep(0.01)

@app.get("/stream/csv", tags=["Streaming"])
async def stream_csv(rows: int = Query(default=100, ge=1, le=10000)):
    """Streams CSV data with specified number of rows."""
    return StreamingResponse(
        generate_csv_data(rows),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=data.csv"}
    )


async def generate_log_stream():
    """Simulates a live log stream."""
    log_levels = ["INFO", "DEBUG", "WARNING", "ERROR"]
    log_messages = [
        "Request received", "Processing data", "Database query executed",
        "Cache hit", "Cache miss", "Connection established", "Task completed",
        "Validation passed", "File uploaded", "Email sent"
    ]
    
    for i in range(50):
        level = random.choice(log_levels)
        message = random.choice(log_messages)
        log_line = f"[{datetime.now().isoformat()}] [{level}] {message}\n"
        yield log_line
        await asyncio.sleep(random.uniform(0.1, 0.5))

@app.get("/stream/logs", tags=["Streaming"])
async def stream_logs():
    """Streams simulated log entries in real-time."""
    return StreamingResponse(
        generate_log_stream(),
        media_type="text/plain"
    )


async def generate_ndjson(count: int):
    """Generates newline-delimited JSON (NDJSON)."""
    for i in range(count):
        item = {
            "id": i + 1,
            "event": f"event_{i + 1}",
            "value": random.randint(1, 1000),
            "timestamp": datetime.now().isoformat()
        }
        yield json.dumps(item) + "\n"
        await asyncio.sleep(0.05)

@app.get("/stream/ndjson", tags=["Streaming"])
async def stream_ndjson(count: int = Query(default=50, ge=1, le=1000)):
    """Streams newline-delimited JSON (NDJSON) format."""
    return StreamingResponse(
        generate_ndjson(count),
        media_type="application/x-ndjson"
    )


# ==================== WebSocket ====================

class ConnectionManager:
    """Manages WebSocket connections."""
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket chat endpoint - broadcasts messages to all connected clients."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.dumps({
                "message": data,
                "timestamp": datetime.now().isoformat(),
                "connections": len(manager.active_connections)
            })
            await manager.broadcast(message)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/echo")
async def websocket_echo(websocket: WebSocket):
    """WebSocket echo endpoint - echoes back whatever is sent."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/ticker")
async def websocket_ticker(websocket: WebSocket):
    """WebSocket ticker - sends random data every second."""
    await websocket.accept()
    try:
        while True:
            data = {
                "value": random.randint(1, 100),
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send_json(data)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass


# ==================== Utility Endpoints ====================

@app.get("/", tags=["General"])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "FastAPI Async Utilities API",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "sse": ["/events", "/sse/clock", "/sse/stock/{symbol}", "/sse/progress"],
            "streaming": ["/stream/json", "/stream/csv", "/stream/logs", "/stream/ndjson"],
            "websocket": ["/ws/chat", "/ws/echo", "/ws/ticker"],
            "utilities": ["/utils/uuid", "/utils/hash", "/utils/base64", "/utils/random", "/utils/time", "/utils/delay"]
        }
    }


@app.get("/health", tags=["General"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/utils/uuid", tags=["Utilities"])
async def generate_uuid(count: int = Query(default=1, ge=1, le=100)):
    """Generate random UUIDs."""
    return {
        "uuids": [str(uuid.uuid4()) for _ in range(count)],
        "count": count
    }


@app.get("/utils/hash", tags=["Utilities"])
async def hash_text(
    text: str = Query(..., description="Text to hash"),
    algorithm: str = Query(default="sha256", description="Hash algorithm (md5, sha1, sha256, sha512)")
):
    """Hash text using specified algorithm."""
    algorithms = {
        "md5": hashlib.md5,
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512
    }
    
    if algorithm not in algorithms:
        raise HTTPException(status_code=400, detail=f"Unsupported algorithm. Use: {list(algorithms.keys())}")
    
    hash_obj = algorithms[algorithm](text.encode())
    return {
        "original": text,
        "algorithm": algorithm,
        "hash": hash_obj.hexdigest()
    }


@app.get("/utils/base64/encode", tags=["Utilities"])
async def base64_encode(text: str = Query(..., description="Text to encode")):
    """Encode text to Base64."""
    encoded = base64.b64encode(text.encode()).decode()
    return {"original": text, "encoded": encoded}


@app.get("/utils/base64/decode", tags=["Utilities"])
async def base64_decode(encoded: str = Query(..., description="Base64 string to decode")):
    """Decode Base64 to text."""
    try:
        decoded = base64.b64decode(encoded).decode()
        return {"encoded": encoded, "decoded": decoded}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Base64 string: {str(e)}")


@app.get("/utils/random", tags=["Utilities"])
async def random_data(
    type: str = Query(default="number", description="Type: number, string, boolean, list"),
    min_val: int = Query(default=0, description="Min value for numbers"),
    max_val: int = Query(default=100, description="Max value for numbers"),
    length: int = Query(default=10, ge=1, le=100, description="Length for strings/lists")
):
    """Generate random data of various types."""
    if type == "number":
        return {"type": type, "value": random.randint(min_val, max_val)}
    elif type == "float":
        return {"type": type, "value": random.uniform(min_val, max_val)}
    elif type == "string":
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        return {"type": type, "value": "".join(random.choice(chars) for _ in range(length))}
    elif type == "boolean":
        return {"type": type, "value": random.choice([True, False])}
    elif type == "list":
        return {"type": type, "value": [random.randint(min_val, max_val) for _ in range(length)]}
    else:
        raise HTTPException(status_code=400, detail="Invalid type. Use: number, float, string, boolean, list")


@app.get("/utils/time", tags=["Utilities"])
async def current_time(
    format: str = Query(default="iso", description="Format: iso, unix, human")
):
    """Get current time in various formats."""
    now = datetime.now()
    
    if format == "iso":
        return {"format": format, "time": now.isoformat()}
    elif format == "unix":
        return {"format": format, "time": now.timestamp()}
    elif format == "human":
        return {"format": format, "time": now.strftime("%B %d, %Y at %I:%M:%S %p")}
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use: iso, unix, human")


@app.get("/utils/delay", tags=["Utilities"])
async def delayed_response(
    seconds: float = Query(default=1.0, ge=0.1, le=30, description="Delay in seconds")
):
    """Returns a response after a specified delay (for testing async behavior)."""
    await asyncio.sleep(seconds)
    return {
        "message": f"Response after {seconds} seconds delay",
        "requested_delay": seconds,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/utils/headers", tags=["Utilities"])
async def echo_headers():
    """Echo request headers (useful for debugging)."""
    from fastapi import Request
    # This is a simplified version - full implementation would use Request dependency
    return {"message": "Visit /docs to see this endpoint with full header echo using Request injection"}


# Background task example
async def log_task(message: str):
    """Simulated background task."""
    await asyncio.sleep(2)
    print(f"Background task completed: {message}")

@app.post("/utils/background-task", tags=["Utilities"])
async def trigger_background_task(
    background_tasks: BackgroundTasks,
    message: str = Query(default="Hello", description="Message to process")
):
    """Trigger a background task that runs asynchronously."""
    background_tasks.add_task(log_task, message)
    return {
        "message": "Background task triggered",
        "task_message": message,
        "timestamp": datetime.now().isoformat()
    }


# ==================== Demo HTML Page ====================

@app.get("/demo", response_class=HTMLResponse, tags=["Demo"])
async def demo_page():
    """Interactive demo page to test SSE and WebSocket features."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>FastAPI Streaming Demo</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }
            .container { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
            .card { background: #16213e; padding: 20px; border-radius: 10px; }
            h1 { color: #e94560; }
            h3 { color: #0f3460; background: #e94560; padding: 10px; border-radius: 5px; }
            button { background: #e94560; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin: 5px; }
            button:hover { background: #ff6b6b; }
            .output { background: #0f3460; padding: 15px; border-radius: 5px; height: 200px; overflow-y: auto; font-family: monospace; font-size: 12px; }
            input { padding: 10px; border-radius: 5px; border: none; margin: 5px; }
        </style>
    </head>
    <body>
        <h1>🚀 FastAPI Async Streaming Demo</h1>
        <div class="container">
            <div class="card">
                <h3>📡 SSE Events</h3>
                <button onclick="startSSE('/events')">Start Events</button>
                <button onclick="startSSE('/sse/clock')">Live Clock</button>
                <button onclick="startSSE('/sse/progress?steps=10')">Progress</button>
                <button onclick="stopSSE()">Stop</button>
                <div class="output" id="sse-output"></div>
            </div>
            
            <div class="card">
                <h3>💬 WebSocket Echo</h3>
                <input type="text" id="ws-input" placeholder="Type a message...">
                <button onclick="sendWS()">Send</button>
                <button onclick="connectWS()">Connect</button>
                <div class="output" id="ws-output"></div>
            </div>
            
            <div class="card">
                <h3>📊 Stock Ticker SSE</h3>
                <input type="text" id="stock-symbol" placeholder="Symbol (e.g., AAPL)" value="AAPL">
                <button onclick="startStock()">Start Ticker</button>
                <button onclick="stopSSE()">Stop</button>
                <div class="output" id="stock-output"></div>
            </div>
            
            <div class="card">
                <h3>🔄 WebSocket Ticker</h3>
                <button onclick="startTicker()">Start</button>
                <button onclick="stopTicker()">Stop</button>
                <div class="output" id="ticker-output"></div>
            </div>
        </div>
        
        <script>
            let eventSource = null;
            let ws = null;
            let tickerWs = null;
            
            function log(id, msg) {
                const el = document.getElementById(id);
                el.innerHTML += msg + '<br>';
                el.scrollTop = el.scrollHeight;
            }
            
            function startSSE(url) {
                stopSSE();
                eventSource = new EventSource(url);
                eventSource.onmessage = (e) => log('sse-output', e.data);
                eventSource.onerror = () => log('sse-output', 'Connection error or closed');
            }
            
            function stopSSE() {
                if (eventSource) { eventSource.close(); eventSource = null; }
            }
            
            function startStock() {
                const symbol = document.getElementById('stock-symbol').value || 'AAPL';
                if (eventSource) eventSource.close();
                eventSource = new EventSource('/sse/stock/' + symbol);
                eventSource.addEventListener('price_update', (e) => {
                    const data = JSON.parse(e.data);
                    const color = data.change >= 0 ? '#4ade80' : '#f87171';
                    log('stock-output', `<span style="color:${color}">${data.symbol}: $${data.price} (${data.change >= 0 ? '+' : ''}${data.change})</span>`);
                });
            }
            
            function connectWS() {
                ws = new WebSocket('ws://' + location.host + '/ws/echo');
                ws.onopen = () => log('ws-output', 'Connected!');
                ws.onmessage = (e) => log('ws-output', e.data);
                ws.onclose = () => log('ws-output', 'Disconnected');
            }
            
            function sendWS() {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(document.getElementById('ws-input').value);
                } else {
                    log('ws-output', 'Not connected! Click Connect first.');
                }
            }
            
            function startTicker() {
                tickerWs = new WebSocket('ws://' + location.host + '/ws/ticker');
                tickerWs.onmessage = (e) => log('ticker-output', e.data);
            }
            
            function stopTicker() {
                if (tickerWs) { tickerWs.close(); tickerWs = null; }
            }
        </script>
    </body>
    </html>
    """