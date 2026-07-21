import os
import tempfile
import pytest
import sqlite3
from vigia.database.connection import init_db, get_connection

@pytest.fixture
def temp_db():
    """Fixture that creates a temporary database file and cleans it up after testing."""
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield temp_db_path
    try:
        os.remove(temp_db_path)
    except OSError:
        pass

def test_init_db(temp_db):
    """Verify that init_db creates the expected tables."""
    init_db(temp_db)
    
    with get_connection(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row['name'] for row in cursor.fetchall()]
        
        assert "projects" in tables
        assert "tasks" in tables
        assert "communications" in tables
        assert "sqlite_sequence" in tables  # Created automatically by AUTOINCREMENT

def test_insert_corrupted_data(temp_db):
    """
    Verify that surrogate key database design successfully ingests corrupted records
    (so that the application-level Audit Engine can evaluate them).
    """
    init_db(temp_db)
    
    with get_connection(temp_db) as conn:
        # 1. Insert corrupted project: negative budget & invalid date
        conn.execute(
            "INSERT INTO projects (project_id, name, status, budget, deadline) VALUES (?, ?, ?, ?, ?)",
            ("P001", "Project Corrupted", "ACTIVE", -50000.0, "2026-13-40")
        )
        
        # 2. Insert corrupted task: null task_id & orphaned project_id
        conn.execute(
            "INSERT INTO tasks (task_id, project_id, assignee, status, updated_at) VALUES (?, ?, ?, ?, ?)",
            (None, "P009", "Unassigned", "BLOCKED", "2026-06-12T16:00:00")
        )
        
        # 3. Insert communication: valid structure but contradictory context (audited later)
        conn.execute(
            "INSERT INTO communications (message_id, project_id, channel, summary, sentiment, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            ("MSG001", "P001", "slack", "Project status looks great but budget is negative!", 0.9, "2026-06-12T16:00:00")
        )
        
    with get_connection(temp_db) as conn:
        # Retrieve projects
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE project_id = 'P001'")
        project = cursor.fetchone()
        assert project is not None
        assert project['budget'] == -50000.0
        assert project['deadline'] == "2026-13-40"
        
        # Retrieve tasks
        cursor.execute("SELECT * FROM tasks WHERE project_id = 'P009'")
        task = cursor.fetchone()
        assert task is not None
        assert task['task_id'] is None
        
        # Retrieve communications
        cursor.execute("SELECT * FROM communications WHERE message_id = 'MSG001'")
        comm = cursor.fetchone()
        assert comm is not None
        assert comm['sentiment'] == 0.9
