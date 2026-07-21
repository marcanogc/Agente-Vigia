"""
vigia.audit.rules
---------------------
Reglas de auditoría pluggables para el motor genérico.
Cada regla es una clase independiente que implementa la interfaz AuditRule.
Se pueden agregar nuevas reglas sin modificar el motor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from vigia.connectors.base import BaseConnector, DataTypeCategory, TableInfo
from vigia.models.schema_models import (
    AuditCategory,
    AuditFinding,
    AuditLevel,
    ColumnProfile,
    SchemaMetadata,
    SemanticType,
)


class AuditRule(ABC):
    """
    Interfaz base para reglas de auditoría.
    Cada regla evalúa un aspecto específico de calidad de datos.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre identificador de la regla."""
        ...

    @property
    @abstractmethod
    def category(self) -> AuditCategory:
        """Categoría de auditoría."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Descripción legible de lo que verifica esta regla."""
        ...

    @abstractmethod
    def evaluate(
        self,
        connector: BaseConnector,
        table_info: TableInfo,
        schema_metadata: SchemaMetadata,
    ) -> list[AuditFinding]:
        """
        Evalúa la regla sobre una tabla y retorna los hallazgos.
        
        Args:
            connector: Conector activo para consultas.
            table_info: Metadatos de la tabla a evaluar.
            schema_metadata: Metadatos completos del esquema (para reglas cross-table).
        
        Returns:
            Lista de hallazgos detectados (puede estar vacía si no hay problemas).
        """
        ...


# ─────────────────────────────────────────────────────────────────────────────
# REGLAS ESTRUCTURALES
# ─────────────────────────────────────────────────────────────────────────────


class NullPrimaryKeyRule(AuditRule):
    """Detecta valores NULL en columnas de clave primaria."""

    @property
    def name(self) -> str:
        return "null_primary_key"

    @property
    def category(self) -> AuditCategory:
        return AuditCategory.STRUCTURAL

    @property
    def description(self) -> str:
        return "Las claves primarias no deben contener valores NULL."

    def evaluate(self, connector, table_info, schema_metadata) -> list[AuditFinding]:
        findings = []
        for pk_col in table_info.primary_keys:
            null_count = connector.count_nulls(table_info.name, pk_col)
            if null_count > 0:
                findings.append(AuditFinding(
                    table=table_info.name,
                    column=pk_col,
                    level=AuditLevel.CRITICAL,
                    category=self.category,
                    rule_name=self.name,
                    message=f"Clave primaria '{pk_col}' contiene {null_count} valores NULL.",
                    affected_rows=null_count,
                ))
        return findings


class DuplicatePrimaryKeyRule(AuditRule):
    """Detecta valores duplicados en columnas de clave primaria."""

    @property
    def name(self) -> str:
        return "duplicate_primary_key"

    @property
    def category(self) -> AuditCategory:
        return AuditCategory.STRUCTURAL

    @property
    def description(self) -> str:
        return "Las claves primarias no deben contener valores duplicados."

    def evaluate(self, connector, table_info, schema_metadata) -> list[AuditFinding]:
        findings = []
        if table_info.primary_keys:
            dup_count = connector.count_duplicates(table_info.name, table_info.primary_keys)
            if dup_count > 0:
                pk_str = ", ".join(table_info.primary_keys)
                findings.append(AuditFinding(
                    table=table_info.name,
                    column=pk_str,
                    level=AuditLevel.CRITICAL,
                    category=self.category,
                    rule_name=self.name,
                    message=f"Clave primaria ({pk_str}) tiene {dup_count} filas duplicadas.",
                    affected_rows=dup_count,
                ))
        return findings


