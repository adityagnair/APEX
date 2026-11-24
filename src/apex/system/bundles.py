"""Bundle dataclasses that group cohesive subsystems of ApexSystem."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from apex.agents._stubs import BaseAgent
    from apex.agents.executor import AgentExecutor
    from apex.agents.manager import AgentManager
    from apex.agents.scheduler import AgentScheduler
    from apex.scheduler.scheduler import TaskScheduler
    from apex.scheduler.store import SchedulerStore
    from apex.security.audit import AuditLogger
    from apex.security.boundary import BoundaryGuard
    from apex.security.capabilities import CapabilityPolicy
    from apex.telemetry.gpu_monitor import GpuMonitor
    from apex.telemetry.store import TelemetryStore
    from apex.traces.collector import TraceCollector
    from apex.traces.store import TraceStore


@dataclass
class SecurityContext:
    """Security policy, audit, and boundary enforcement."""

    capability_policy: Optional[CapabilityPolicy] = None
    audit_logger: Optional[AuditLogger] = None
    boundary_guard: Optional[BoundaryGuard] = None
    rate_limiter: Optional[Any] = None


@dataclass
class Observability:
    """Telemetry, traces, and hardware monitoring."""

    telemetry_store: Optional[TelemetryStore] = None
    trace_store: Optional[TraceStore] = None
    trace_collector: Optional[TraceCollector] = None
    gpu_monitor: Optional[GpuMonitor] = None


@dataclass
class AgentRuntime:
    """Active agent and agent lifecycle managers."""

    agent: Optional[BaseAgent] = None
    agent_name: str = ""
    manager: Optional[AgentManager] = None
    scheduler: Optional[AgentScheduler] = None
    executor: Optional[AgentExecutor] = None


@dataclass
class Scheduling:
    """Task scheduler and its persistent store."""

    store: Optional[SchedulerStore] = None
    runner: Optional[TaskScheduler] = None

