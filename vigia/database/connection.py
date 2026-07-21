import sqlite3
import os
from contextlib import contextmanager

# Default database file path
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
    "vigia.db"
)
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

@contextmanager
def get_connection(db_path=DEFAULT_DB_PATH):
    """
    Context manager that provides a SQLite connection.
    Automatically commits on success or rolls back on exception, and closes the connection.
    """
    conn = sqlite3.connect(db_path)
    # Enable dict-like row factory for easier dictionary-like access
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_db(db_path=DEFAULT_DB_PATH):
    """
    Initializes the SQLite database using schema.sql.
    """
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"Schema file not found at {SCHEMA_PATH}")
        
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
        
    with get_connection(db_path) as conn:
        conn.executescript(schema_sql)
        
    return db_path
