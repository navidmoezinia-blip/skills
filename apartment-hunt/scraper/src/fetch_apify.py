"""Run an Apify actor and return its dataset items. Standard library only.

Apify's run-sync-get-dataset-items endpoint runs the actor and returns the
resulting items in one call:
    POST https://api.apify.com/v2/acts/{actorId}/run-sync-get-dataset-items?token=...
"""

import json
import urllib.error
import urllib.parse
import urllib.request


API_BASE = "https://api.apify.com/v2"


def run_actor(actor_id: str, token: str, actor_input: dict | None, timeout: int = 300) -> list[dict]:
    """Run an actor synchronously and return dataset items (list of dicts)."""
    if not actor_id or not token:
        raise ValueError("actor_id and token are required to call Apify.")

    quoted = actor_id.replace("/", "~")  # Apify accepts user~actor in the path
    url = f"{API_BASE}/acts/{urllib.parse.quote(quoted)}/run-sync-get-dataset-items?token={urllib.parse.quote(token)}"
    body = json.dumps(actor_input or {}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"Apify actor '{actor_id}' failed: HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Apify for '{actor_id}': {exc}") from exc

    if isinstance(data, dict):
        data = data.get("items") or data.get("results") or [data]
    return [r for r in data if isinstance(r, dict)]
