"""Structural protocols for substituting fakes in place of ApexSystem."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Protocol

if TYPE_CHECKING:
    from apex.core.config import ApexConfig
    from apex.core.events import EventBus
    from apex.engine._stubs import InferenceEngine
    from apex.security.capabilities import CapabilityPolicy
    from apex.sessions.session import SessionStore
    from apex.tools._stubs import BaseTool
    from apex.tools.storage._stubs import MemoryBackend
    from apex.traces.collector import TraceCollector
    from apex.traces.store import TraceStore


class OrchestratorDeps(Protocol):
    """Minimum surface of ApexSystem that QueryOrchestrator depends on.

    Tests can satisfy this with a lightweight class — no need to construct
    the full ApexSystem dataclass or materialize every subsystem.
    """

    config: ApexConfig
    bus: EventBus
    engine: InferenceEngine
    engine_key: str
    model: str
    agent_name: str
    tools: List[BaseTool]
    memory_backend: Optional[MemoryBackend]
    capability_policy: Optional[CapabilityPolicy]
    rate_limiter: Optional[Any]
    session_store: Optional[SessionStore]
    trace_store: Optional[TraceStore]
    trace_collector: Optional[TraceCollector]  # written by _run_agent

    # Optional attribute (getattr with default) — declared for type clarity.
    _skill_few_shot_examples: Any

