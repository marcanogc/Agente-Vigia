import os
import tempfile
import pytest
from vigia.database.connection import get_connection
from vigia.database.seed import seed_data

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

def test_seed_data(temp_db):
    """Verify that seed_data correctly populates all tables with the expected number of records."""
    seed_data(temp_db)
    
    with get_connection(temp_db) as conn:
        cursor = conn.cursor()
        
        # Check counts
        cursor.execute("SELECT COUNT(*) as cnt FROM projects;")
        assert cursor.fetchone()['cnt'] == 5
        
        cursor.execute("SELECT COUNT(*) as cnt FROM tasks;")
        assert cursor.fetchone()['cnt'] == 6
        
        cursor.execute("SELECT COUNT(*) as cnt FROM communications;")
        assert cursor.fetchone()['cnt'] == 6

def test_seed_data_corruptions(temp_db):
    """Assert that the seed data contains the exact corrupted records we need to test our Audit Engine."""
    seed_data(temp_db)
    
    with get_connection(temp_db) as conn:
        cursor = conn.cursor()
        
        # 1. Negative budget project check
        cursor.execute("SELECT * FROM projects WHERE budget < 0;")
        neg_budget_projects = cursor.fetchall()
        assert len(neg_budget_projects) == 1
        assert neg_budget_projects[0]['project_id'] == "P004"
        
        # 2. Invalid deadline format project check
        cursor.execute("SELECT * FROM projects WHERE project_id = 'P005';")
        invalid_date_project = cursor.fetchone()
        assert invalid_date_project['deadline'] == "2026-13-45"
        
        # 3. Orphaned task check (project_id P009 does not exist in projects)
        cursor.execute("""
            SELECT * FROM tasks 
            WHERE project_id NOT IN (SELECT project_id FROM projects)
        """)
        orphaned_tasks = cursor.fetchall()
        assert len(orphaned_tasks) == 1
        assert orphaned_tasks[0]['task_id'] == "T004"
        
        # 4. Null task_id task check
        cursor.execute("SELECT * FROM tasks WHERE task_id IS NULL;")
        null_id_tasks = cursor.fetchall()
        assert len(null_id_tasks) == 1
        assert null_id_tasks[0]['project_id'] == "P001"
        
        # 5. Stagnant blocked task check
        cursor.execute("SELECT * FROM tasks WHERE status = 'BLOCKED';")
        blocked_tasks = cursor.fetchall()
        assert len(blocked_tasks) == 1
        assert blocked_tasks[0]['task_id'] == "T005"
        assert blocked_tasks[0]['updated_at'] == "2026-01-10T08:00:00"
        
        # 6. Contradictory communications check
        cursor.execute("SELECT * FROM communications WHERE sentiment < 0;")
        negative_comms = cursor.fetchall()
        assert len(negative_comms) == 2  # MSG003 (-0.80) and MSG004 (-0.20)
