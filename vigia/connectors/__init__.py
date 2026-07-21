"""
vigia.connectors
-------------------
Capa de conectores para fuentes de datos heterogéneas.
Provee una interfaz unificada (BaseConnector) que abstrae el acceso
a SQLite, CSV, Excel, PostgreSQL, MySQL y futuras fuentes.
"""

from vigia.connectors.base import (
    BaseConnector,
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    TableInfo,
    ConnectionConfig,
)
from vigia.connectors.sqlite_connector import SQLiteConnector
from vigia.connectors.csv_connector import CSVConnector

__all__ = [
    "BaseConnector",
    "ColumnInfo",
    "ForeignKeyInfo",
    "IndexInfo",
    "TableInfo",
    "ConnectionConfig",
    "SQLiteConnector",
    "CSVConnector",
]
