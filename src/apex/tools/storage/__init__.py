"""Storage primitive — persistent searchable storage."""

from __future__ import annotations

import importlib
import logging

# Always-available backend
import apex.tools.storage.sqlite  # noqa: F401
from apex.tools.storage._stubs import MemoryBackend, RetrievalResult
from apex.tools.storage.chunking import Chunk, ChunkConfig, chunk_text
from apex.tools.storage.context import ContextConfig, inject_context
from apex.tools.storage.ingest import ingest_path, read_document

logger = logging.getLogger(__name__)

# Optional backends — import to trigger registration
_OPTIONAL_STORAGE_BACKENDS = (
    "bm25",
    "faiss_backend",
    "colbert_backend",
    "hybrid",
    "dense",
)

for _backend in _OPTIONAL_STORAGE_BACKENDS:
    try:
        importlib.import_module(f"apex.tools.storage.{_backend}")
    except ImportError as _exc:
        logger.debug("Optional storage backend %s not loaded: %s", _backend, _exc)

__all__ = [
    "Chunk",
    "ChunkConfig",
    "ContextConfig",
    "MemoryBackend",
    "RetrievalResult",
    "chunk_text",
    "inject_context",
    "ingest_path",
    "read_document",
]

