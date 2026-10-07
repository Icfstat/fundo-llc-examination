"""File-based cache for LLM responses.

This is the project's determinism contract. Every reviewer call is keyed by a
hash of (model + prompt). Responses are written here and committed to git, so a
clean checkout replays them with NO API key and produces identical output. The
model's own `seed` is only best-effort; the cache is what actually guarantees
reproducibility.
"""

import hashlib
import json
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "llm"


def key(model: str, prompt: str) -> str:
    """Stable content hash identifying one request."""
    h = hashlib.sha256(f"{model}\n{prompt}".encode("utf-8"))
    return h.hexdigest()


def get(k: str):
    """Return the cached response dict, or None on a miss."""
    path = CACHE_DIR / f"{k}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def put(k: str, value: dict) -> None:
    """Write a response to the cache (pretty + sorted for clean git diffs)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_DIR / f"{k}.json", "w") as f:
        json.dump(value, f, indent=2, sort_keys=True)
