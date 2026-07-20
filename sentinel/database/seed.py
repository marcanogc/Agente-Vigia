import os
import sys
from sentinel.database.connection import get_connection, init_db, DEFAULT_DB_PATH

# Define seed datasets
PROJECTS = [
    # project_id, name, status, budget, deadline
    ("P001", "Phoenix Project", "ACTIVE", 150000.0, "2026-09-30"),
    ("P002", "Project Apollo", "ACTIVE", 85000.0, "2026-07-15"),
    ("P003", "Titan Initiative", "COMPLETED", 200000.0, "2026-05-01"),
    # Corrupted: Negative budget
    ("P004", "Project Icarus", "ACTIVE", -50000.0, "2026-08-31"),
    # Corrupted: Invalid date format/values
    ("P005", "Nemesis Protocol", "ACTIVE", 120000.0, "2026-13-45"),
]

TASKS = [
    # task_id, project_id, assignee, status, updated_at
    ("T001", "P001", "Alice", "IN_PROGRESS", "2026-06-10T12:00:00"),
    ("T002", "P001", "Bob", "COMPLETED", "2026-06-11T14:30:00"),
    ("T003", "P002", "Charlie", "IN_PROGRESS", "2026-06-09T09:00:00"),
    # Corrupted: Orphaned task (P009 does not exist)
    ("T004", "P009", "Dave", "IN_PROGRESS", "2026-06-12T10:00:00"),
    # Corrupted: Missing task_id (null identifier)
    (None, "P001", "Eve", "IN_PROGRESS", "2026-06-12T11:00:00"),
    # Operational Risk: Stagnant task (status is BLOCKED and updated long ago)
    ("T005", "P002", "Frank", "BLOCKED", "2026-01-10T08:00:00"),
]

COMMUNICATIONS = [
    # message_id, project_id, channel, summary, sentiment, timestamp
    ("MSG001", "P001", "slack", "Frontend UI design is looking great, on track.", 0.85, "2026-06-12T10:15:00"),
    ("MSG002", "P002", "teams", "Completed backend API endpoints integration.", 0.90, "2026-06-11T16:45:00"),
    # Risk/Contradictory: Project status is ACTIVE (tasks are in progress), but slack reveals critical failure
    ("MSG003", "P002", "slack", "Backend API is crashing constantly. We might miss the deadline.", -0.80, "2026-06-12T09:00:00"),
    # Valid notification on Icarus
    ("MSG004", "P004", "slack", "Budget concerns raised due to negative figures.", -0.20, "2026-06-12T11:30:00"),
    # Corrupted: Missing project_id
    ("MSG005", None, "email", "General team check-in scheduled for next Tuesday.", 0.10, "2026-06-12T12:00:00"),
    # Corrupted: Orphaned project reference (P009 does not exist)
    ("MSG006", "P009", "slack", "Discussing database migration details with Dave.", 0.50, "2026-06-12T12:30:00"),
]

def seed_data(db_path=DEFAULT_DB_PATH):
    """
    Clears tables and populates the database with valid and corrupted seed records.
    """
    # Initialize the database schema first to ensure tables exist
    init_db(db_path)
    
    with get_connection(db_path) as conn:
        # Clear existing records
        conn.execute("DELETE FROM projects")
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM communications")
        
        # Insert Projects
        conn.executemany(
            "INSERT INTO projects (project_id, name, status, budget, deadline) VALUES (?, ?, ?, ?, ?)",
            PROJECTS
        )
        
        # Insert Tasks
        conn.executemany(
            "INSERT INTO tasks (task_id, project_id, assignee, status, updated_at) VALUES (?, ?, ?, ?, ?)",
            TASKS
        )
        
        # Insert Communications
        conn.executemany(
            "INSERT INTO communications (message_id, project_id, channel, summary, sentiment, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            COMMUNICATIONS
        )
        
    print(f"Database successfully seeded at: {db_path}")
    return db_path

if __name__ == "__main__":
    db_file = DEFAULT_DB_PATH
    if len(sys.argv) > 1:
        db_file = sys.argv[1]
    seed_data(db_file)
