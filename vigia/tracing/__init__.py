"""
vigia.tracing
--------------
Sistema de trazabilidad reutilizable para registrar y visualizar
la ejecución completa del agente Vigía.
"""

from vigia.tracing.collector import TraceCollector, TraceEvent, TraceStep, EventType

__all__ = ["TraceCollector", "TraceEvent", "TraceStep", "EventType"]
