"""
Test suite for FastAPI Async Utilities API
Run with: pytest test_main.py -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient
from main import app
import json

# Sync client for basic tests
client = TestClient(app)


# ==================== General Endpoints ====================

class TestGeneralEndpoints:
    """Tests for general endpoints."""

    def test_root_endpoint(self):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "endpoints" in data
        assert "sse" in data["endpoints"]
        assert "streaming" in data["endpoints"]
        assert "websocket" in data["endpoints"]
        assert "utilities" in data["endpoints"]

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_demo_page(self):
        """Test demo HTML page is served."""
        response = client.get("/demo")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "FastAPI Streaming Demo" in response.text


# ==================== Utility Endpoints ====================

class TestUtilityEndpoints:
    """Tests for utility endpoints."""

    def test_uuid_single(self):
        """Test generating a single UUID."""
        response = client.get("/utils/uuid")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["uuids"]) == 1

    def test_uuid_multiple(self):
        """Test generating multiple UUIDs."""
        response = client.get("/utils/uuid?count=5")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 5
        assert len(data["uuids"]) == 5
        # Ensure all UUIDs are unique
        assert len(set(data["uuids"])) == 5

    def test_hash_sha256(self):
        """Test SHA256 hashing."""
        response = client.get("/utils/hash?text=hello&algorithm=sha256")
        assert response.status_code == 200
        data = response.json()
        assert data["original"] == "hello"
        assert data["algorithm"] == "sha256"
        # Known SHA256 hash of "hello"
        assert data["hash"] == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    def test_hash_md5(self):
        """Test MD5 hashing."""
        response = client.get("/utils/hash?text=hello&algorithm=md5")
        assert response.status_code == 200
        data = response.json()
        assert data["algorithm"] == "md5"
        # Known MD5 hash of "hello"
        assert data["hash"] == "5d41402abc4b2a76b9719d911017c592"

    def test_hash_invalid_algorithm(self):
        """Test hash with invalid algorithm returns error."""
        response = client.get("/utils/hash?text=hello&algorithm=invalid")
        assert response.status_code == 400

    def test_base64_encode(self):
        """Test Base64 encoding."""
        response = client.get("/utils/base64/encode?text=HelloWorld")
        assert response.status_code == 200
        data = response.json()
        assert data["original"] == "HelloWorld"
        assert data["encoded"] == "SGVsbG9Xb3JsZA=="

    def test_base64_decode(self):
        """Test Base64 decoding."""
        response = client.get("/utils/base64/decode?encoded=SGVsbG9Xb3JsZA==")
        assert response.status_code == 200
        data = response.json()
        assert data["decoded"] == "HelloWorld"

    def test_base64_decode_invalid(self):
        """Test Base64 decode with invalid input."""
        response = client.get("/utils/base64/decode?encoded=invalid!!!")
        assert response.status_code == 400

    def test_random_number(self):
        """Test random number generation."""
        response = client.get("/utils/random?type=number&min_val=1&max_val=10")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "number"
        assert 1 <= data["value"] <= 10

    def test_random_string(self):
        """Test random string generation."""
        response = client.get("/utils/random?type=string&length=20")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "string"
        assert len(data["value"]) == 20

    def test_random_boolean(self):
        """Test random boolean generation."""
        response = client.get("/utils/random?type=boolean")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "boolean"
        assert isinstance(data["value"], bool)

    def test_random_list(self):
        """Test random list generation."""
        response = client.get("/utils/random?type=list&length=5")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "list"
        assert len(data["value"]) == 5

    def test_random_invalid_type(self):
        """Test random with invalid type."""
        response = client.get("/utils/random?type=invalid")
        assert response.status_code == 400

    def test_time_iso(self):
        """Test time in ISO format."""
        response = client.get("/utils/time?format=iso")
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "iso"
        assert "T" in data["time"]  # ISO format contains 'T'

    def test_time_unix(self):
        """Test time in Unix timestamp."""
        response = client.get("/utils/time?format=unix")
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "unix"
        assert isinstance(data["time"], float)

    def test_time_human(self):
        """Test time in human readable format."""
        response = client.get("/utils/time?format=human")
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "human"

    def test_time_invalid_format(self):
        """Test time with invalid format."""
        response = client.get("/utils/time?format=invalid")
        assert response.status_code == 400


# ==================== Streaming Endpoints ====================

class TestStreamingEndpoints:
    """Tests for streaming endpoints."""

    def test_stream_json(self):
        """Test JSON streaming."""
        response = client.get("/stream/json?count=5")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        data = response.json()
        assert len(data) == 5
        for item in data:
            assert "id" in item
            assert "uuid" in item
            assert "data" in item

    def test_stream_csv(self):
        """Test CSV streaming."""
        response = client.get("/stream/csv?rows=5")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        lines = response.text.strip().split("\n")
        assert len(lines) == 6  # Header + 5 rows
        assert "id,name,email,score,created_at" in lines[0]

    def test_stream_ndjson(self):
        """Test NDJSON streaming."""
        response = client.get("/stream/ndjson?count=5")
        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        assert len(lines) == 5
        for line in lines:
            item = json.loads(line)
            assert "id" in item
            assert "event" in item
            assert "value" in item


# ==================== SSE Endpoints ====================

class TestSSEEndpoints:
    """Tests for SSE endpoints."""

    def test_events_endpoint(self):
        """Test basic SSE events endpoint."""
        # SSE returns a stream, we just verify it starts correctly
        with client.stream("GET", "/events") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            # Read first chunk
            for chunk in response.iter_lines():
                if chunk:
                    assert "event:" in chunk or "data:" in chunk
                    break

    def test_sse_clock_endpoint(self):
        """Test SSE clock endpoint."""
        with client.stream("GET", "/sse/clock") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

    def test_sse_stock_endpoint(self):
        """Test SSE stock endpoint."""
        with client.stream("GET", "/sse/stock/AAPL") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

    def test_sse_progress_endpoint(self):
        """Test SSE progress endpoint."""
        with client.stream("GET", "/sse/progress?steps=5") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]


# ==================== WebSocket Endpoints ====================

class TestWebSocketEndpoints:
    """Tests for WebSocket endpoints."""

    def test_websocket_echo(self):
        """Test WebSocket echo endpoint."""
        with client.websocket_connect("/ws/echo") as websocket:
            websocket.send_text("Hello")
            data = websocket.receive_text()
            assert data == "Echo: Hello"

    def test_websocket_echo_multiple(self):
        """Test WebSocket echo with multiple messages."""
        with client.websocket_connect("/ws/echo") as websocket:
            messages = ["First", "Second", "Third"]
            for msg in messages:
                websocket.send_text(msg)
                data = websocket.receive_text()
                assert data == f"Echo: {msg}"

    def test_websocket_ticker(self):
        """Test WebSocket ticker endpoint."""
        with client.websocket_connect("/ws/ticker") as websocket:
            data = websocket.receive_json()
            assert "value" in data
            assert "timestamp" in data
            assert isinstance(data["value"], int)

    def test_websocket_chat(self):
        """Test WebSocket chat endpoint."""
        with client.websocket_connect("/ws/chat") as websocket:
            websocket.send_text("Hello chat!")
            data = websocket.receive_text()
            parsed = json.loads(data)
            assert "message" in parsed
            assert parsed["message"] == "Hello chat!"
            assert "timestamp" in parsed
            assert "connections" in parsed


# ==================== Async Tests ====================

@pytest.mark.asyncio
class TestAsyncEndpoints:
    """Async tests for endpoints."""

    async def test_delay_endpoint(self):
        """Test delayed response endpoint."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/utils/delay?seconds=0.1")
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert data["requested_delay"] == 0.1

    async def test_background_task(self):
        """Test background task endpoint."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/utils/background-task?message=test")
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Background task triggered"
            assert data["task_message"] == "test"


# ==================== Edge Cases ====================

class TestEdgeCases:
    """Tests for edge cases and validation."""

    def test_uuid_max_count(self):
        """Test UUID with max count."""
        response = client.get("/utils/uuid?count=100")
        assert response.status_code == 200
        assert len(response.json()["uuids"]) == 100

    def test_uuid_exceeds_max(self):
        """Test UUID count exceeding max returns validation error."""
        response = client.get("/utils/uuid?count=101")
        assert response.status_code == 422  # Validation error

    def test_stream_json_max(self):
        """Test JSON stream with large count."""
        response = client.get("/stream/json?count=100")
        assert response.status_code == 200
        assert len(response.json()) == 100

    def test_delay_min(self):
        """Test minimum delay."""
        response = client.get("/utils/delay?seconds=0.1")
        assert response.status_code == 200

    def test_delay_exceeds_max(self):
        """Test delay exceeding max returns validation error."""
        response = client.get("/utils/delay?seconds=31")
        assert response.status_code == 422


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
