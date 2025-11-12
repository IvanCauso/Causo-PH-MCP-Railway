import os
import requests
from fastmcp import FastMCP

# Server instance (old versions don’t support extra params like enable_ws / sse_path)
app = FastMCP("ProductHunt MCP")

@app.tool()
def ph_posts(start: str, end: str = None, first: int = 50):
    """Fetch Product Hunt posts between given dates."""
    token = os.getenv("PRODUCTHUNT_TOKEN")
    if not token:
        raise RuntimeError("Missing PRODUCTHUNT_TOKEN environment variable")

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

    response = requests.post(
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
    response.raise_for_status()
    data = response.json()

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


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    # Minimal syntax supported by 2.9
    app.run("http", host="0.0.0.0", port=port)
