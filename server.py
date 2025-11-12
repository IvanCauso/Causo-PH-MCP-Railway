import os, requests
from datetime import datetime, timedelta, timezone
from fastmcp import FastMCP, tool

PH_TOKEN = os.environ.get("PRODUCTHUNT_TOKEN")
PH_URL = "https://api.producthunt.com/v2/api/graphql"

app = FastMCP("ProductHunt MCP")

def _hdrs():
    if not PH_TOKEN:
        raise RuntimeError("PRODUCTHUNT_TOKEN not set")
    return {"Authorization": f"Bearer {PH_TOKEN}", "Content-Type": "application/json"}

def _day_bounds(d: str):
    dt = datetime.fromisoformat(d).replace(tzinfo=timezone.utc)
    after = dt.isoformat().replace("+00:00","Z")
    before = (dt + timedelta(days=1)).isoformat().replace("+00:00","Z")
    return after, before

_QUERY = """
query($after: DateTime!, $before: DateTime!, $first: Int!, $cursor: String) {
  posts(postedAfter: $after, postedBefore: $before, first: $first, after: $cursor, order: RANKING) {
    edges { node {
      id name tagline votesCount createdAt website slug
      makers { name username }
    }}
    pageInfo { endCursor hasNextPage }
  }
}
"""

@tool
def ph_posts(start: str, end: str = None, first: int = 100) -> list:
    end = end or start
    items = []
    cur = datetime.fromisoformat(start).date()
    end_d = datetime.fromisoformat(end).date()
    while cur <= end_d and len(items) < first:
        after, before = _day_bounds(cur.isoformat())
        cursor = None
        while len(items) < first:
            body = {"query": _QUERY, "variables": {
                "after": after, "before": before,
                "first": min(30, first - len(items)), "cursor": cursor
            }}
            r = requests.post(PH_URL, headers=_hdrs(), json=body, timeout=30)
            r.raise_for_status()
            data = r.json().get("data", {}).get("posts", {})
            items += [e["node"] for e in data.get("edges", [])]
            page = data.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
        cur = cur + timedelta(days=1)
    return items[:first]

if __name__ == "__main__":
    # FastMCP starts a WS server and binds to PORT
    app.run()
