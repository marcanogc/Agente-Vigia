"""
vigia.tracing.collector
------------------------
Sistema de trazabilidad ligero y reutilizable.

Diseñado para registrar cada paso de ejecución del agente sin acoplarse
a ningún pipeline específico. Puede usarse como context manager o
invocando métodos directamente.

Inspirado en el modelo de trazas de OpenTelemetry pero simplificado
para visualización en Streamlit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from datetime import datetime


class EventType(str, Enum):
    """Tipos de eventos en la traza de ejecución."""
    # Lifecycle
    PIPELINE_START = "pipeline_start"
    PIPELINE_END = "pipeline_end"
    
    # Stages
    STAGE_START = "stage_start"
    STAGE_END = "stage_end"
    
    # Tools / Operations
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    
    # Decisions
    DECISION = "decision"
    
    # Findings
    FINDING = "finding"
    
    # LLM
    LLM_CALL = "llm_call"
    LLM_RESPONSE = "llm_response"
    
    # Errors / Warnings
    ERROR = "error"
    WARNING = "warning"
    
    # Info
    INFO = "info"
    METRIC = "metric"


@dataclass
class TraceEvent:
    """Un evento individual en la traza de ejecución."""
    event_type: EventType
    stage: str                          # Nombre del stage (connector, inspector, audit, insight, llm)
    title: str                          # Título legible del evento
    timestamp: float = field(default_factory=time.time)  # Unix timestamp
    duration_ms: float | None = None    # Duración en ms (para eventos con inicio/fin)
    details: dict[str, Any] = field(default_factory=dict)  # Datos adicionales
    children: list[TraceEvent] = field(default_factory=list)  # Sub-eventos
    level: int = 0                      # Nivel de anidamiento (0 = top-level)
    
    @property
    def timestamp_str(self) -> str:
        """Timestamp formateado como HH:MM:SS.mmm"""
        dt = datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%H:%M:%S.") + f"{dt.microsecond // 1000:03d}"
    
    @property
    def duration_str(self) -> str:
        """Duración formateada legible."""
        if self.duration_ms is None:
            return ""
        if self.duration_ms < 1000:
            return f"{self.duration_ms:.0f}ms"
        return f"{self.duration_ms / 1000:.2f}s"


@dataclass
class TraceStep:
    """
    Un paso de alto nivel en la ejecución (stage).
    Agrupa eventos relacionados bajo un nombre de stage.
    """
    name: str                           # Nombre del stage
    display_name: str                   # Nombre para mostrar
    icon: str = ""                      # Emoji/icon
    status: str = "pending"             # pending, running, completed, error
    start_time: float | None = None
    end_time: float | None = None
    events: list[TraceEvent] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)  # Resumen del step
    
    @property
    def duration_ms(self) -> float | None:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None
    
    @property
    def duration_str(self) -> str:
        d = self.duration_ms
        if d is None:
            return ""
        if d < 1000:
            return f"{d:.0f}ms"
        return f"{d / 1000:.2f}s"


class TraceCollector:
    """
    Colector de trazas de ejecución.
    
    Uso como context manager:
        with trace.stage("inspector", "Schema Inspector", "🔍") as stage:
            trace.event("tool_call", "inspector", "get_tables", details={...})
            ...
    
    Uso directo:
        trace.start_stage("inspector", "Schema Inspector", "🔍")
        trace.event("tool_call", "inspector", "get_tables")
        trace.end_stage("inspector", summary={...})
    """

    def __init__(self):
        self.steps: list[TraceStep] = []
        self.events: list[TraceEvent] = []
        self._step_map: dict[str, TraceStep] = {}
        self._pipeline_start: float | None = None
        self._pipeline_end: float | None = None

    @property
    def total_duration_ms(self) -> float | None:
        if self._pipeline_start and self._pipeline_end:
            return (self._pipeline_end - self._pipeline_start) * 1000
        return None

    @property
    def total_duration_str(self) -> str:
        d = self.total_duration_ms
        if d is None:
            return ""
        if d < 1000:
            return f"{d:.0f}ms"
        return f"{d / 1000:.2f}s"

    # ─── Pipeline lifecycle ──────────────────────────────────────────────

    def start_pipeline(self):
        """Marca el inicio de la ejecución del pipeline."""
        self._pipeline_start = time.time()
        self.events.append(TraceEvent(
            event_type=EventType.PIPELINE_START,
            stage="pipeline",
            title="Pipeline iniciado",
            timestamp=self._pipeline_start,
        ))

    def end_pipeline(self, success: bool = True, error: str | None = None):
        """Marca el fin de la ejecución del pipeline."""
        self._pipeline_end = time.time()
        duration = (self._pipeline_end - self._pipeline_start) * 1000 if self._pipeline_start else None
        details = {"success": success}
        if error:
            details["error"] = error
        self.events.append(TraceEvent(
            event_type=EventType.PIPELINE_END,
            stage="pipeline",
            title="Pipeline finalizado" if success else f"Pipeline fallido: {error}",
            timestamp=self._pipeline_end,
            duration_ms=duration,
            details=details,
        ))

    # ─── Stage management ────────────────────────────────────────────────

    def start_stage(self, name: str, display_name: str, icon: str = "") -> TraceStep:
        """Inicia un nuevo stage de ejecución."""
        step = TraceStep(
            name=name,
            display_name=display_name,
            icon=icon,
            status="running",
            start_time=time.time(),
        )
        self.steps.append(step)
        self._step_map[name] = step
        
        self.events.append(TraceEvent(
            event_type=EventType.STAGE_START,
            stage=name,
            title=f"{icon} {display_name} iniciado",
            timestamp=step.start_time,
        ))
        return step

    def end_stage(self, name: str, summary: dict[str, Any] | None = None, error: str | None = None):
        """Finaliza un stage."""
        step = self._step_map.get(name)
        if not step:
            return
        
        step.end_time = time.time()
        step.status = "error" if error else "completed"
        if summary:
            step.summary = summary
        
        self.events.append(TraceEvent(
            event_type=EventType.STAGE_END,
            stage=name,
            title=f"{step.icon} {step.display_name} completado" if not error else f"{step.icon} {step.display_name} falló: {error}",
            timestamp=step.end_time,
            duration_ms=step.duration_ms,
            details=summary or {},
        ))

    def stage(self, name: str, display_name: str, icon: str = ""):
        """Context manager para un stage."""
        return _StageContext(self, name, display_name, icon)

    # ─── Event recording ─────────────────────────────────────────────────

    def event(
        self,
        event_type: EventType | str,
        stage: str,
        title: str,
        details: dict[str, Any] | None = None,
        duration_ms: float | None = None,
    ):
        """Registra un evento en la traza."""
        if isinstance(event_type, str):
            event_type = EventType(event_type)
        
        evt = TraceEvent(
            event_type=event_type,
            stage=stage,
            title=title,
            details=details or {},
            duration_ms=duration_ms,
        )
        self.events.append(evt)
        
        # También agregar al step correspondiente
        step = self._step_map.get(stage)
        if step:
            step.events.append(evt)

    def tool(self, stage: str, tool_name: str, inputs: dict[str, Any] | None = None, outputs: dict[str, Any] | None = None, duration_ms: float | None = None):
        """Shorthand para registrar una invocación de herramienta."""
        self.event(
            EventType.TOOL_CALL,
            stage=stage,
            title=f"Tool: {tool_name}",
            details={"tool": tool_name, "inputs": inputs or {}, "outputs": outputs or {}},
            duration_ms=duration_ms,
        )

    def decision(self, stage: str, title: str, reasoning: str = "", outcome: str = ""):
        """Registra una decisión del agente."""
        self.event(
            EventType.DECISION,
            stage=stage,
            title=title,
            details={"reasoning": reasoning, "outcome": outcome},
        )

    def finding(self, stage: str, title: str, details: dict[str, Any] | None = None):
        """Registra un hallazgo detectado."""
        self.event(EventType.FINDING, stage=stage, title=title, details=details or {})

    def metric(self, stage: str, name: str, value: Any):
        """Registra una métrica."""
        self.event(EventType.METRIC, stage=stage, title=f"{name}: {value}", details={"metric": name, "value": value})

    def error(self, stage: str, message: str, details: dict[str, Any] | None = None):
        """Registra un error."""
        self.event(EventType.ERROR, stage=stage, title=message, details=details or {})

    def warning(self, stage: str, message: str, details: dict[str, Any] | None = None):
        """Registra una advertencia."""
        self.event(EventType.WARNING, stage=stage, title=message, details=details or {})

    def info(self, stage: str, message: str, details: dict[str, Any] | None = None):
        """Registra información."""
        self.event(EventType.INFO, stage=stage, title=message, details=details or {})

    # ─── Serialization ───────────────────────────────────────────────────

    def get_mermaid_flowchart(self) -> str:
        """Genera un diagrama Mermaid del flujo de ejecución."""
        lines = ["graph TD"]
        
        for i, step in enumerate(self.steps):
            node_id = f"S{i}"
            status_icon = {"completed": "✅", "error": "❌", "running": "🔄", "pending": "⏳"}.get(step.status, "")
            label = f"{step.icon} {step.display_name}\\n{status_icon} {step.duration_str}"
            lines.append(f'    {node_id}["{label}"]')
            
            if i > 0:
                prev_id = f"S{i-1}"
                lines.append(f"    {prev_id} --> {node_id}")
            
            # Style based on status
            if step.status == "completed":
                lines.append(f"    style {node_id} fill:#d4edda,stroke:#28a745")
            elif step.status == "error":
                lines.append(f"    style {node_id} fill:#f8d7da,stroke:#dc3545")

        return "\n".join(lines)

    def get_timeline_data(self) -> list[dict[str, Any]]:
        """Retorna datos para visualización de timeline."""
        timeline = []
        for step in self.steps:
            timeline.append({
                "name": step.display_name,
                "icon": step.icon,
                "status": step.status,
                "duration_ms": step.duration_ms,
                "duration_str": step.duration_str,
                "events_count": len(step.events),
                "summary": step.summary,
                "events": [
                    {
                        "type": e.event_type.value,
                        "title": e.title,
                        "time": e.timestamp_str,
                        "duration": e.duration_str,
                        "details": e.details,
                    }
                    for e in step.events
                ],
            })
        return timeline


class _StageContext:
    """Context manager interno para stages."""
    
    def __init__(self, collector: TraceCollector, name: str, display_name: str, icon: str):
        self._collector = collector
        self._name = name
        self._display_name = display_name
        self._icon = icon
        self._step: TraceStep | None = None

    def __enter__(self) -> TraceStep:
        self._step = self._collector.start_stage(self._name, self._display_name, self._icon)
        return self._step

    def __exit__(self, exc_type, exc_val, exc_tb):
        error = str(exc_val) if exc_val else None
        self._collector.end_stage(self._name, error=error)
        return False  # Don't suppress exceptions
