"""
vigia.connectors.sqlite_connector
-------------------------------------
Conector para bases de datos SQLite.
Soporta archivos .db/.sqlite locales y uploads en memoria (bytes).
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from typing import Any

from vigia.connectors.base import (
    BaseConnector,
    ColumnInfo,
    ConnectionConfig,
    ConnectorType,
    DataTypeCategory,
    ForeignKeyInfo,
    IndexInfo,
    TableInfo,
)


# Mapeo de tipos SQLite a categorías genéricas
_SQLITE_TYPE_MAP: dict[str, DataTypeCategory] = {
    "integer": DataTypeCategory.INTEGER,
    "int": DataTypeCategory.INTEGER,
    "bigint": DataTypeCategory.INTEGER,
    "smallint": DataTypeCategory.INTEGER,
    "tinyint": DataTypeCategory.INTEGER,
    "real": DataTypeCategory.FLOAT,
    "float": DataTypeCategory.FLOAT,
    "double": DataTypeCategory.FLOAT,
    "numeric": DataTypeCategory.FLOAT,
    "decimal": DataTypeCategory.FLOAT,
    "text": DataTypeCategory.TEXT,
    "varchar": DataTypeCategory.TEXT,
    "char": DataTypeCategory.TEXT,
    "nvarchar": DataTypeCategory.TEXT,
    "clob": DataTypeCategory.TEXT,
    "blob": DataTypeCategory.BLOB,
    "boolean": DataTypeCategory.BOOLEAN,
    "bool": DataTypeCategory.BOOLEAN,
    "date": DataTypeCategory.DATE,
    "datetime": DataTypeCategory.DATETIME,
    "timestamp": DataTypeCategory.TIMESTAMP,
    "json": DataTypeCategory.JSON,
}


def _normalize_sqlite_type(raw_type: str) -> DataTypeCategory:
    """Normaliza un tipo SQLite a su categoría genérica."""
    if not raw_type:
        return DataTypeCategory.TEXT  # SQLite permite columnas sin tipo

    # Quitar paréntesis y contenido (e.g., VARCHAR(255) -> VARCHAR)
    base_type = raw_type.split("(")[0].strip().lower()

    if base_type in _SQLITE_TYPE_MAP:
        return _SQLITE_TYPE_MAP[base_type]

    # Intentar match parcial
    for key, category in _SQLITE_TYPE_MAP.items():
        if key in base_type:
            return category

    return DataTypeCategory.UNKNOWN


class SQLiteConnector(BaseConnector):
    """
    Conector para bases de datos SQLite.
    
    Acepta:
    - file_path: ruta a un archivo .db/.sqlite existente
    - file_bytes: contenido binario (para uploads desde Streamlit)
    """

    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self._conn: sqlite3.Connection | None = None
        self._temp_file: str | None = None

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.SQLITE

    # ─── Ciclo de vida ───────────────────────────────────────────────────

    def connect(self) -> None:
        """Establece conexión a la base de datos SQLite."""
        if self._connected and self._conn:
            return

        db_path = self.config.file_path

        # Si se proporcionan bytes (upload), escribir a archivo temporal
        if self.config.file_bytes:
            fd, self._temp_file = tempfile.mkstemp(suffix=".db")
            os.close(fd)
            with open(self._temp_file, "wb") as f:
                f.write(self.config.file_bytes)
            db_path = self._temp_file

        if not db_path:
            raise ValueError("SQLiteConnector requiere file_path o file_bytes en la configuración.")

        if not self.config.file_bytes and not os.path.exists(db_path):
            raise FileNotFoundError(f"No se encontró el archivo de base de datos: {db_path}")

        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Habilitar foreign_keys para que PRAGMA foreign_key_list funcione
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._connected = True

    def disconnect(self) -> None:
        """Cierra la conexión y limpia archivos temporales."""
        if self._conn:
            self._conn.close()
            self._conn = None
        self._connected = False

        # Limpiar archivo temporal si fue creado
        if self._temp_file and os.path.exists(self._temp_file):
            try:
                os.remove(self._temp_file)
            except OSError:
                pass
            self._temp_file = None

    # ─── Introspección de esquema ────────────────────────────────────────

    def get_tables(self) -> list[str]:
        """Retorna las tablas de usuario (excluye tablas internas de SQLite)."""
        self._ensure_connected()
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_table_info(self, table: str) -> TableInfo:
        """Retorna metadatos completos de una tabla."""
        self._ensure_connected()

        # Obtener info de columnas via PRAGMA
        columns = self._get_columns(table)
        primary_keys = [col.name for col in columns if col.is_primary_key]
        foreign_keys = self.get_foreign_keys(table)
        indexes = self.get_indexes(table)
        row_count = self.get_row_count(table)

        return TableInfo(
            name=table,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
            indexes=indexes,
            row_count=row_count,
        )

    def _get_columns(self, table: str) -> list[ColumnInfo]:
        """Obtiene metadatos de columnas usando PRAGMA table_info."""
        cursor = self._conn.execute(f"PRAGMA table_info('{table}')")
        columns = []

        for row in cursor.fetchall():
            cid, name, col_type, notnull, default_val, pk = (
                row[0], row[1], row[2], row[3], row[4], row[5]
            )
            columns.append(ColumnInfo(
                name=name,
                raw_type=col_type or "TEXT",
                generic_type=_normalize_sqlite_type(col_type or ""),
                nullable=not bool(notnull),
                is_primary_key=bool(pk),
                is_unique=False,  # Se actualiza al procesar índices
                default_value=default_val,
                ordinal_position=cid + 1,
            ))

        # Marcar columnas con UNIQUE constraints
        indexes = self.get_indexes(table)
        for idx in indexes:
            if idx.is_unique and len(idx.columns) == 1:
                for col in columns:
                    if col.name == idx.columns[0]:
                        col.is_unique = True

        return columns

    def get_foreign_keys(self, table: str) -> list[ForeignKeyInfo]:
        """Obtiene claves foráneas declaradas via PRAGMA."""
        self._ensure_connected()
        cursor = self._conn.execute(f"PRAGMA foreign_key_list('{table}')")
        fks = []

        for row in cursor.fetchall():
            # Columns: id, seq, table, from, to, on_update, on_delete, match
            fks.append(ForeignKeyInfo(
                column=row[3],  # from
                referenced_table=row[2],  # table
                referenced_column=row[4],  # to
                constraint_name=None,
                is_inferred=False,
                confidence=1.0,
            ))

        return fks

    def get_indexes(self, table: str) -> list[IndexInfo]:
        """Obtiene índices de una tabla."""
        self._ensure_connected()
        cursor = self._conn.execute(f"PRAGMA index_list('{table}')")
        indexes = []

        for row in cursor.fetchall():
            idx_name = row[1]
            is_unique = bool(row[2])
            origin = row[3] if len(row) > 3 else ""  # 'c' = CREATE INDEX, 'u' = UNIQUE, 'pk' = PRIMARY

            # Obtener columnas del índice
            col_cursor = self._conn.execute(f"PRAGMA index_info('{idx_name}')")
            columns = [col_row[2] for col_row in col_cursor.fetchall()]

            indexes.append(IndexInfo(
                name=idx_name,
                columns=columns,
                is_unique=is_unique,
                is_primary=(origin == "pk"),
            ))

        return indexes

    # ─── Acceso a datos ──────────────────────────────────────────────────

    def get_row_count(self, table: str) -> int:
        """Cuenta filas en una tabla."""
        self._ensure_connected()
        cursor = self._conn.execute(f"SELECT COUNT(*) FROM [{table}]")
        return cursor.fetchone()[0]

    def sample_data(self, table: str, limit: int = 100) -> list[dict[str, Any]]:
        """Retorna una muestra de datos."""
        self._ensure_connected()
        cursor = self._conn.execute(f"SELECT * FROM [{table}] LIMIT ?", (limit,))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_column_values(self, table: str, column: str, limit: int = 1000) -> list[Any]:
        """Retorna valores de una columna para análisis."""
        self._ensure_connected()
        cursor = self._conn.execute(
            f"SELECT [{column}] FROM [{table}] WHERE [{column}] IS NOT NULL LIMIT ?",
            (limit,),
        )
        return [row[0] for row in cursor.fetchall()]

    def count_nulls(self, table: str, column: str) -> int:
        """Cuenta NULLs en una columna."""
        self._ensure_connected()
        cursor = self._conn.execute(
            f"SELECT COUNT(*) FROM [{table}] WHERE [{column}] IS NULL"
        )
        return cursor.fetchone()[0]

    def count_distinct(self, table: str, column: str) -> int:
        """Cuenta valores distintos."""
        self._ensure_connected()
        cursor = self._conn.execute(
            f"SELECT COUNT(DISTINCT [{column}]) FROM [{table}]"
        )
        return cursor.fetchone()[0]

    def count_duplicates(self, table: str, columns: list[str]) -> int:
        """Cuenta filas duplicadas basándose en las columnas especificadas."""
        self._ensure_connected()
        cols_sql = ", ".join(f"[{c}]" for c in columns)
        query = f"""
            SELECT SUM(cnt - 1) FROM (
                SELECT {cols_sql}, COUNT(*) as cnt 
                FROM [{table}] 
                GROUP BY {cols_sql} 
                HAVING COUNT(*) > 1
            )
        """
        cursor = self._conn.execute(query)
        result = cursor.fetchone()[0]
        return result if result else 0

    def get_numeric_stats(self, table: str, column: str) -> dict[str, float | None]:
        """Calcula estadísticas numéricas de una columna."""
        self._ensure_connected()
        
        # Estadísticas básicas disponibles en SQLite
        query = f"""
            SELECT 
                MIN(CAST([{column}] AS REAL)) as min_val,
                MAX(CAST([{column}] AS REAL)) as max_val,
                AVG(CAST([{column}] AS REAL)) as avg_val,
                COUNT([{column}]) as count_val
            FROM [{table}]
            WHERE [{column}] IS NOT NULL 
              AND typeof([{column}]) IN ('integer', 'real')
        """
        
        try:
            cursor = self._conn.execute(query)
            row = cursor.fetchone()
            
            if not row or row[3] == 0:  # count == 0
                return {"min": None, "max": None, "avg": None, "stddev": None, 
                        "median": None, "q1": None, "q3": None}

            # Para stddev, mediana y cuartiles necesitamos los valores
            values = self._get_numeric_values(table, column)
            
            if not values:
                return {
                    "min": row[0], "max": row[1], "avg": row[2],
                    "stddev": None, "median": None, "q1": None, "q3": None,
                }

            values.sort()
            n = len(values)
            
            # Calcular stddev
            avg = row[2]
            variance = sum((v - avg) ** 2 for v in values) / n if n > 0 else 0
            stddev = variance ** 0.5

            # Calcular cuartiles
            median = self._percentile(values, 0.5)
            q1 = self._percentile(values, 0.25)
            q3 = self._percentile(values, 0.75)

            return {
                "min": row[0], "max": row[1], "avg": row[2],
                "stddev": stddev, "median": median, "q1": q1, "q3": q3,
            }
        except (sqlite3.OperationalError, ValueError):
            return {"min": None, "max": None, "avg": None, "stddev": None,
                    "median": None, "q1": None, "q3": None}

    def check_referential_integrity(
        self, table: str, column: str, ref_table: str, ref_column: str
    ) -> list[Any]:
        """Retorna valores huérfanos (existen en table.column pero no en ref_table.ref_column)."""
        self._ensure_connected()
        query = f"""
            SELECT DISTINCT t.[{column}] 
            FROM [{table}] t
            WHERE t.[{column}] IS NOT NULL
              AND t.[{column}] NOT IN (SELECT [{ref_column}] FROM [{ref_table}] WHERE [{ref_column}] IS NOT NULL)
        """
        try:
            cursor = self._conn.execute(query)
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            return []

    # ─── Helpers internos ────────────────────────────────────────────────

    def _ensure_connected(self) -> None:
        """Verifica que hay conexión activa."""
        if not self._connected or not self._conn:
            raise RuntimeError("SQLiteConnector no está conectado. Llama a connect() primero.")

    def _get_numeric_values(self, table: str, column: str) -> list[float]:
        """Obtiene todos los valores numéricos no-null de una columna."""
        cursor = self._conn.execute(
            f"SELECT CAST([{column}] AS REAL) FROM [{table}] "
            f"WHERE [{column}] IS NOT NULL AND typeof([{column}]) IN ('integer', 'real')"
        )
        return [row[0] for row in cursor.fetchall()]

    @staticmethod
    def _percentile(sorted_values: list[float], p: float) -> float:
        """Calcula el percentil p (0-1) de una lista ordenada."""
        n = len(sorted_values)
        if n == 0:
            return 0.0
        if n == 1:
            return sorted_values[0]
        
        k = (n - 1) * p
        floor_k = int(k)
        ceil_k = floor_k + 1
        
        if ceil_k >= n:
            return sorted_values[-1]
        
        fraction = k - floor_k
        return sorted_values[floor_k] + fraction * (sorted_values[ceil_k] - sorted_values[floor_k])
