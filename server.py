import os
import requests
from fastmcp import FastMCP

# Server instance
app = FastMCP("ProductHunt MCP")

@app.tool()
def ph_posts(start: str, end: str = None, first: int = 50):
    """Fetch Product Hunt posts between given dates.
    
    Args:
        start: Start date in YYYY-MM-DD format
        end: End date in YYYY-MM-DD format (defaults to start date if not provided)
        first: Maximum number of posts to return (default: 50)
    
    Returns:
        List of Product Hunt posts with details including name, tagline, votes, and makers
    """
    try:
        print(f"[DEBUG] ph_posts called with start={start}, end={end}, first={first}")
        
        token = os.getenv("PRODUCTHUNT_TOKEN")
        if not token:
            print("[ERROR] Missing PRODUCTHUNT_TOKEN")
            return {"error": "Missing PRODUCTHUNT_TOKEN environment variable", "posts": []}

        if not end:
            end = start

        print(f"[DEBUG] Querying Product Hunt API for {start} to {end}")

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
        
        print(f"[DEBUG] Product Hunt API response status: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        
        # Check for GraphQL errors
        if "errors" in data:
            print(f"[ERROR] GraphQL errors: {data['errors']}")
            return {"error": "Product Hunt API returned errors", "details": data["errors"], "posts": []}

        posts = []
        edges = data.get("data", {}).get("posts", {}).get("edges", [])
        print(f"[DEBUG] Found {len(edges)} posts")
        
        for edge in edges:
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
        
        print(f"[DEBUG] Returning {len(posts)} posts")
        return {"posts": posts, "count": len(posts)}
        
    except Exception as e:
        print(f"[ERROR] Exception in ph_posts: {str(e)}")
        return {"error": str(e), "posts": []}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    # Run with HTTP transport for MCP - fastmcp 2.9 uses "http" not "sse"
    app.run("http", host="0.0.0.0", port=port)