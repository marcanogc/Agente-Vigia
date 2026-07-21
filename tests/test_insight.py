import os
import tempfile
import pytest
from vigia.database.seed import seed_data
from vigia.insight.engine import InsightEngine

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

def test_insight_engine_sanitization(seeded_db):
    """Verify that only validated records are included in the analysis dataset."""
    engine = InsightEngine(seeded_db)
    analysis = engine.run_analysis()
    
    clean_stats = analysis["clean_stats"]
    
    # 5 projects total: P004 (negative budget) and P005 (invalid deadline) must be excluded
    # Remaining: P001, P002, P003. Total = 3
    assert clean_stats["projects_count"] == 3
    
    # 6 tasks total:
    # Excluded: Task with null task_id (structural error)
    # Excluded: Task T004 (orphaned task pointing to P009 - relational error)
    # Remaining: T001, T002, T003, T005. Total = 4
    assert clean_stats["tasks_count"] == 4
    
    # 6 communications: all are structurally valid and are retained in raw clean collection,
    # but only those referencing active valid projects are evaluated for sentiment risk.
    assert clean_stats["communications_count"] == 6

def test_insight_engine_risk_detection(seeded_db):
    """Verify that specific operational risks are correctly detected on the clean dataset."""
    engine = InsightEngine(seeded_db)
    analysis = engine.run_analysis()
    
    risk_register = analysis["risk_register"]
    
    # We expect 3 operational risks:
    # 1. Stagnant blocked task (T005 on project P002 - Frank)
    # 2. Highly negative communication (MSG003 on project P002 - sentiment -0.80)
    # 3. Close deadline risk (Project P002 deadline is 2026-07-15, which is 33 days from 2026-06-12)
    assert len(risk_register) == 3
    
    # Assert stagnant blocked task details
    stagnant_risks = [r for r in risk_register if r["risk_type"] == "Stagnant Blocked Task"]
    assert len(stagnant_risks) == 1
    assert stagnant_risks[0]["evidence_reference"] == "T005"
    assert stagnant_risks[0]["priority"] == "HIGH"
    
    # Assert negative sentiment details
    sentiment_risks = [r for r in risk_register if r["risk_type"] == "Negative Communication Sentiment"]
    assert len(sentiment_risks) == 1
    assert sentiment_risks[0]["evidence_reference"] == "MSG003"
    assert sentiment_risks[0]["priority"] == "HIGH"

    # Assert close deadline details
    deadline_risks = [r for r in risk_register if r["risk_type"] == "Close Deadline Risk"]
    assert len(deadline_risks) == 1
    assert deadline_risks[0]["evidence_reference"] == "P002"
    assert deadline_risks[0]["priority"] == "HIGH"  # P002 has a blocked task, so priority becomes HIGH

def test_insight_engine_report_generation(seeded_db):
    """Verifica que el reporte Markdown generado tiene estructura correcta y referencia elementos críticos."""
    engine = InsightEngine(seeded_db)
    analysis = engine.run_analysis()
    report = analysis["report_markdown"]

    # El reporte debe iniciar con el título de Agente Vigía
    assert "Agente Vigía" in report

    # Debe contener las secciones principales
    assert "Resumen Ejecutivo" in report or "Executive Summary" in report

    # Debe referenciar entidades críticas específicas
    assert "P002" in report
    assert "T005" in report
    assert "MSG003" in report
    assert "25.0" in report  # Score de confianza
