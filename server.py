import os
import requests
from fastmcp import FastMCP

# Create the MCP app
app = FastMCP("ProductHunt MCP")

# Register tool manually (older-compatible style)
@app.tool()
def ph_posts(start: str, end: str = None, first: int = 50):
    """Fetch Product Hunt posts between given dates."""
    token = os.getenv("PRODUCTHUNT_TOKEN")
    if not token:
        raise RuntimeError("Missing PRODUCTHUNT_TOKEN env var")

    if not end:
        end = start

    query = """
    query ($start: DateTime!, $end: DateTime!, $first: Int!) {
      posts(postedAfter: $start, postedBefore: $end, first: $first, order: VOTES_COUNT) {
        edges {
          node {
            id
            name
            tagline
            votesCount
            createdAt
            website
            slug
            makers { name username }
          }
        }
      }
    }
    """

    resp = requests.post(
        "https://api.producthunt.com/v2/api/graphql",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "variables": {
                "start": f"{start}T00:00:00Z",
                "end": f"{end}T23:59:59Z",
                "first": first,
            },
        },
        timeout=30,
    )

    resp.raise_for_status()
    data = resp.json()

    posts = []
    for edge in data.get("data", {}).get("posts", {}).get("edges", []):
        n = edge.get("node", {})
        posts.append({
            "id": n.get("id"),
            "name": n.get("name"),
            "tagline": n.get("tagline"),
            "votesCount": n.get("votesCount"),
            "createdAt": n.get("createdAt"),
            "website": n.get("website"),
            "slug": n.get("slug"),
            "makers": n.get("makers"),
        })
    return posts


# ---------------------
# Run server with WS + SSE transport
# ---------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(
        transport="http",
        host="0.0.0.0",
        port=port,
        sse_path="/mcp",
        ws_path="/mcp/ws",
        log_level="debug",
        enable_ws=True,
    )
