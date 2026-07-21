import pytest
from pydantic import ValidationError
from vigia.models.validation import ProjectModel, TaskModel, CommunicationModel

def test_project_model_valid():
    """Verify that a valid project configuration is parsed successfully."""
    project_data = {
        "project_id": "P001",
        "name": "Phoenix Project",
        "status": "ACTIVE",
        "budget": 150000.0,
        "deadline": "2026-09-30"
    }
    project = ProjectModel(**project_data)
    assert project.project_id == "P001"
    assert project.budget == 150000.0
    assert project.deadline == "2026-09-30"

def test_project_model_invalid_budget():
    """Verify that a negative budget triggers a ValidationError."""
    project_data = {
        "project_id": "P004",
        "name": "Project Icarus",
        "status": "ACTIVE",
        "budget": -50000.0,
        "deadline": "2026-08-31"
    }
    with pytest.raises(ValidationError) as exc_info:
        ProjectModel(**project_data)
    
    assert "budget" in str(exc_info.value)
    assert "Budget must be non-negative" in str(exc_info.value)

def test_project_model_invalid_date():
    """Verify that an invalid deadline format triggers a ValidationError."""
    project_data = {
        "project_id": "P005",
        "name": "Nemesis Protocol",
        "status": "ACTIVE",
        "budget": 120000.0,
        "deadline": "2026-13-45"
    }
    with pytest.raises(ValidationError) as exc_info:
        ProjectModel(**project_data)
        
    assert "deadline" in str(exc_info.value)
    assert "Deadline must be a valid ISO date" in str(exc_info.value)

def test_task_model_valid():
    """Verify that a valid task configuration is parsed successfully."""
    task_data = {
        "task_id": "T001",
        "project_id": "P001",
        "assignee": "Alice",
        "status": "IN_PROGRESS",
        "updated_at": "2026-06-10T12:00:00"
    }
    task = TaskModel(**task_data)
    assert task.task_id == "T001"
    assert task.updated_at == "2026-06-10T12:00:00"

def test_task_model_invalid_ids():
    """Verify that null/missing/empty task_id triggers a ValidationError."""
    # Empty task_id
    with pytest.raises(ValidationError):
        TaskModel(task_id="", project_id="P001", assignee="Eve", status="IN_PROGRESS", updated_at="2026-06-10T12:00:00")
        
    # Missing task_id (None)
    with pytest.raises(ValidationError):
        TaskModel(task_id=None, project_id="P001", assignee="Eve", status="IN_PROGRESS", updated_at="2026-06-10T12:00:00")

def test_task_model_invalid_datetime():
    """Verify that an invalid updated_at datetime format triggers a ValidationError."""
    task_data = {
        "task_id": "T001",
        "project_id": "P001",
        "assignee": "Alice",
        "status": "IN_PROGRESS",
        "updated_at": "June 10th 2026"
    }
    with pytest.raises(ValidationError) as exc_info:
        TaskModel(**task_data)
    assert "updated_at" in str(exc_info.value)

def test_communication_model_valid():
    """Verify that a valid communication configuration is parsed successfully."""
    comm_data = {
        "message_id": "MSG001",
        "project_id": "P001",
        "channel": "slack",
        "summary": "Frontend UI design looks great.",
        "sentiment": 0.85,
        "timestamp": "2026-06-12T10:15:00"
    }
    comm = CommunicationModel(**comm_data)
    assert comm.message_id == "MSG001"
    assert comm.sentiment == 0.85

def test_communication_model_invalid_sentiment():
    """Verify that sentiment score outside [-1.0, 1.0] triggers a ValidationError."""
    comm_data = {
        "message_id": "MSG001",
        "project_id": "P001",
        "channel": "slack",
        "summary": "Frontend UI design looks great.",
        "sentiment": 1.5,  # Out of range!
        "timestamp": "2026-06-12T10:15:00"
    }
    with pytest.raises(ValidationError) as exc_info:
        CommunicationModel(**comm_data)
    assert "sentiment" in str(exc_info.value)
    assert "Sentiment score must be between -1.0 and 1.0" in str(exc_info.value)
