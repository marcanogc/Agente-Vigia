"""
vigia.models.schema_models
-----------------------------
Modelos de datos centrales del sistema de auditoría universal.
Dataclasses que representan los resultados del análisis en cada fase:
- SchemaMetadata: resultado de la introspección del esquema
- ColumnProfile: perfil estadístico de una columna
- AuditFinding: hallazgo individual de auditoría
- AuditReport: reporte completo de auditoría
- RiskEntry: riesgo operacional detectado
- SemanticLabel: clasificación semántica inferida
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from vigia.connectors.base import (
    DataTypeCategory,
    ForeignKeyInfo,
    TableInfo,
)


# ─────────────────────────────────────────────────────────────────────────────
# Enumeraciones
# ─────────────────────────────────────────────────────────────────────────────


class SemanticType(str, Enum):
    """Clasificación semántica inferida para columnas."""
    IDENTIFIER = "identifier"           # IDs, códigos, claves
    NAME = "name"                       # Nombres propios, títulos
    EMAIL = "email"                     # Direcciones de email
    PHONE = "phone"                     # Números de teléfono
    URL = "url"                         # URLs, links
    DATE = "date"                       # Fechas
    DATETIME = "datetime"              # Fecha + hora
    MONETARY = "monetary"              # Valores monetarios (precios, salarios, presupuestos)
    PERCENTAGE = "percentage"          # Porcentajes (0-100 o 0-1)
    PROBABILITY = "probability"        # Probabilidades (0-1)
    QUANTITY = "quantity"              # Cantidades, conteos
    MEASUREMENT = "measurement"        # Mediciones físicas (temperatura, peso, etc.)
    CATEGORICAL = "categorical"        # Variables categóricas (status, tipo, etc.)
    BOOLEAN = "boolean"                # Valores binarios
    TEXT_FREE = "text_free"            # Texto libre, descripciones
    ADDRESS = "address"                # Direcciones físicas
    GEOGRAPHIC = "geographic"          # Coordenadas, ubicaciones
    BINARY_DATA = "binary_data"        # Datos binarios
    UNKNOWN = "unknown"                # No se pudo clasificar


class AuditLevel(str, Enum):
    """Nivel de severidad de un hallazgo de auditoría."""
    CRITICAL = "CRITICAL"   # Bloquea el análisis
    ERROR = "ERROR"         # Problema grave de calidad
    WARNING = "WARNING"     # Problema menor o inferencia
    INFO = "INFO"           # Información contextual


class AuditCategory(str, Enum):
    """Categoría de auditoría."""
    STRUCTURAL = "STRUCTURAL"       # Tipos, nulls, formatos
    RELATIONAL = "RELATIONAL"       # Integridad referencial
    STATISTICAL = "STATISTICAL"     # Outliers, distribuciones
    CONSISTENCY = "CONSISTENCY"     # Contradicciones entre datos
    COMPLETENESS = "COMPLETENESS"   # Datos faltantes, cobertura


class RiskPriority(str, Enum):
    """Prioridad de un riesgo detectado."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ─────────────────────────────────────────────────────────────────────────────
# Modelos de datos
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SemanticLabel:
    """Clasificación semántica de una columna con nivel de confianza."""
    semantic_type: SemanticType
    confidence: float                  # 0.0 a 1.0
    reasoning: str = ""                # Explicación de por qué se infirió este tipo
    constraints: dict[str, Any] = field(default_factory=dict)
    # Constraints inferidas: {"min": 0, "max": 100} para porcentaje, etc.


@dataclass
class ColumnProfile:
    """Perfil estadístico completo de una columna."""
    table_name: str
    column_name: str
    data_type: DataTypeCategory
    semantic_label: SemanticLabel | None = None

    # Estadísticas de completitud
    total_count: int = 0
    null_count: int = 0
    empty_string_count: int = 0
    distinct_count: int = 0

    # Estadísticas numéricas (solo si aplica)
    min_value: float | None = None
    max_value: float | None = None
    avg_value: float | None = None
    stddev_value: float | None = None
    median_value: float | None = None
    q1_value: float | None = None
    q3_value: float | None = None

    # Estadísticas de texto (solo si aplica)
    min_length: int | None = None
    max_length: int | None = None
    avg_length: float | None = None

    # Patrones
    most_frequent_values: list[tuple[Any, int]] = field(default_factory=list)
    sample_values: list[Any] = field(default_factory=list)

    @property
    def null_percentage(self) -> float:
        """Porcentaje de valores nulos."""
        if self.total_count == 0:
            return 0.0
        return (self.null_count / self.total_count) * 100.0

    @property
    def completeness(self) -> float:
        """Porcentaje de completitud (no-null)."""
        return 100.0 - self.null_percentage

    @property
    def uniqueness(self) -> float:
        """Porcentaje de valores únicos sobre el total no-null."""
        non_null = self.total_count - self.null_count
        if non_null == 0:
            return 0.0
        return (self.distinct_count / non_null) * 100.0

    @property
    def is_constant(self) -> bool:
        """True si la columna tiene un solo valor distinto (o está vacía)."""
        return self.distinct_count <= 1

    @property
    def iqr(self) -> float | None:
        """Rango intercuartílico."""
        if self.q1_value is not None and self.q3_value is not None:
            return self.q3_value - self.q1_value
        return None


