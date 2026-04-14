"""Build a Qdrant client without Docker: embedded storage on disk by default."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    load_dotenv(_PROJECT_ROOT / ".env")


def build_qdrant_client() -> QdrantClient:
    """
    - Default: embedded Qdrant under <project>/qdrant_storage (no server, no Docker).
    - Optional: QDRANT_PATH=/custom/dir for another local folder.
    - Optional: QDRANT_URL + optional QDRANT_API_KEY for Qdrant Cloud or a remote server.
    """
    _load_env()
    url = os.environ.get("QDRANT_URL", "").strip()
    api_key = os.environ.get("QDRANT_API_KEY", "").strip()
    path_override = os.environ.get("QDRANT_PATH", "").strip()

    if url:
        kwargs: dict = {"url": url}
        if api_key:
            kwargs["api_key"] = api_key
        return QdrantClient(**kwargs)

    if path_override:
        p = Path(path_override).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return QdrantClient(path=str(p))

    local_dir = _PROJECT_ROOT / "qdrant_storage"
    local_dir.mkdir(exist_ok=True)
    return QdrantClient(path=str(local_dir))