class NullRequiredFieldRule(AuditRule):
    """Detecta valores NULL en columnas marcadas como NOT NULL o en identificadores."""

    @property
    def name(self) -> str:
        return "null_required_field"

    @property
    def category(self) -> AuditCategory:
        return AuditCategory.COMPLETENESS

    @property
    def description(self) -> str:
        return "Columnas identificadas como requeridas no deben tener valores NULL."

    def evaluate(self, connector, table_info, schema_metadata) -> list[AuditFinding]:
        findings = []
        for col in table_info.columns:
            # Verificar columnas NOT NULL o con semántica de identificador
            profile = schema_metadata.get_column_profile(table_info.name, col.name)
            is_required = not col.nullable
            
            if profile and profile.semantic_label:
                if profile.semantic_label.semantic_type == SemanticType.IDENTIFIER:
                    is_required = True

            if is_required and not col.is_primary_key:
                null_count = connector.count_nulls(table_info.name, col.name)
                if null_count > 0:
                    row_count = table_info.row_count or 1
                    pct = (null_count / row_count) * 100
                    findings.append(AuditFinding(
                        table=table_info.name,
                        column=col.name,
                        level=AuditLevel.ERROR if pct > 5 else AuditLevel.WARNING,
                        category=self.category,
                        rule_name=self.name,
                        message=f"Columna requerida '{col.name}' tiene {null_count} valores NULL ({pct:.1f}%).",
                        affected_rows=null_count,
                        details={"null_percentage": round(pct, 2)},
                    ))
        return findings


class InvalidDateRule(AuditRule):
    """Detecta fechas inválidas en columnas de tipo fecha/datetime."""

    @property
    def name(self) -> str:
        return "invalid_date"

    @property
    def category(self) -> AuditCategory:
        return AuditCategory.STRUCTURAL

    @property
    def description(self) -> str:
        return "Las columnas de fecha deben contener valores en formato válido."

    def evaluate(self, connector, table_info, schema_metadata) -> list[AuditFinding]:
        from datetime import datetime

        findings = []
        date_columns = [
            col for col in table_info.columns
            if col.generic_type in (DataTypeCategory.DATE, DataTypeCategory.DATETIME, DataTypeCategory.TIMESTAMP)
        ]

        # También incluir columnas clasificadas semánticamente como fecha
        for col in table_info.columns:
            if col not in date_columns:
                profile = schema_metadata.get_column_profile(table_info.name, col.name)
                if profile and profile.semantic_label:
                    if profile.semantic_label.semantic_type in (SemanticType.DATE, SemanticType.DATETIME):
                        date_columns.append(col)

        for col in date_columns:
            values = connector.get_column_values(table_info.name, col.name, limit=500)
            invalid_count = 0
            invalid_samples = []

            for val in values:
                if val is None:
                    continue
                if not self._is_valid_date(str(val)):
                    invalid_count += 1
                    if len(invalid_samples) < 5:
                        invalid_samples.append(val)

            if invalid_count > 0:
                findings.append(AuditFinding(
                    table=table_info.name,
                    column=col.name,
                    level=AuditLevel.ERROR,
                    category=self.category,
                    rule_name=self.name,
                    message=f"Columna '{col.name}' contiene {invalid_count} fechas inválidas.",
                    affected_rows=invalid_count,
                    sample_values=invalid_samples,
                ))

        return findings

    @staticmethod
    def _is_valid_date(val: str) -> bool:
        """Verifica si un string es una fecha válida."""
        from datetime import datetime
        formats = [
            "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
            "%d-%m-%Y", "%d.%m.%Y",
            "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f",
        ]
        for fmt in formats:
            try:
                datetime.strptime(val, fmt)
                return True
            except ValueError:
                continue
        return False


