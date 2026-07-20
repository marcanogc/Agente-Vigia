import os
import tempfile
import pytest
from sentinel.database.seed import seed_data
from sentinel.audit.engine import AuditEngine

@pytest.fixture
def seeded_db():
    """Fixture that initializes a temporary database, seeds it, and cleans up afterwards."""
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    seed_data(temp_db_path)
    yield temp_db_path
    try:
        os.remove(temp_db_path)
    except OSError:
        pass

def test_audit_engine_execution(seeded_db):
    """Verify that AuditEngine runs and correctly calculates the summary stats."""
    engine = AuditEngine(seeded_db)
    report = engine.run_audit()
    
    assert "quality_score" in report
    assert "summary" in report
    assert "logs" in report
    
    summary = report["summary"]
    # Total seeded records: 5 projects + 6 tasks + 6 communications = 17 records
    assert summary["total_records"] == 17
    # 3 records fail structural validation (P004, P005, and task with null task_id)
    assert summary["failed_records"] == 3
    assert summary["passed_records"] == 14

def test_audit_engine_structural_errors(seeded_db):
    """Verify that specific structural failures are captured in the logs."""
    engine = AuditEngine(seeded_db)
    report = engine.run_audit()
    logs = report["logs"]
    
    structural_errors = [log for log in logs if log["type"] == "STRUCTURAL"]
    assert len(structural_errors) == 3
    
    # 1. Project P004 negative budget
    p004_errors = [log for log in structural_errors if log["entity_id"] == "P004"]
    assert len(p004_errors) == 1
    assert "budget" in p004_errors[0]["message"]
    
    # 2. Project P005 invalid deadline date
    p005_errors = [log for log in structural_errors if log["entity_id"] == "P005"]
    assert len(p005_errors) == 1
    assert "deadline" in p005_errors[0]["message"]
    
    # 3. Task with null task_id
    task_null_errors = [log for log in structural_errors if log["table"] == "tasks" and log["entity_id"] is None]
    assert len(task_null_errors) == 1
    assert "task_id" in task_null_errors[0]["message"]

def test_audit_engine_relational_checks(seeded_db):
    """Verify that relational warnings and errors (orphaned records) are captured."""
    engine = AuditEngine(seeded_db)
    report = engine.run_audit()
    logs = report["logs"]
    
    relational_logs = [log for log in logs if log["type"] == "RELATIONAL"]
    assert len(relational_logs) == 3
    
    # 1. Task T004 (orphaned task pointing to project P009) - ERROR level
    t004_errors = [log for log in relational_logs if log["entity_id"] == "T004"]
    assert len(t004_errors) == 1
    assert t004_errors[0]["level"] == "ERROR"
    assert "P009" in t004_errors[0]["message"]
    
    # 2. Comm MSG005 (missing project reference) - WARNING level
    msg005_logs = [log for log in relational_logs if log["entity_id"] == "MSG005"]
    assert len(msg005_logs) == 1
    assert msg005_logs[0]["level"] == "WARNING"
    assert "lack" in msg005_logs[0]["message"].lower() or "missing" in msg005_logs[0]["message"].lower()
    
    # 3. Comm MSG006 (orphaned project reference P009) - WARNING level
    msg006_logs = [log for log in relational_logs if log["entity_id"] == "MSG006"]
    assert len(msg006_logs) == 1
    assert msg006_logs[0]["level"] == "WARNING"
    assert "P009" in msg006_logs[0]["message"]

def test_audit_engine_semantic_checks(seeded_db):
    """Verify that semantic warnings (stagnant blocked tasks and contradictory sentiments) are captured."""
    engine = AuditEngine(seeded_db)
    report = engine.run_audit()
    logs = report["logs"]
    
    semantic_logs = [log for log in logs if log["type"] == "SEMANTIC"]
    assert len(semantic_logs) == 2
    
    # 1. Stagnant blocked task (T005 - BLOCKED since January)
    t005_warnings = [log for log in semantic_logs if log["entity_id"] == "T005"]
    assert len(t005_warnings) == 1
    assert "BLOCKED" in t005_warnings[0]["message"]
    assert "stagnant" in t005_warnings[0]["message"].lower() or "operational risk" in t005_warnings[0]["message"].lower()
    
    # 2. Contradictory signal (Project P002 status is ACTIVE, but negative slack communication MSG003)
    p002_warnings = [log for log in semantic_logs if log["entity_id"] == "P002"]
    assert len(p002_warnings) == 1
    assert "ACTIVE" in p002_warnings[0]["message"]
    assert "negative sentiment" in p002_warnings[0]["message"]

def test_data_quality_score_calculation(seeded_db):
    """
    Verify the final calculated quality score.
    Starting Score: 100.0
    Deductions:
      - 3 Structural errors: 3 * -15 = -45
      - 1 Relational error (Task): -10
      - 2 Relational warnings (Comms): 2 * -5 = -10
      - 2 Semantic warnings: 2 * -5 = -10
    Expected Score: 100.0 - 75.0 = 25.0
    """
    engine = AuditEngine(seeded_db)
    report = engine.run_audit()
    
    assert report["quality_score"] == 25.0
