import os
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP

app = FastMCP("ProductHunt MCP")
PH_URL = "https://api.producthunt.com/v2/api/graphql"

def _ph_headers() -> Dict[str, str]:
    token = os.environ.get("PRODUCTHUNT_TOKEN")
    if not token:
        raise RuntimeError("PRODUCTHUNT_TOKEN not set")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def _iso_day_bounds(day_str: str) -> tuple[str, str]:
    dt = datetime.fromisoformat(day_str).replace(tzinfo=timezone.utc)
    after = dt.isoformat().replace("+00:00", "Z")
    before = (dt + timedelta(days=1)).isoformat().replace("+00:00", "Z")
    return after, before

_QUERY = """
query($after: DateTime!, $before: DateTime!, $first: Int!, $cursor: String) {
  posts(postedAfter: $after, postedBefore: $before, first: $first, after: $cursor, order: RANKING) {
    edges { node {
      id name tagline votesCount createdAt website slug
      makers { name username }
    } }
    pageInfo { endCursor hasNextPage }
  }
}
"""

def _fetch_day(day_str: str, budget: int) -> List[Dict[str, Any]]:
    after, before = _iso_day_bounds(day_str)
    items: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    while budget > 0:
        body = {"query": _QUERY, "variables": {
            "after": after, "before": before, "first": min(30, budget), "cursor": cursor
        }}
        r = requests.post(PH_URL, headers=_ph_headers(), json=body, timeout=30)
        r.raise_for_status()
        payload = r.json()
        if payload.get("errors"):
            raise RuntimeError(f"Product Hunt GraphQL error: {payload['errors']}")
        posts = (payload.get("data") or {}).get("posts") or {}
        edges = posts.get("edges") or []
        items.extend([e["node"] for e in edges])
        page = posts.get("pageInfo") or {}
        budget -= len(edges)
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
    return items

@app.tool(
    name="ph_posts",
    description="Return up to `first` Product Hunt posts between UTC dates start..end (YYYY-MM-DD). If end is omitted, fetch a single day."
)
def ph_posts(start: str, end: Optional[str] = None, first: int = 100) -> List[Dict[str, Any]]:
    try:
        _ = datetime.fromisoformat(start)
        if end:
            _ = datetime.fromisoformat(end)
    except Exception:
        raise ValueError("Dates must be ISO format YYYY-MM-DD")
    if first <= 0:
        return []
    end = end or start
    out: List[Dict[str, Any]] = []
    cur = datetime.fromisoformat(start).date()
    end_d = datetime.fromisoformat(end).date()
    while cur <= end_d and len(out) < first:
        out.extend(_fetch_day(cur.isoformat(), first - len(out)))
        cur += timedelta(days=1)
    return out[:first]

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(transport="http", host="0.0.0.0", port=port)