class NegativeValueRule(AuditRule):
    """Detecta valores negativos en columnas que semánticamente no deberían serlo."""

    @property
    def name(self) -> str:
        return "negative_value"

    @property
    def category(self) -> AuditCategory:
        return AuditCategory.STRUCTURAL

    @property
    def description(self) -> str:
        return "Columnas monetarias, de cantidad o porcentaje no deben tener valores negativos."

    def evaluate(self, connector, table_info, schema_metadata) -> list[AuditFinding]:
        findings = []
        non_negative_types = {
            SemanticType.MONETARY, SemanticType.QUANTITY,
            SemanticType.PERCENTAGE, SemanticType.PROBABILITY,
        }

        for col in table_info.columns:
            if col.generic_type not in (DataTypeCategory.INTEGER, DataTypeCategory.FLOAT):
                continue

            profile = schema_metadata.get_column_profile(table_info.name, col.name)
            if not profile or not profile.semantic_label:
                continue

            if profile.semantic_label.semantic_type not in non_negative_types:
                continue

            # Solo reportar si hay confianza razonable en la clasificación
            if profile.semantic_label.confidence < 0.6:
                continue

            if profile.min_value is not None and profile.min_value < 0:
                # Contar cuántos negativos hay
                values = connector.get_column_values(table_info.name, col.name, limit=1000)
                neg_count = sum(1 for v in values if v is not None and isinstance(v, (int, float)) and v < 0)

                if neg_count > 0:
                    findings.append(AuditFinding(
                        table=table_info.name,
                        column=col.name,
                        level=AuditLevel.ERROR,
                        category=self.category,
                        rule_name=self.name,
                        message=(
                            f"Columna '{col.name}' ({profile.semantic_label.semantic_type.value}) "
                            f"contiene {neg_count} valores negativos (min: {profile.min_value})."
                        ),
                        affected_rows=neg_count,
                        details={
                            "semantic_type": profile.semantic_label.semantic_type.value,
                            "confidence": profile.semantic_label.confidence,
                            "min_value": profile.min_value,
                        },
                    ))

        return findings


class EmptyStringRule(AuditRule):
    """Detecta columnas con alto porcentaje de strings vacíos."""

    @property
    def name(self) -> str:
        return "empty_strings"

    @property
    def category(self) -> AuditCategory:
        return AuditCategory.COMPLETENESS

    @property
    def description(self) -> str:
        return "Columnas de texto no deben tener porcentaje excesivo de strings vacíos."

    def evaluate(self, connector, table_info, schema_metadata) -> list[AuditFinding]:
        findings = []
        for col in table_info.columns:
            if col.generic_type != DataTypeCategory.TEXT:
                continue

            profile = schema_metadata.get_column_profile(table_info.name, col.name)
            if not profile:
                continue

            if profile.empty_string_count > 0 and table_info.row_count > 0:
                pct = (profile.empty_string_count / table_info.row_count) * 100
                if pct >= 10:  # Solo reportar si >= 10%
                    findings.append(AuditFinding(
                        table=table_info.name,
                        column=col.name,
                        level=AuditLevel.WARNING,
                        category=self.category,
                        rule_name=self.name,
                        message=f"Columna '{col.name}' tiene {profile.empty_string_count} strings vacíos ({pct:.1f}%).",
                        affected_rows=profile.empty_string_count,
                        details={"empty_percentage": round(pct, 2)},
                    ))
        return findings


# ─────────────────────────────────────────────────────────────────────────────
# REGLAS RELACIONALES
# ─────────────────────────────────────────────────────────────────────────────


class OrphanedForeignKeyRule(AuditRule):
    """Detecta valores huérfanos en claves foráneas (declaradas e inferidas)."""

    @property
    def name(self) -> str:
        return "orphaned_foreign_key"

    @property
    def category(self) -> AuditCategory:
        return AuditCategory.RELATIONAL

    @property
    def description(self) -> str:
        return "Los valores de claves foráneas deben existir en la tabla referenciada."

    def evaluate(self, connector, table_info, schema_metadata) -> list[AuditFinding]:
        findings = []

        # Verificar FKs declaradas
        for fk in table_info.foreign_keys:
            orphans = connector.check_referential_integrity(
                table_info.name, fk.column, fk.referenced_table, fk.referenced_column
            )
            if orphans:
                sample = orphans[:5]
                findings.append(AuditFinding(
                    table=table_info.name,
                    column=fk.column,
                    level=AuditLevel.ERROR,
                    category=self.category,
                    rule_name=self.name,
                    message=(
                        f"FK '{fk.column}' tiene {len(orphans)} valores huérfanos "
                        f"(no existen en '{fk.referenced_table}.{fk.referenced_column}')."
                    ),
                    affected_rows=len(orphans),
                    sample_values=sample,
                ))

        # Verificar relaciones inferidas con alta confianza
        for rel in schema_metadata.inferred_relationships:
            if rel.source_table != table_info.name:
                continue
            if rel.confidence < 0.7:
                continue

            orphans = connector.check_referential_integrity(
                rel.source_table, rel.source_column, rel.target_table, rel.target_column
            )
            if orphans:
                sample = orphans[:5]
                findings.append(AuditFinding(
                    table=table_info.name,
                    column=rel.source_column,
                    level=AuditLevel.WARNING,
                    category=self.category,
                    rule_name=self.name,
                    message=(
                        f"Relación inferida: '{rel.source_column}' tiene {len(orphans)} valores "
                        f"que no existen en '{rel.target_table}.{rel.target_column}' "
                        f"(confianza: {rel.confidence:.0%})."
                    ),
                    affected_rows=len(orphans),
                    sample_values=sample,
                    details={"inferred": True, "confidence": rel.confidence},
                ))

        return findings


