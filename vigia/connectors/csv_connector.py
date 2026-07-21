"""
vigia.connectors.csv_connector
---------------------------------
Conector para archivos CSV y Excel.
Carga los datos en una base SQLite en memoria para ofrecer la misma
interfaz de introspección y consultas que el conector SQLite.
"""

from __future__ import annotations

import csv
import io
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


def _infer_column_type(values: list[str]) -> DataTypeCategory:
    """
    Infiere el tipo de dato genérico a partir de una muestra de valores string.
    Analiza los primeros valores no-vacíos para determinar el tipo más probable.
    """
    # Filtrar valores vacíos y None
    sample = [v for v in values[:200] if v is not None and str(v).strip() != ""]

    if not sample:
        return DataTypeCategory.TEXT

    int_count = 0
    float_count = 0
    bool_count = 0
    date_count = 0

    bool_values = {"true", "false", "yes", "no", "1", "0", "si", "sí"}

    for val in sample:
        val_str = str(val).strip().lower()

        # Boolean check
        if val_str in bool_values:
            bool_count += 1
            continue

        # Integer check
        try:
            int(val_str)
            int_count += 1
            continue
        except ValueError:
            pass

        # Float check
        try:
            float(val_str.replace(",", "."))
            float_count += 1
            continue
        except ValueError:
            pass

        # Date check (patrones comunes)
        if _looks_like_date(val_str):
            date_count += 1

    total = len(sample)
    threshold = 0.7  # 70% de los valores deben ser del mismo tipo

    if int_count / total >= threshold:
        return DataTypeCategory.INTEGER
    if (int_count + float_count) / total >= threshold:
        return DataTypeCategory.FLOAT
    if bool_count / total >= threshold:
        return DataTypeCategory.BOOLEAN
    if date_count / total >= threshold:
        return DataTypeCategory.DATETIME

    return DataTypeCategory.TEXT


def _looks_like_date(val: str) -> bool:
    """Heurística simple para detectar strings que parecen fechas."""
    from datetime import datetime

    date_formats = [
        "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y",
        "%Y/%m/%d", "%d.%m.%Y",
    ]
    for fmt in date_formats:
        try:
            datetime.strptime(val, fmt)
            return True
        except ValueError:
            continue
    return False


def _sanitize_table_name(filename: str) -> str:
    """Genera un nombre de tabla válido a partir de un nombre de archivo."""
    # Quitar extensión y caracteres especiales
    name = os.path.splitext(os.path.basename(filename))[0]
    # Reemplazar caracteres no alfanuméricos con underscore
    sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    # Asegurar que no empiece con número
    if sanitized and sanitized[0].isdigit():
        sanitized = "t_" + sanitized
    return sanitized or "imported_data"


