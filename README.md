# FastAPI Async Utilities API

A comprehensive FastAPI application demonstrating async capabilities, Server-Sent Events (SSE), streaming responses, WebSockets, and various utility endpoints. Ready for deployment on Google Cloud Run.

## 🚀 Features

### 📡 Server-Sent Events (SSE)
| Endpoint | Description |
|----------|-------------|
| `GET /events` | Basic SSE - streams 10 events with 1s intervals |
| `GET /sse/clock` | Live clock - infinite stream of current time |
| `GET /sse/stock/{symbol}` | Simulated stock price updates |
| `GET /sse/progress?steps=N` | Progress bar simulation |

### 🔄 Streaming Responses
| Endpoint | Description |
|----------|-------------|
| `GET /stream/json?count=N` | Streams large JSON array |
| `GET /stream/csv?rows=N` | Streams CSV file data |
| `GET /stream/logs` | Simulated live log stream |
| `GET /stream/ndjson?count=N` | Newline-delimited JSON (NDJSON) |

### 🔌 WebSocket Endpoints
| Endpoint | Description |
|----------|-------------|
| `WS /ws/chat` | Multi-client chat with broadcast |
| `WS /ws/echo` | Echo back messages |
| `WS /ws/ticker` | Auto-sends random data every second |

### 🛠️ Utility Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /utils/uuid?count=N` | Generate random UUIDs |
| `GET /utils/hash?text=X&algorithm=sha256` | Hash text (md5, sha1, sha256, sha512) |
| `GET /utils/base64/encode?text=X` | Base64 encode |
| `GET /utils/base64/decode?encoded=X` | Base64 decode |
| `GET /utils/random?type=number` | Random data generator |
| `GET /utils/time?format=iso` | Current time in various formats |
| `GET /utils/delay?seconds=N` | Delayed response for testing async |
| `POST /utils/background-task` | Trigger async background tasks |

### 📖 General Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /` | API info with all endpoints |
| `GET /health` | Health check |
| `GET /demo` | Interactive HTML demo page |
| `GET /docs` | Swagger UI documentation |
| `GET /redoc` | ReDoc documentation |

## 📦 Installation

### Local Development

```bash
# Clone the repository
git clone https://github.com/Yash-Kavaiya/cloud-run-fastapi-async.git
cd cloud-run-fastapi-async

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Docker

```bash
# Build the image
docker build -t fastapi-async-utils .

# Run the container
docker run -p 8000:8000 fastapi-async-utils
```

## 🧪 Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest test_main.py -v
```

## 📝 Usage Examples

### SSE with curl

```bash
# Basic events
curl -N http://localhost:8000/events

# Live clock
curl -N http://localhost:8000/sse/clock

# Stock ticker
curl -N http://localhost:8000/sse/stock/AAPL

# Progress bar
curl -N http://localhost:8000/sse/progress?steps=10
```

### Streaming with curl

```bash
# Stream JSON
curl http://localhost:8000/stream/json?count=10

# Stream CSV
curl http://localhost:8000/stream/csv?rows=100 -o data.csv

# Stream logs
curl -N http://localhost:8000/stream/logs

# NDJSON stream
curl http://localhost:8000/stream/ndjson?count=10
```

### Utilities with curl

```bash
# Generate UUIDs
curl "http://localhost:8000/utils/uuid?count=5"

# Hash text
curl "http://localhost:8000/utils/hash?text=hello&algorithm=sha256"

# Base64 encode
curl "http://localhost:8000/utils/base64/encode?text=HelloWorld"

# Random data
curl "http://localhost:8000/utils/random?type=string&length=20"

# Current time
curl "http://localhost:8000/utils/time?format=human"

# Delayed response
curl "http://localhost:8000/utils/delay?seconds=2"
```

### WebSocket with websocat

```bash
# Install websocat
# brew install websocat  # macOS
# cargo install websocat  # Rust

# Echo endpoint
websocat ws://localhost:8000/ws/echo

# Ticker endpoint
websocat ws://localhost:8000/ws/ticker
```

### JavaScript SSE Example

```javascript
const eventSource = new EventSource('http://localhost:8000/events');

eventSource.onmessage = (event) => {
    console.log('Received:', event.data);
};

eventSource.addEventListener('complete', (event) => {
    console.log('Stream completed');
    eventSource.close();
});
```

### JavaScript WebSocket Example

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/echo');

ws.onopen = () => {
    console.log('Connected');
    ws.send('Hello, server!');
};

ws.onmessage = (event) => {
    console.log('Received:', event.data);
};
```

## ☁️ Deploy to Google Cloud Run

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID

# Build and deploy
gcloud run deploy fastapi-async-utils \
    --source . \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated
```

## 📁 Project Structure

```
cloud-run-fastapi-async/
├── main.py              # FastAPI application
├── test_main.py         # Test suite
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker configuration
└── README.md            # This file
```

## 🔧 Requirements

- Python 3.9+
- FastAPI
- Uvicorn
- SSE-Starlette
- Websockets

## 📄 License

MIT License

## 👤 Author

**Yash Kavaiya**
- GitHub: [@Yash-Kavaiya](https://github.com/Yash-Kavaiya)