@dataclass
class InferredRelationship:
    """Relación inferida entre tablas por heurísticas."""
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    confidence: float                 # 0.0 a 1.0
    method: str                       # "name_convention", "value_overlap", "cardinality_match"
    reasoning: str = ""


@dataclass
class SchemaMetadata:
    """Resultado completo de la introspección y análisis del esquema."""
    tables: list[TableInfo] = field(default_factory=list)
    column_profiles: list[ColumnProfile] = field(default_factory=list)
    declared_relationships: list[ForeignKeyInfo] = field(default_factory=list)
    inferred_relationships: list[InferredRelationship] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)  # Lo que no se pudo determinar

    # Estadísticas globales
    total_tables: int = 0
    total_columns: int = 0
    total_rows: int = 0

    def get_table(self, name: str) -> TableInfo | None:
        """Obtiene una tabla por nombre."""
        name_lower = name.lower()
        for t in self.tables:
            if t.name.lower() == name_lower:
                return t
        return None

    def get_column_profile(self, table: str, column: str) -> ColumnProfile | None:
        """Obtiene el perfil de una columna específica."""
        for cp in self.column_profiles:
            if cp.table_name.lower() == table.lower() and cp.column_name.lower() == column.lower():
                return cp
        return None

    def get_table_profiles(self, table: str) -> list[ColumnProfile]:
        """Obtiene todos los perfiles de columnas de una tabla."""
        return [cp for cp in self.column_profiles if cp.table_name.lower() == table.lower()]


@dataclass
class AuditFinding:
    """Un hallazgo individual de auditoría."""
    table: str
    column: str | None                # None si aplica a toda la tabla
    level: AuditLevel
    category: AuditCategory
    rule_name: str                    # Nombre de la regla que generó el hallazgo
    message: str                      # Descripción legible del problema
    affected_rows: int = 0            # Número de filas afectadas
    sample_values: list[Any] = field(default_factory=list)  # Muestra de valores problemáticos
    details: dict[str, Any] = field(default_factory=dict)   # Detalles adicionales


@dataclass
class TableAuditSummary:
    """Resumen de auditoría para una tabla individual."""
    table_name: str
    row_count: int = 0
    column_count: int = 0
    findings_count: int = 0
    critical_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    quality_score: float = 100.0      # Score de calidad por tabla (0-100)
    score_explanation: list[str] = field(default_factory=list)  # Desglose del score


@dataclass
class AuditReport:
    """Reporte completo de auditoría."""
    # Findings por tabla y categoría
    findings: list[AuditFinding] = field(default_factory=list)
    table_summaries: list[TableAuditSummary] = field(default_factory=list)

    # Score global
    global_quality_score: float = 100.0
    score_explanation: list[str] = field(default_factory=list)

    # Resumen numérico
    total_tables_audited: int = 0
    total_rows_audited: int = 0
    total_findings: int = 0
    critical_findings: int = 0
    error_findings: int = 0
    warning_findings: int = 0
    info_findings: int = 0

    # Metadatos
    limitations: list[str] = field(default_factory=list)

    def get_findings_by_table(self, table: str) -> list[AuditFinding]:
        """Filtra hallazgos por tabla."""
        return [f for f in self.findings if f.table.lower() == table.lower()]

    def get_findings_by_category(self, category: AuditCategory) -> list[AuditFinding]:
        """Filtra hallazgos por categoría."""
        return [f for f in self.findings if f.category == category]

    def get_findings_by_level(self, level: AuditLevel) -> list[AuditFinding]:
        """Filtra hallazgos por nivel."""
        return [f for f in self.findings if f.level == level]


@dataclass
class RiskEntry:
    """Un riesgo operacional detectado en los datos."""
    risk_type: str
    priority: RiskPriority
    table: str
    column: str | None = None
    description: str = ""
    evidence: list[str] = field(default_factory=list)  # IDs o valores de evidencia
    recommendation: str = ""


@dataclass
class InsightReport:
    """Reporte completo de insights generado por el motor de IA."""
    audit_report: AuditReport
    schema_metadata: SchemaMetadata
    risks: list[RiskEntry] = field(default_factory=list)
    report_markdown: str = ""
    llm_provider_used: str = ""       # "bedrock", "nvidia", "openai", "mock"
    clean_data_stats: dict[str, int] = field(default_factory=dict)
