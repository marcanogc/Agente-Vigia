"""
vigia.inspector.schema_inspector
------------------------------------
Motor de introspección que analiza cualquier fuente de datos a través
de un conector y genera SchemaMetadata completa incluyendo:
- Metadatos de tablas y columnas
- Perfiles estadísticos
- Clasificación semántica de columnas
- Inferencia de relaciones no declaradas
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from vigia.connectors.base import (
    BaseConnector,
    DataTypeCategory,
    ForeignKeyInfo,
    TableInfo,
)
from vigia.models.schema_models import (
    ColumnProfile,
    InferredRelationship,
    SchemaMetadata,
    SemanticLabel,
    SemanticType,
)


# ─────────────────────────────────────────────────────────────────────────────
# Patrones para clasificación semántica
# ─────────────────────────────────────────────────────────────────────────────

_SEMANTIC_PATTERNS: list[tuple[str, SemanticType, float]] = [
    # (regex para nombre de columna, tipo semántico, confianza base)
    # Identificadores
    (r"^(id|pk|key)$", SemanticType.IDENTIFIER, 0.95),
    (r"_id$|_pk$|_key$", SemanticType.IDENTIFIER, 0.90),
    (r"^id_|^pk_|^key_", SemanticType.IDENTIFIER, 0.85),
    (r"(code|codigo|cod)$", SemanticType.IDENTIFIER, 0.80),
    # Emails
    (r"e?mail", SemanticType.EMAIL, 0.90),
    (r"correo", SemanticType.EMAIL, 0.85),
    # Teléfonos
    (r"(phone|tel|telefono|celular|mobile|fax)", SemanticType.PHONE, 0.85),
    # URLs
    (r"(url|link|href|website|sitio)", SemanticType.URL, 0.85),
    # Nombres
    (r"^(name|nombre|first_name|last_name|apellido|titulo|title)$", SemanticType.NAME, 0.90),
    (r"(_name|_nombre)$", SemanticType.NAME, 0.80),
    # Fechas
    (r"(date|fecha|created_at|updated_at|deleted_at|born|nacimiento|expir)", SemanticType.DATE, 0.85),
    (r"(_at|_on|_date)$", SemanticType.DATETIME, 0.85),
    (r"^(timestamp|ts)$", SemanticType.DATETIME, 0.90),
    # Monetario
    (r"(price|precio|cost|costo|salary|salario|budget|presupuesto|amount|monto|revenue|ingreso|profit|ganancia|balance|total|subtotal|tax|impuesto|fee|tarifa|payment|pago)", SemanticType.MONETARY, 0.80),
    # Porcentajes
    (r"(percent|porcentaje|pct|ratio|tasa|rate)(?!_id)", SemanticType.PERCENTAGE, 0.80),
    (r"(discount|descuento|margin|margen|commission|comision)", SemanticType.PERCENTAGE, 0.70),
    # Probabilidades
    (r"(probability|probabilidad|confidence|confianza|score|puntuacion|likelihood)", SemanticType.PROBABILITY, 0.70),
    (r"(sentiment|sentimiento)", SemanticType.PROBABILITY, 0.75),
    # Cantidades
    (r"(count|quantity|cantidad|qty|num_|number_of|total_|stock)", SemanticType.QUANTITY, 0.75),
    # Mediciones
    (r"(weight|peso|height|altura|temperature|temperatura|length|longitud|width|ancho|distance|distancia|speed|velocidad|size|tamaño)", SemanticType.MEASUREMENT, 0.80),
    # Categóricos
    (r"(status|estado|type|tipo|category|categoria|level|nivel|class|clase|group|grupo|priority|prioridad|role|rol|gender|genero|country|pais|city|ciudad|region)", SemanticType.CATEGORICAL, 0.80),
    # Booleanos
    (r"(is_|has_|can_|flag_|active|activo|enabled|deleted|visible|verified|approved)", SemanticType.BOOLEAN, 0.85),
    # Direcciones
    (r"(address|direccion|street|calle|city|ciudad|state|zip|postal|cp)", SemanticType.ADDRESS, 0.75),
    # Geográficos
    (r"(lat|lng|lon|latitude|longitude|latitud|longitud|coord)", SemanticType.GEOGRAPHIC, 0.85),
]

# Patrones de email regex para validar en datos
_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_URL_REGEX = re.compile(r"^https?://|^www\.", re.IGNORECASE)


class SchemaInspector:
    """
    Inspector de esquema que genera metadatos completos de cualquier fuente de datos.
    
    Responsabilidades:
    1. Introspección de estructura (tablas, columnas, tipos, PKs, FKs)
    2. Perfilado estadístico de cada columna
    3. Clasificación semántica con nivel de confianza
    4. Inferencia de relaciones no declaradas
    5. Reporte de limitaciones
    """

    def __init__(self, connector: BaseConnector, sample_size: int = 500):
        """
        Args:
            connector: Conector ya conectado a la fuente de datos.
            sample_size: Tamaño de muestra para análisis estadístico y heurísticas.
        """
        self.connector = connector
        self.sample_size = sample_size

    def inspect(self) -> SchemaMetadata:
        """
        Ejecuta la inspección completa del esquema.
        Retorna SchemaMetadata con toda la información descubierta.
        """
        tables = self.connector.get_tables()
        limitations: list[str] = []

        if not tables:
            limitations.append("No se encontraron tablas en la fuente de datos.")
            return SchemaMetadata(limitations=limitations)

        # 1. Obtener metadatos de cada tabla
        table_infos: list[TableInfo] = []
        for table_name in tables:
            try:
                info = self.connector.get_table_info(table_name)
                table_infos.append(info)
            except Exception as e:
                limitations.append(f"No se pudo inspeccionar la tabla '{table_name}': {e}")

        # 2. Perfilar cada columna
        column_profiles: list[ColumnProfile] = []
        for table_info in table_infos:
            for col in table_info.columns:
                try:
                    profile = self._profile_column(table_info.name, col.name, col.generic_type, table_info.row_count)
                    column_profiles.append(profile)
                except Exception as e:
                    limitations.append(
                        f"No se pudo perfilar '{table_info.name}.{col.name}': {e}"
                    )

        # 3. Clasificación semántica
        for profile in column_profiles:
            profile.semantic_label = self._classify_semantically(profile)

        # 4. Recopilar relaciones declaradas
        declared_rels: list[ForeignKeyInfo] = []
        for table_info in table_infos:
            declared_rels.extend(table_info.foreign_keys)

        # 5. Inferir relaciones no declaradas
        inferred_rels = self._infer_relationships(table_infos, column_profiles, declared_rels)

        # 6. Estadísticas globales
        total_rows = sum(t.row_count for t in table_infos)
        total_cols = sum(len(t.columns) for t in table_infos)

        return SchemaMetadata(
            tables=table_infos,
            column_profiles=column_profiles,
            declared_relationships=declared_rels,
            inferred_relationships=inferred_rels,
            limitations=limitations,
            total_tables=len(table_infos),
            total_columns=total_cols,
            total_rows=total_rows,
        )

    # ─── Perfilado de columnas ───────────────────────────────────────────

    def _profile_column(
        self, table: str, column: str, data_type: DataTypeCategory, row_count: int
    ) -> ColumnProfile:
        """Genera el perfil estadístico de una columna."""
        profile = ColumnProfile(
            table_name=table,
            column_name=column,
            data_type=data_type,
            total_count=row_count,
        )

        # Conteos básicos
        profile.null_count = self.connector.count_nulls(table, column)
        profile.distinct_count = self.connector.count_distinct(table, column)

        # Muestra de valores
        try:
            sample_values = self.connector.get_column_values(table, column, limit=self.sample_size)
            profile.sample_values = sample_values[:20]  # Solo guardar 20 para el reporte
        except Exception:
            sample_values = []

        # Valores más frecuentes
        profile.most_frequent_values = self._get_most_frequent(table, column)

        # Estadísticas numéricas
        if data_type in (DataTypeCategory.INTEGER, DataTypeCategory.FLOAT):
            stats = self.connector.get_numeric_stats(table, column)
            profile.min_value = stats.get("min")
            profile.max_value = stats.get("max")
            profile.avg_value = stats.get("avg")
            profile.stddev_value = stats.get("stddev")
            profile.median_value = stats.get("median")
            profile.q1_value = stats.get("q1")
            profile.q3_value = stats.get("q3")

        # Estadísticas de texto
        elif data_type == DataTypeCategory.TEXT and sample_values:
            str_values = [str(v) for v in sample_values if v is not None]
            if str_values:
                lengths = [len(s) for s in str_values]
                profile.min_length = min(lengths)
                profile.max_length = max(lengths)
                profile.avg_length = sum(lengths) / len(lengths)

        # Contar empty strings (para columnas de texto)
        if data_type == DataTypeCategory.TEXT:
            profile.empty_string_count = self._count_empty_strings(table, column)

        return profile

    def _get_most_frequent(self, table: str, column: str, top_n: int = 5) -> list[tuple[Any, int]]:
        """Obtiene los N valores más frecuentes de una columna."""
        try:
            # Usar el connector para obtener valores y contar manualmente
            # (No todos los conectores soportan GROUP BY directamente)
            values = self.connector.get_column_values(table, column, limit=self.sample_size)
            if not values:
                return []

            freq: dict[Any, int] = {}
            for v in values:
                freq[v] = freq.get(v, 0) + 1

            sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
            return sorted_freq[:top_n]
        except Exception:
            return []

    def _count_empty_strings(self, table: str, column: str) -> int:
        """Cuenta strings vacíos (no NULL, pero '') en una columna."""
        try:
            values = self.connector.get_column_values(table, column, limit=self.sample_size)
            empty_count = sum(1 for v in values if isinstance(v, str) and v.strip() == "")
            # Extrapolar si estamos usando sample
            total = self.connector.get_row_count(table)
            if len(values) < total and len(values) > 0:
                ratio = empty_count / len(values)
                return int(ratio * total)
            return empty_count
        except Exception:
            return 0

    # ─── Clasificación semántica ─────────────────────────────────────────

    def _classify_semantically(self, profile: ColumnProfile) -> SemanticLabel:
        """
        Clasifica semánticamente una columna usando:
        1. Patrones en el nombre de la columna
        2. Análisis de los valores reales
        3. Tipo de dato y distribución
        """
        column_name = profile.column_name.lower()
        candidates: list[tuple[SemanticType, float, str]] = []

        # 1. Matching por nombre de columna
        for pattern, sem_type, base_confidence in _SEMANTIC_PATTERNS:
            if re.search(pattern, column_name, re.IGNORECASE):
                candidates.append((sem_type, base_confidence, f"Nombre '{profile.column_name}' coincide con patrón '{pattern}'"))
                break  # Solo el primer match por nombre

        # 2. Análisis por valores
        value_classification = self._classify_by_values(profile)
        if value_classification:
            candidates.append(value_classification)

        # 3. Análisis por tipo de dato y distribución
        type_classification = self._classify_by_type_and_distribution(profile)
        if type_classification:
            candidates.append(type_classification)

        # Seleccionar la clasificación con mayor confianza
        if not candidates:
            return SemanticLabel(
                semantic_type=SemanticType.UNKNOWN,
                confidence=0.0,
                reasoning="No se pudo determinar la semántica de esta columna.",
            )

        # Si hay múltiples candidatos que coinciden, aumentar confianza
        best = max(candidates, key=lambda x: x[1])
        
        # Verificar si hay consenso entre candidatos
        same_type_count = sum(1 for c in candidates if c[0] == best[0])
        confidence_boost = min(0.1 * (same_type_count - 1), 0.1)
        final_confidence = min(best[1] + confidence_boost, 1.0)

        constraints = self._infer_constraints(best[0], profile)

        return SemanticLabel(
            semantic_type=best[0],
            confidence=round(final_confidence, 2),
            reasoning=best[2],
            constraints=constraints,
        )

    def _classify_by_values(self, profile: ColumnProfile) -> tuple[SemanticType, float, str] | None:
        """Clasifica basándose en los valores reales de la columna."""
        sample = profile.sample_values
        if not sample:
            return None

        str_values = [str(v) for v in sample if v is not None]
        if not str_values:
            return None

        # Detectar emails
        email_matches = sum(1 for v in str_values if _EMAIL_REGEX.match(v))
        if email_matches / len(str_values) >= 0.7:
            return (SemanticType.EMAIL, 0.95, "70%+ de valores son emails válidos")

        # Detectar URLs
        url_matches = sum(1 for v in str_values if _URL_REGEX.match(v))
        if url_matches / len(str_values) >= 0.7:
            return (SemanticType.URL, 0.90, "70%+ de valores son URLs")

        # Detectar booleanos por valores
        if profile.distinct_count <= 3 and profile.data_type in (DataTypeCategory.TEXT, DataTypeCategory.INTEGER):
            unique_lower = {str(v).lower() for v in str_values}
            bool_sets = [
                {"true", "false"}, {"yes", "no"}, {"si", "no"},
                {"1", "0"}, {"activo", "inactivo"}, {"active", "inactive"},
            ]
            for bool_set in bool_sets:
                if unique_lower.issubset(bool_set | {""}):
                    return (SemanticType.BOOLEAN, 0.90, f"Valores son un set binario: {unique_lower}")

        # Detectar categóricos por baja cardinalidad
        if profile.distinct_count <= 20 and profile.total_count > 50:
            ratio = profile.distinct_count / max(profile.total_count - profile.null_count, 1)
            if ratio < 0.05:
                return (SemanticType.CATEGORICAL, 0.75, f"Baja cardinalidad: {profile.distinct_count} valores distintos sobre {profile.total_count} registros")

        return None

    def _classify_by_type_and_distribution(self, profile: ColumnProfile) -> tuple[SemanticType, float, str] | None:
        """Clasifica basándose en el tipo de dato y la distribución estadística."""
        # Detectar probabilidades/porcentajes por rango
        if profile.data_type in (DataTypeCategory.FLOAT, DataTypeCategory.INTEGER):
            if profile.min_value is not None and profile.max_value is not None:
                # Rango 0-1 -> Probabilidad
                if 0.0 <= profile.min_value and profile.max_value <= 1.0 and profile.data_type == DataTypeCategory.FLOAT:
                    return (SemanticType.PROBABILITY, 0.65, f"Rango [{profile.min_value}, {profile.max_value}] sugiere probabilidad (0-1)")

                # Rango 0-100 -> Posible porcentaje
                if 0.0 <= profile.min_value and profile.max_value <= 100.0:
                    # Solo si el promedio está en un rango razonable para porcentaje
                    if profile.avg_value is not None and 0.0 < profile.avg_value < 100.0:
                        return (SemanticType.PERCENTAGE, 0.50, f"Rango [0, 100] podría ser porcentaje (confianza baja)")

        # Identificadores por alta unicidad
        if profile.uniqueness > 95.0 and profile.data_type in (DataTypeCategory.TEXT, DataTypeCategory.INTEGER):
            if profile.total_count > 10:
                return (SemanticType.IDENTIFIER, 0.70, f"Alta unicidad ({profile.uniqueness:.0f}%) sugiere identificador")

        return None

    def _infer_constraints(self, sem_type: SemanticType, profile: ColumnProfile) -> dict[str, Any]:
        """Infiere constraints basadas en el tipo semántico."""
        constraints: dict[str, Any] = {}

        if sem_type == SemanticType.PROBABILITY:
            constraints["min"] = 0.0
            constraints["max"] = 1.0
        elif sem_type == SemanticType.PERCENTAGE:
            constraints["min"] = 0.0
            constraints["max"] = 100.0
        elif sem_type == SemanticType.MONETARY:
            constraints["min"] = 0.0  # Normalmente no negativo
        elif sem_type == SemanticType.QUANTITY:
            constraints["min"] = 0
        elif sem_type == SemanticType.IDENTIFIER:
            constraints["unique"] = True
            constraints["not_null"] = True

        return constraints

    # ─── Inferencia de relaciones ────────────────────────────────────────

    def _infer_relationships(
        self,
        tables: list[TableInfo],
        profiles: list[ColumnProfile],
        declared: list[ForeignKeyInfo],
    ) -> list[InferredRelationship]:
        """
        Infiere relaciones entre tablas que no están declaradas como FKs.
        
        Métodos:
        1. Convención de nombres (column_name = table_id o table_name_id)
        2. Overlap de valores entre columnas
        """
        inferred: list[InferredRelationship] = []
        
        # Set de relaciones ya declaradas para no duplicar
        declared_set = {
            (fk.column, fk.referenced_table, fk.referenced_column)
            for fk in declared
        }

        table_names = {t.name.lower(): t for t in tables}
        
        # Para cada tabla, buscar columnas que podrían ser FKs
        for table in tables:
            for col in table.columns:
                col_name_lower = col.name.lower()

                # Método 1: Convención de nombres
                # Patrón: <table_name>_id o <table_name>_pk
                candidate_refs = self._find_table_reference_by_name(col_name_lower, table_names, table.name)
                
                for ref_table, ref_column, confidence, method in candidate_refs:
                    # Verificar que no está ya declarada
                    if (col.name, ref_table, ref_column) in declared_set:
                        continue

                    # Método 2: Verificar overlap de valores para aumentar/disminuir confianza
                    adjusted_confidence = self._verify_relationship_by_values(
                        table.name, col.name, ref_table, ref_column, confidence
                    )

                    if adjusted_confidence >= 0.5:  # Umbral mínimo
                        inferred.append(InferredRelationship(
                            source_table=table.name,
                            source_column=col.name,
                            target_table=ref_table,
                            target_column=ref_column,
                            confidence=round(adjusted_confidence, 2),
                            method=method,
                            reasoning=f"Columna '{col.name}' en '{table.name}' probablemente referencia '{ref_table}.{ref_column}'"
                        ))

        return inferred

    def _find_table_reference_by_name(
        self, col_name: str, table_names: dict[str, TableInfo], current_table: str
    ) -> list[tuple[str, str, float, str]]:
        """
        Busca si un nombre de columna sugiere una referencia a otra tabla.
        Retorna: [(ref_table, ref_column, confidence, method), ...]
        """
        results = []

        # Patrón 1: column_name termina en _id
        if col_name.endswith("_id"):
            prefix = col_name[:-3]  # Quitar _id
            
            # Buscar tabla que coincida con el prefijo
            for table_name, table_info in table_names.items():
                if table_name == current_table.lower():
                    continue

                # Match: "project_id" -> tabla "project" o "projects"
                if table_name == prefix or table_name == prefix + "s" or table_name.rstrip("s") == prefix:
                    # Estrategia 1: Si la tabla tiene una columna con el mismo nombre (col_name),
                    # esa es la referencia más probable (business key)
                    same_name_col = table_info.get_column(col_name)
                    if same_name_col:
                        results.append((table_info.name, same_name_col.name, 0.90, "name_convention"))
                    else:
                        # Estrategia 2: Usar la PK de la tabla referenciada
                        pk_col = self._get_primary_key_column(table_info)
                        if pk_col:
                            results.append((table_info.name, pk_col, 0.85, "name_convention"))

        # Patrón 2: column_name es exactamente el nombre de una tabla + "id" sin underscore
        # e.g., "projectid" -> tabla "project"
        for table_name, table_info in table_names.items():
            if table_name == current_table.lower():
                continue
            if col_name == table_name + "id" or col_name == table_name + "_pk":
                same_name_col = table_info.get_column(col_name)
                if same_name_col:
                    results.append((table_info.name, same_name_col.name, 0.80, "name_convention"))
                else:
                    pk_col = self._get_primary_key_column(table_info)
                    if pk_col:
                        results.append((table_info.name, pk_col, 0.75, "name_convention"))

        return results

    def _get_primary_key_column(self, table_info: TableInfo) -> str | None:
        """Obtiene la columna de clave primaria principal de una tabla."""
        if table_info.primary_keys:
            return table_info.primary_keys[0]
        # Buscar columna marcada como PK
        for col in table_info.columns:
            if col.is_primary_key:
                return col.name
        # Buscar columna con nombre "id"
        for col in table_info.columns:
            if col.name.lower() == "id":
                return col.name
        return None

    def _verify_relationship_by_values(
        self, source_table: str, source_col: str, 
        target_table: str, target_col: str, base_confidence: float
    ) -> float:
        """
        Verifica una relación candidata comparando valores reales.
        Ajusta la confianza hacia arriba o abajo según el overlap.
        """
        try:
            orphans = self.connector.check_referential_integrity(
                source_table, source_col, target_table, target_col
            )
            
            # Obtener total de valores no-null en la columna fuente
            source_values = self.connector.get_column_values(source_table, source_col, limit=200)
            non_null_count = len(source_values)
            
            if non_null_count == 0:
                return base_confidence * 0.5  # Sin datos para verificar

            orphan_ratio = len(orphans) / non_null_count

            if orphan_ratio == 0:
                # Todos los valores existen en la tabla referenciada -> alta confianza
                return min(base_confidence + 0.10, 1.0)
            elif orphan_ratio < 0.1:
                # Pocas excepciones -> mantener confianza
                return base_confidence
            elif orphan_ratio < 0.3:
                # Algunas excepciones -> reducir un poco
                return base_confidence * 0.7
            else:
                # Muchos huérfanos -> probablemente no es una relación real
                return base_confidence * 0.3

        except Exception:
            # Si no se puede verificar, mantener confianza base reducida
            return base_confidence * 0.6