class CSVConnector(BaseConnector):
    """
    Conector para archivos CSV y Excel.
    
    Internamente carga los datos en SQLite en memoria para permitir
    consultas SQL y ofrecer la misma interfaz que SQLiteConnector.
    
    Acepta:
    - file_path: ruta a un archivo .csv o .xlsx
    - file_bytes: contenido binario (para uploads desde Streamlit)
    - options.encoding: encoding del archivo (default: utf-8)
    - options.delimiter: separador de columnas (default: auto-detect)
    - options.sheet_name: nombre de la hoja para Excel (default: primera hoja)
    """

    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self._conn: sqlite3.Connection | None = None
        self._table_names: list[str] = []

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.CSV

    # ─── Ciclo de vida ───────────────────────────────────────────────────

    def connect(self) -> None:
        """Carga el CSV/Excel en SQLite en memoria."""
        if self._connected and self._conn:
            return

        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        file_path = self.config.file_path
        file_bytes = self.config.file_bytes
        encoding = self.config.options.get("encoding", "utf-8")

        if file_bytes:
            # Detectar si es Excel por extensión en options o magic bytes
            file_ext = self.config.options.get("file_extension", ".csv").lower()
            if file_ext in (".xlsx", ".xls"):
                self._load_excel_bytes(file_bytes)
            else:
                content = file_bytes.decode(encoding)
                table_name = self.config.options.get("table_name", "imported_data")
                self._load_csv_content(content, table_name)
        elif file_path:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"No se encontró el archivo: {file_path}")

            ext = os.path.splitext(file_path)[1].lower()
            table_name = _sanitize_table_name(file_path)

            if ext in (".xlsx", ".xls"):
                self._load_excel_file(file_path)
            else:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                self._load_csv_content(content, table_name)
        else:
            raise ValueError("CSVConnector requiere file_path o file_bytes.")

        self._connected = True

    def disconnect(self) -> None:
        """Cierra la conexión en memoria."""
        if self._conn:
            self._conn.close()
            self._conn = None
        self._connected = False
        self._table_names = []

    # ─── Carga de datos ──────────────────────────────────────────────────

    def _load_csv_content(self, content: str, table_name: str) -> None:
        """Carga contenido CSV string en una tabla SQLite."""
        delimiter = self.config.options.get("delimiter")
        
        # Auto-detectar delimiter si no se especifica
        if not delimiter:
            sniffer = csv.Sniffer()
            try:
                sample = content[:8192]
                dialect = sniffer.sniff(sample, delimiters=",;\t|")
                delimiter = dialect.delimiter
            except csv.Error:
                delimiter = ","

        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)

        if not rows:
            return

        # Primera fila como headers
        headers = [h.strip() for h in rows[0]]
        # Sanitizar nombres de columnas
        headers = [self._sanitize_column_name(h, i) for i, h in enumerate(headers)]
        data_rows = rows[1:]

        if not data_rows:
            return

        # Inferir tipos de columnas
        col_types = []
        for col_idx in range(len(headers)):
            col_values = [row[col_idx] if col_idx < len(row) else "" for row in data_rows[:200]]
            col_types.append(_infer_column_type(col_values))

        # Crear tabla
        col_defs = []
        for header, col_type in zip(headers, col_types):
            sqlite_type = self._generic_to_sqlite_type(col_type)
            col_defs.append(f"[{header}] {sqlite_type}")

        create_sql = f"CREATE TABLE [{table_name}] ({', '.join(col_defs)})"
        self._conn.execute(create_sql)

        # Insertar datos
        placeholders = ", ".join(["?"] * len(headers))
        insert_sql = f"INSERT INTO [{table_name}] VALUES ({placeholders})"

        for row in data_rows:
            # Normalizar longitud de fila
            padded_row = row + [""] * (len(headers) - len(row))
            values = []
            for val, col_type in zip(padded_row[:len(headers)], col_types):
                values.append(self._cast_value(val, col_type))
            self._conn.execute(insert_sql, values)

        self._conn.commit()
        self._table_names.append(table_name)

    def _load_excel_file(self, file_path: str) -> None:
        """Carga un archivo Excel usando openpyxl o pandas."""
        try:
            import pandas as pd
            sheet_name = self.config.options.get("sheet_name", None)
            
            # Leer todas las hojas o la especificada
            if sheet_name:
                dfs = {sheet_name: pd.read_excel(file_path, sheet_name=sheet_name)}
            else:
                dfs = pd.read_excel(file_path, sheet_name=None)

            for name, df in dfs.items():
                table_name = _sanitize_table_name(str(name))
                self._load_dataframe(df, table_name)

        except ImportError:
            raise ImportError(
                "Para cargar archivos Excel se requiere el paquete 'openpyxl'. "
                "Instálalo con: pip install openpyxl"
            )

    def _load_excel_bytes(self, file_bytes: bytes) -> None:
        """Carga bytes de Excel."""
        try:
            import pandas as pd
            sheet_name = self.config.options.get("sheet_name", None)

            if sheet_name:
                dfs = {sheet_name: pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)}
            else:
                dfs = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)

            for name, df in dfs.items():
                table_name = _sanitize_table_name(str(name))
                self._load_dataframe(df, table_name)

        except ImportError:
            raise ImportError(
                "Para cargar archivos Excel se requiere el paquete 'openpyxl'. "
                "Instálalo con: pip install openpyxl"
            )

    def _load_dataframe(self, df, table_name: str) -> None:
        """Carga un DataFrame de pandas en SQLite."""
        import pandas as pd

        # Sanitizar nombres de columnas
        df.columns = [self._sanitize_column_name(str(c), i) for i, c in enumerate(df.columns)]
        
        # Usar pandas to_sql para la carga
        df.to_sql(table_name, self._conn, if_exists="replace", index=False)
        self._table_names.append(table_name)

    # ─── Introspección de esquema ────────────────────────────────────────

    def get_tables(self) -> list[str]:
        """Retorna las tablas cargadas."""
        self._ensure_connected()
        if self._table_names:
            return list(self._table_names)
        # Fallback: consultar SQLite
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_table_info(self, table: str) -> TableInfo:
        """Retorna metadatos de una tabla."""
        self._ensure_connected()
        columns = self._get_columns(table)
        row_count = self.get_row_count(table)

        return TableInfo(
            name=table,
            columns=columns,
            primary_keys=[],  # CSVs no tienen PKs declaradas
            foreign_keys=[],  # Se inferirán via SchemaInspector
            indexes=[],
            row_count=row_count,
        )

    def _get_columns(self, table: str) -> list[ColumnInfo]:
        """Obtiene columnas via PRAGMA."""
        cursor = self._conn.execute(f"PRAGMA table_info('{table}')")
        columns = []
        for row in cursor.fetchall():
            cid, name, col_type, notnull, default_val, pk = (
                row[0], row[1], row[2], row[3], row[4], row[5]
            )
            # Re-inferir tipo genérico basado en datos reales
            values = self.get_column_values(table, name, limit=200)
            generic_type = _infer_column_type([str(v) for v in values if v is not None])
            
            columns.append(ColumnInfo(
                name=name,
                raw_type=col_type or "TEXT",
                generic_type=generic_type,
                nullable=not bool(notnull),
                is_primary_key=bool(pk),
                is_unique=False,
                default_value=default_val,
                ordinal_position=cid + 1,
            ))
        return columns

    def get_foreign_keys(self, table: str) -> list[ForeignKeyInfo]:
        """CSVs no tienen FKs declaradas — se inferirán via SchemaInspector."""
        return []

    def get_indexes(self, table: str) -> list[IndexInfo]:
        """CSVs no tienen índices."""
        return []

    # ─── Acceso a datos ──────────────────────────────────────────────────

    def get_row_count(self, table: str) -> int:
        self._ensure_connected()
        cursor = self._conn.execute(f"SELECT COUNT(*) FROM [{table}]")
        return cursor.fetchone()[0]

    def sample_data(self, table: str, limit: int = 100) -> list[dict[str, Any]]:
        self._ensure_connected()
        cursor = self._conn.execute(f"SELECT * FROM [{table}] LIMIT ?", (limit,))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_column_values(self, table: str, column: str, limit: int = 1000) -> list[Any]:
        self._ensure_connected()
        try:
            cursor = self._conn.execute(
                f"SELECT [{column}] FROM [{table}] WHERE [{column}] IS NOT NULL LIMIT ?",
                (limit,),
            )
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            return []

    def count_nulls(self, table: str, column: str) -> int:
        self._ensure_connected()
        cursor = self._conn.execute(
            f"SELECT COUNT(*) FROM [{table}] WHERE [{column}] IS NULL OR TRIM([{column}]) = ''"
        )
        return cursor.fetchone()[0]

    def count_distinct(self, table: str, column: str) -> int:
        self._ensure_connected()
        cursor = self._conn.execute(
            f"SELECT COUNT(DISTINCT [{column}]) FROM [{table}]"
        )
        return cursor.fetchone()[0]

    def count_duplicates(self, table: str, columns: list[str]) -> int:
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
        """Calcula estadísticas numéricas."""
        self._ensure_connected()
        try:
            cursor = self._conn.execute(
                f"SELECT MIN(CAST([{column}] AS REAL)), MAX(CAST([{column}] AS REAL)), "
                f"AVG(CAST([{column}] AS REAL)), COUNT([{column}]) "
                f"FROM [{table}] WHERE [{column}] IS NOT NULL AND [{column}] != ''"
            )
            row = cursor.fetchone()
            if not row or row[3] == 0:
                return {"min": None, "max": None, "avg": None, "stddev": None,
                        "median": None, "q1": None, "q3": None}

            # Obtener valores para cuartiles
            val_cursor = self._conn.execute(
                f"SELECT CAST([{column}] AS REAL) FROM [{table}] "
                f"WHERE [{column}] IS NOT NULL AND [{column}] != '' "
                f"ORDER BY CAST([{column}] AS REAL)"
            )
            values = [r[0] for r in val_cursor.fetchall()]

            if not values:
                return {"min": row[0], "max": row[1], "avg": row[2],
                        "stddev": None, "median": None, "q1": None, "q3": None}

            n = len(values)
            avg = row[2]
            variance = sum((v - avg) ** 2 for v in values) / n if n > 0 else 0
            stddev = variance ** 0.5

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
        """Verifica integridad referencial."""
        self._ensure_connected()
        query = f"""
            SELECT DISTINCT t.[{column}] 
            FROM [{table}] t
            WHERE t.[{column}] IS NOT NULL AND TRIM(t.[{column}]) != ''
              AND t.[{column}] NOT IN (
                  SELECT [{ref_column}] FROM [{ref_table}] WHERE [{ref_column}] IS NOT NULL
              )
        """
        try:
            cursor = self._conn.execute(query)
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            return []

    # ─── Helpers ─────────────────────────────────────────────────────────

    def _ensure_connected(self) -> None:
        if not self._connected or not self._conn:
            raise RuntimeError("CSVConnector no está conectado. Llama a connect() primero.")

    @staticmethod
    def _sanitize_column_name(name: str, index: int) -> str:
        """Sanitiza un nombre de columna para SQL."""
        if not name or not name.strip():
            return f"column_{index}"
        sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in name.strip())
        if sanitized[0].isdigit():
            sanitized = "c_" + sanitized
        return sanitized

    @staticmethod
    def _generic_to_sqlite_type(col_type: DataTypeCategory) -> str:
        """Convierte tipo genérico a tipo SQLite para CREATE TABLE."""
        mapping = {
            DataTypeCategory.INTEGER: "INTEGER",
            DataTypeCategory.FLOAT: "REAL",
            DataTypeCategory.BOOLEAN: "INTEGER",
            DataTypeCategory.DATE: "TEXT",
            DataTypeCategory.DATETIME: "TEXT",
            DataTypeCategory.TIMESTAMP: "TEXT",
            DataTypeCategory.TEXT: "TEXT",
            DataTypeCategory.BLOB: "BLOB",
            DataTypeCategory.JSON: "TEXT",
            DataTypeCategory.UNKNOWN: "TEXT",
        }
        return mapping.get(col_type, "TEXT")

    @staticmethod
    def _cast_value(val: str, col_type: DataTypeCategory) -> Any:
        """Intenta castear un valor string al tipo apropiado."""
        if val is None or str(val).strip() == "":
            return None

        val_str = str(val).strip()

        if col_type == DataTypeCategory.INTEGER:
            try:
                return int(val_str)
            except ValueError:
                try:
                    return int(float(val_str))
                except ValueError:
                    return val_str

        if col_type == DataTypeCategory.FLOAT:
            try:
                return float(val_str.replace(",", "."))
            except ValueError:
                return val_str

        if col_type == DataTypeCategory.BOOLEAN:
            lower = val_str.lower()
            if lower in ("true", "yes", "si", "sí", "1"):
                return 1
            if lower in ("false", "no", "0"):
                return 0
            return val_str

        return val_str

    @staticmethod
    def _percentile(sorted_values: list[float], p: float) -> float:
        """Calcula percentil."""
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
