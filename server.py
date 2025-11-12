import os
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from fastapi import FastAPI, Request
from fastmcp import FastMCP, tool

app = FastMCP("ProductHunt MCP")

# ---------------------------------------------------
# Tool
# ---------------------------------------------------
@tool
def ph_posts(start: str, end: Optional[str] = None, first: int = 100) -> List[Dict[str, Any]]:
    token = os.getenv("PRODUCTHUNT_TOKEN", "")
    if not token:
        raise RuntimeError("PRODUCTHUNT_TOKEN missing")

    if not end:
        end = start
    start_dt = f"{start}T00:00:00Z"
    end_dt = f"{end}T23:59:59Z"

    query = """
    query ($start: DateTime!, $end: DateTime!, $first: Int!) {
      posts(postedAfter: $start, postedBefore: $end, first: $first, order: VOTES_COUNT) {
        edges { node { id name tagline votesCount createdAt website slug makers { name username } } }
      }
    }
    """
    res = requests.post(
        "https://api.producthunt.com/v2/api/graphql",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": query, "variables": {"start": start_dt, "end": end_dt, "first": first}},
        timeout=30,
    )
    res.raise_for_status()
    data = res.json()
    edges = data.get("data", {}).get("posts", {}).get("edges", [])
    return [
        {
            "id": n["id"],
            "name": n["name"],
            "tagline": n["tagline"],
            "votesCount": n["votesCount"],
            "createdAt": n["createdAt"],
            "website": n["website"],
            "slug": n["slug"],
            "makers": [{"name": m["name"], "username": m["username"]} for m in n.get("makers", [])],
        }
        for e in edges
        if (n := e.get("node"))
    ]

# ---------------------------------------------------
# Patch FastMCP HTTP transport to recover lost ?session=
# ---------------------------------------------------
from fastmcp.server.server import HTTPTransport

orig_asgi_app = HTTPTransport.asgi_app

async def patched_asgi_app(self, scope, receive, send):
    if scope["type"] == "http":
        # Try to manually parse query if proxy stripped it
        qs = scope.get("query_string", b"").decode()
        if "session=" not in qs and scope.get("path", "").startswith("/mcp"):
            raw_url = scope.get("raw_path", b"").decode()
            if "?" in raw_url:
                query = raw_url.split("?", 1)[1]
                scope["query_string"] = query.encode()
    return await orig_asgi_app(self, scope, receive, send)

HTTPTransport.asgi_app = patched_asgi_app

# ---------------------------------------------------
# Discovery + health
# ---------------------------------------------------
fa = FastAPI()

@app.mount_http_app(fa)
def _mount():
    pass

@fa.get("/.well-known/mcp.json")
def mcp_discovery():
    base = os.getenv("PUBLIC_BASE_URL", "https://causo-ph-mcp-railway-production.up.railway.app").rstrip("/")
    host = base.removeprefix("https://").removeprefix("http://")
    return {
        "servers": [{
            "name": "ProductHunt MCP",
            "sse_url": f"{base}/mcp",
            "ws_url":  f"wss://{host}/mcp/ws"
        }]
    }

@fa.get("/health")
def health():
    return {"ok": True}

# ---------------------------------------------------
# WebSocket compatibility patch (Uvicorn >= 0.34)
# ---------------------------------------------------
try:
    import uvicorn.config as _cfg
    if "websockets" not in _cfg.WS_PROTOCOLS:
        _cfg.WS_PROTOCOLS["websockets"] = "uvicorn.protocols.websockets.websockets_impl:WebSocketProtocol"
except Exception:
    pass

# ---------------------------------------------------
# Run
# ---------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(
        transport="http",
        host="0.0.0.0",
        port=port,
        sse_path="/mcp",
        ws_path="/mcp/ws",
        log_level="debug"
    )