# ─────────────────────────────────────────────────────────────────────────────
# REGLAS ESTADÍSTICAS
# ─────────────────────────────────────────────────────────────────────────────


class OutlierDetectionRule(AuditRule):
    """Detecta outliers en columnas numéricas usando el método IQR."""

    @property
    def name(self) -> str:
        return "outlier_detection"

    @property
    def category(self) -> AuditCategory:
        return AuditCategory.STATISTICAL

    @property
    def description(self) -> str:
        return "Detecta valores atípicos usando el método IQR (1.5x rango intercuartílico)."

    def evaluate(self, connector, table_info, schema_metadata) -> list[AuditFinding]:
        findings = []

        for col in table_info.columns:
            if col.generic_type not in (DataTypeCategory.INTEGER, DataTypeCategory.FLOAT):
                continue

            profile = schema_metadata.get_column_profile(table_info.name, col.name)
            if not profile or profile.iqr is None:
                continue

            # No aplicar a identificadores o booleanos
            if profile.semantic_label:
                if profile.semantic_label.semantic_type in (SemanticType.IDENTIFIER, SemanticType.BOOLEAN):
                    continue

            q1 = profile.q1_value
            q3 = profile.q3_value
            iqr = profile.iqr

            if iqr == 0 or q1 is None or q3 is None:
                continue

            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            # Contar outliers
            values = connector.get_column_values(table_info.name, col.name, limit=2000)
            numeric_values = [v for v in values if isinstance(v, (int, float))]
            outliers = [v for v in numeric_values if v < lower_bound or v > upper_bound]

            if outliers and len(outliers) > 0:
                pct = (len(outliers) / max(len(numeric_values), 1)) * 100
                # Solo reportar si hay un % significativo de outliers
                if pct >= 1.0 or len(outliers) >= 3:
                    findings.append(AuditFinding(
                        table=table_info.name,
                        column=col.name,
                        level=AuditLevel.WARNING,
                        category=self.category,
                        rule_name=self.name,
                        message=(
                            f"Columna '{col.name}' tiene {len(outliers)} outliers ({pct:.1f}%). "
                            f"Rango esperado: [{lower_bound:.2f}, {upper_bound:.2f}]."
                        ),
                        affected_rows=len(outliers),
                        sample_values=sorted(outliers)[:5],
                        details={
                            "lower_bound": round(lower_bound, 2),
                            "upper_bound": round(upper_bound, 2),
                            "iqr": round(iqr, 2),
                            "outlier_percentage": round(pct, 2),
                        },
                    ))

        return findings


class ConstantColumnRule(AuditRule):
    """Detecta columnas con un solo valor (constantes o vacías)."""

    @property
    def name(self) -> str:
        return "constant_column"

    @property
    def category(self) -> AuditCategory:
        return AuditCategory.STATISTICAL

    @property
    def description(self) -> str:
        return "Columnas con un solo valor distinto no aportan información analítica."

    def evaluate(self, connector, table_info, schema_metadata) -> list[AuditFinding]:
        findings = []

        for col in table_info.columns:
            profile = schema_metadata.get_column_profile(table_info.name, col.name)
            if not profile:
                continue

            # Solo reportar en tablas con más de 1 fila
            if table_info.row_count <= 1:
                continue

            if profile.is_constant and (profile.total_count - profile.null_count) > 0:
                findings.append(AuditFinding(
                    table=table_info.name,
                    column=col.name,
                    level=AuditLevel.INFO,
                    category=self.category,
                    rule_name=self.name,
                    message=f"Columna '{col.name}' tiene un solo valor distinto (columna constante).",
                    affected_rows=table_info.row_count,
                    sample_values=profile.sample_values[:3],
                ))

        return findings


