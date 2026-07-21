from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from typing import Optional

class ProjectModel(BaseModel):
    """Pydantic model representing a validated project record."""
    project_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    budget: float
    deadline: str  # Kept as string but validated as ISO date format

    @field_validator("budget")
    @classmethod
    def budget_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Budget must be non-negative")
        return v

    @field_validator("deadline")
    @classmethod
    def deadline_must_be_valid_date(cls, v: str) -> str:
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError("Deadline must be a valid ISO date in YYYY-MM-DD format")
        return v

class TaskModel(BaseModel):
    """Pydantic model representing a validated task record."""
    task_id: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)
    assignee: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    updated_at: str  # Kept as string but validated as ISO 8601 datetime format

    @field_validator("updated_at")
    @classmethod
    def updated_at_must_be_valid_datetime(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError("updated_at must be a valid ISO 8601 datetime format")
        return v

class CommunicationModel(BaseModel):
    """Pydantic model representing a validated communication record."""
    message_id: str = Field(..., min_length=1)
    project_id: Optional[str] = None  # project_id can be missing/null in raw data
    channel: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    sentiment: float
    timestamp: str  # Kept as string but validated as ISO 8601 datetime format

    @field_validator("sentiment")
    @classmethod
    def sentiment_must_be_in_range(cls, v: float) -> float:
        if not (-1.0 <= v <= 1.0):
            raise ValueError("Sentiment score must be between -1.0 and 1.0 inclusive")
        return v

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_valid_datetime(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError("timestamp must be a valid ISO 8601 datetime format")
        return v
