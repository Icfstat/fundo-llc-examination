"""Single-file cache for LLM responses.

This is the project's determinism contract. Every reviewer call is keyed by a
hash of (model + prompt), and all responses live in one JSON file that is
committed to git, so a clean checkout replays them with NO API key and produces
identical output. The model's own `seed` is only best-effort; the cache is what
actually guarantees reproducibility.
"""

import hashlib
import json
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parent.parent / "cache" / "llm.json"


def key(model: str, prompt: str) -> str:
    """Stable content hash identifying one request."""
    return hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()


def load() -> dict:
    """Return the whole cache as {key: response}, or {} if none exists yet."""
    if CACHE_PATH.exists():
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def save(data: dict) -> None:
    """Persist the cache (pretty + sorted keys for clean, stable git diffs)."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
