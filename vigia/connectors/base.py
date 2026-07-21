"""
vigia.connectors.base
------------------------
Definiciones base para la capa de conectores:
- Dataclasses para metadatos de esquema (ColumnInfo, ForeignKeyInfo, IndexInfo, TableInfo)
- Configuración de conexión genérica (ConnectionConfig)
- Clase abstracta BaseConnector que todo conector debe implementar
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Enumeraciones
# ─────────────────────────────────────────────────────────────────────────────


class ConnectorType(str, Enum):
    """Tipos de conectores soportados."""
    SQLITE = "sqlite"
    CSV = "csv"
    EXCEL = "excel"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLSERVER = "sqlserver"
    ORACLE = "oracle"
    REST_API = "rest_api"


class DataTypeCategory(str, Enum):
    """Categorías genéricas de tipos de datos (independientes del motor)."""
    INTEGER = "integer"
    FLOAT = "float"
    TEXT = "text"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIMESTAMP = "timestamp"
    BLOB = "blob"
    JSON = "json"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses de metadatos
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ColumnInfo:
    """Metadatos de una columna individual."""
    name: str
    raw_type: str                          # Tipo tal como lo reporta el motor (TEXT, VARCHAR(255), etc.)
    generic_type: DataTypeCategory         # Tipo normalizado/genérico
    nullable: bool = True
    is_primary_key: bool = False
    is_unique: bool = False
    default_value: Any = None
    ordinal_position: int = 0             # Posición dentro de la tabla (1-indexed)


@dataclass
class ForeignKeyInfo:
    """Representa una relación de clave foránea."""
    column: str                            # Columna local
    referenced_table: str                  # Tabla referenciada
    referenced_column: str                 # Columna referenciada
    constraint_name: str | None = None     # Nombre del constraint (si existe)
    is_inferred: bool = False              # True si fue inferida por heurísticas, no declarada
    confidence: float = 1.0               # 1.0 para explícitas, < 1.0 para inferidas


@dataclass
class IndexInfo:
    """Metadatos de un índice."""
    name: str
    columns: list[str] = field(default_factory=list)
    is_unique: bool = False
    is_primary: bool = False


@dataclass
class TableInfo:
    """Metadatos completos de una tabla."""
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    primary_keys: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKeyInfo] = field(default_factory=list)
    indexes: list[IndexInfo] = field(default_factory=list)
    row_count: int = 0

    def get_column(self, name: str) -> ColumnInfo | None:
        """Obtiene una columna por nombre (case-insensitive)."""
        name_lower = name.lower()
        for col in self.columns:
            if col.name.lower() == name_lower:
                return col
        return None

    @property
    def column_names(self) -> list[str]:
        """Lista de nombres de columnas."""
        return [col.name for col in self.columns]


@dataclass
class ConnectionConfig:
    """Configuración genérica de conexión."""
    connector_type: ConnectorType
    # Para SQLite / CSV / Excel:
    file_path: str | None = None
    file_bytes: bytes | None = None        # Para uploads vía Streamlit
    # Para bases de datos remotas:
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    # Opciones adicionales (SSL, schema, etc.):
    options: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Clase abstracta base
# ─────────────────────────────────────────────────────────────────────────────


class BaseConnector(ABC):
    """
    Interfaz abstracta que todo conector de datos debe implementar.
    
    Provee operaciones de introspección de esquema y acceso a datos
    de forma uniforme, independiente del motor subyacente.
    """

    def __init__(self, config: ConnectionConfig):
        self.config = config
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    @abstractmethod
    def connector_type(self) -> ConnectorType:
        """Tipo de conector."""
        ...

    # ─── Ciclo de vida ───────────────────────────────────────────────────

    @abstractmethod
    def connect(self) -> None:
        """Establece la conexión a la fuente de datos."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Cierra la conexión y libera recursos."""
        ...

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

    # ─── Introspección de esquema ────────────────────────────────────────

    @abstractmethod
    def get_tables(self) -> list[str]:
        """Retorna la lista de nombres de tablas disponibles."""
        ...

    @abstractmethod
    def get_table_info(self, table: str) -> TableInfo:
        """Retorna metadatos completos de una tabla específica."""
        ...

    @abstractmethod
    def get_foreign_keys(self, table: str) -> list[ForeignKeyInfo]:
        """Retorna las claves foráneas declaradas de una tabla."""
        ...

    @abstractmethod
    def get_indexes(self, table: str) -> list[IndexInfo]:
        """Retorna los índices de una tabla."""
        ...

    # ─── Acceso a datos ──────────────────────────────────────────────────

    @abstractmethod
    def get_row_count(self, table: str) -> int:
        """Retorna el número total de filas en una tabla."""
        ...

    @abstractmethod
    def sample_data(self, table: str, limit: int = 100) -> list[dict[str, Any]]:
        """Retorna una muestra de datos de la tabla (primeras N filas)."""
        ...

    @abstractmethod
    def get_column_values(self, table: str, column: str, limit: int = 1000) -> list[Any]:
        """Retorna los valores de una columna específica (para análisis estadístico)."""
        ...

    @abstractmethod
    def count_nulls(self, table: str, column: str) -> int:
        """Cuenta valores NULL en una columna."""
        ...

    @abstractmethod
    def count_distinct(self, table: str, column: str) -> int:
        """Cuenta valores distintos en una columna."""
        ...

    @abstractmethod
    def count_duplicates(self, table: str, columns: list[str]) -> int:
        """Cuenta filas duplicadas basándose en las columnas especificadas."""
        ...

    @abstractmethod
    def get_numeric_stats(self, table: str, column: str) -> dict[str, float | None]:
        """
        Retorna estadísticas numéricas de una columna:
        {min, max, avg, stddev, median, q1, q3}
        Retorna valores None si la columna no es numérica.
        """
        ...

    @abstractmethod
    def check_referential_integrity(
        self, table: str, column: str, ref_table: str, ref_column: str
    ) -> list[Any]:
        """
        Verifica integridad referencial: retorna valores en table.column
        que NO existen en ref_table.ref_column (claves huérfanas).
        """
        ...

    # ─── Utilidades ──────────────────────────────────────────────────────

    def get_all_tables_info(self) -> list[TableInfo]:
        """Retorna metadatos de todas las tablas."""
        return [self.get_table_info(t) for t in self.get_tables()]

    def get_total_row_count(self) -> int:
        """Retorna la suma total de filas en todas las tablas."""
        return sum(self.get_row_count(t) for t in self.get_tables())