class HighNullRateRule(AuditRule):
    """Detecta columnas con un porcentaje muy alto de valores NULL."""

    @property
    def name(self) -> str:
        return "high_null_rate"

    @property
    def category(self) -> AuditCategory:
        return AuditCategory.COMPLETENESS

    @property
    def description(self) -> str:
        return "Columnas con más del 50% de valores NULL pueden indicar problemas de ingesta."

    def evaluate(self, connector, table_info, schema_metadata) -> list[AuditFinding]:
        findings = []

        for col in table_info.columns:
            if col.nullable is False:  # Columna declarada NOT NULL
                continue

            profile = schema_metadata.get_column_profile(table_info.name, col.name)
            if not profile or table_info.row_count == 0:
                continue

            null_pct = profile.null_percentage

            if null_pct >= 90:
                level = AuditLevel.WARNING
                msg = f"Columna '{col.name}' tiene {null_pct:.1f}% de valores NULL (casi vacía)."
            elif null_pct >= 50:
                level = AuditLevel.INFO
                msg = f"Columna '{col.name}' tiene {null_pct:.1f}% de valores NULL."
            else:
                continue

            findings.append(AuditFinding(
                table=table_info.name,
                column=col.name,
                level=level,
                category=self.category,
                rule_name=self.name,
                message=msg,
                affected_rows=profile.null_count,
                details={"null_percentage": round(null_pct, 2)},
            ))

        return findings


class CardinalityAnomalyRule(AuditRule):
    """Detecta anomalías de cardinalidad (columnas que deberían ser únicas pero tienen duplicados)."""

    @property
    def name(self) -> str:
        return "cardinality_anomaly"

    @property
    def category(self) -> AuditCategory:
        return AuditCategory.STATISTICAL

    @property
    def description(self) -> str:
        return "Columnas clasificadas como identificadores deben tener alta unicidad."

    def evaluate(self, connector, table_info, schema_metadata) -> list[AuditFinding]:
        findings = []

        for col in table_info.columns:
            profile = schema_metadata.get_column_profile(table_info.name, col.name)
            if not profile or not profile.semantic_label:
                continue

            # Aplicar solo a identificadores
            if profile.semantic_label.semantic_type != SemanticType.IDENTIFIER:
                continue
            if profile.semantic_label.confidence < 0.7:
                continue

            # Verificar unicidad
            if profile.uniqueness < 95.0 and profile.total_count > 10:
                dup_count = connector.count_duplicates(table_info.name, [col.name])
                if dup_count > 0:
                    findings.append(AuditFinding(
                        table=table_info.name,
                        column=col.name,
                        level=AuditLevel.WARNING,
                        category=self.category,
                        rule_name=self.name,
                        message=(
                            f"Columna '{col.name}' parece ser un identificador pero tiene "
                            f"{dup_count} duplicados (unicidad: {profile.uniqueness:.1f}%)."
                        ),
                        affected_rows=dup_count,
                        details={"uniqueness": round(profile.uniqueness, 2)},
                    ))

        return findings


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRO DE REGLAS POR DEFECTO
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_RULES: list[AuditRule] = [
    # Estructurales
    NullPrimaryKeyRule(),
    DuplicatePrimaryKeyRule(),
    InvalidDateRule(),
    NegativeValueRule(),
    EmptyStringRule(),
    # Completitud
    NullRequiredFieldRule(),
    HighNullRateRule(),
    # Relacionales
    OrphanedForeignKeyRule(),
    # Estadísticas
    OutlierDetectionRule(),
    ConstantColumnRule(),
    CardinalityAnomalyRule(),
]
