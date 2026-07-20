import os
from datetime import datetime
from pydantic import ValidationError
from sentinel.database.connection import get_connection, DEFAULT_DB_PATH
from sentinel.models.validation import ProjectModel, TaskModel, CommunicationModel

class AuditEngine:
    """
    Motor de Auditoría de Datos de Agente Vigía.
    Audita datos SQLite en busca de inconsistencias estructurales, relacionales y semánticas.
    """
    def __init__(self, db_path=DEFAULT_DB_PATH, reference_date_str="2026-06-12T16:00:00"):
        self.db_path = db_path
        # Parse reference date for stagnant task checks (defaulting to current simulation date)
        self.reference_date = datetime.fromisoformat(reference_date_str)
        
    def load_raw_data(self):
        """Loads all raw records from projects, tasks, and communications."""
        raw_data = {"projects": [], "tasks": [], "communications": []}
        
        with get_connection(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM projects")
            raw_data["projects"] = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT * FROM tasks")
            raw_data["tasks"] = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT * FROM communications")
            raw_data["communications"] = [dict(row) for row in cursor.fetchall()]
            
        return raw_data

    def run_audit(self) -> dict:
        """
        Runs structural, relational, and semantic audits on the database.
        Returns an audit report containing logs, score, and execution summary.
        """
        raw_data = self.load_raw_data()
        
        logs = []
        valid_projects = {}
        valid_tasks = []
        valid_communications = []
        
        # Keep track of all raw project IDs in the DB (even corrupted ones) to check relational integrity
        all_raw_project_ids = {row["project_id"] for row in raw_data["projects"] if row["project_id"] is not None}
        
        total_records = len(raw_data["projects"]) + len(raw_data["tasks"]) + len(raw_data["communications"])
        failed_records_count = 0
        
        # 1. STRUCTURAL AUDIT (Pydantic layer)
        # Audit Projects
        for row in raw_data["projects"]:
            try:
                # Pydantic validation
                model = ProjectModel(**row)
                valid_projects[model.project_id] = model
            except ValidationError as e:
                failed_records_count += 1
                for error in e.errors():
                    field = ".".join(map(str, error["loc"]))
                    logs.append({
                        "table": "projects",
                        "row_id": row.get("id"),
                        "entity_id": row.get("project_id"),
                        "level": "ERROR",
                        "type": "STRUCTURAL",
                        "message": f"Validation failed on field '{field}': {error['msg']}"
                    })
            except Exception as ex:
                failed_records_count += 1
                logs.append({
                    "table": "projects",
                    "row_id": row.get("id"),
                    "entity_id": row.get("project_id"),
                    "level": "ERROR",
                    "type": "STRUCTURAL",
                    "message": f"Unexpected error: {str(ex)}"
                })

        # Audit Tasks
        for row in raw_data["tasks"]:
            try:
                model = TaskModel(**row)
                valid_tasks.append(model)
            except ValidationError as e:
                failed_records_count += 1
                for error in e.errors():
                    field = ".".join(map(str, error["loc"]))
                    logs.append({
                        "table": "tasks",
                        "row_id": row.get("id"),
                        "entity_id": row.get("task_id"),
                        "level": "ERROR",
                        "type": "STRUCTURAL",
                        "message": f"Validation failed on field '{field}': {error['msg']}"
                    })
            except Exception as ex:
                failed_records_count += 1
                logs.append({
                    "table": "tasks",
                    "row_id": row.get("id"),
                    "entity_id": row.get("task_id"),
                    "level": "ERROR",
                    "type": "STRUCTURAL",
                    "message": f"Unexpected error: {str(ex)}"
                })

        # Audit Communications
        for row in raw_data["communications"]:
            try:
                model = CommunicationModel(**row)
                valid_communications.append(model)
            except ValidationError as e:
                failed_records_count += 1
                for error in e.errors():
                    field = ".".join(map(str, error["loc"]))
                    logs.append({
                        "table": "communications",
                        "row_id": row.get("id"),
                        "entity_id": row.get("message_id"),
                        "level": "ERROR",
                        "type": "STRUCTURAL",
                        "message": f"Validation failed on field '{field}': {error['msg']}"
                    })
            except Exception as ex:
                failed_records_count += 1
                logs.append({
                    "table": "communications",
                    "row_id": row.get("id"),
                    "entity_id": row.get("message_id"),
                    "level": "ERROR",
                    "type": "STRUCTURAL",
                    "message": f"Unexpected error: {str(ex)}"
                })

        # 2. RELATIONAL AUDIT
        # Orphaned Tasks: Task references project_id that is not in the projects table
        for task in valid_tasks:
            if task.project_id not in all_raw_project_ids:
                logs.append({
                    "table": "tasks",
                    "row_id": None, # Relational checks are cross-record
                    "entity_id": task.task_id,
                    "level": "ERROR",
                    "type": "RELATIONAL",
                    "message": f"Orphaned Task: Task references project_id '{task.project_id}', which does not exist in projects."
                })
                
        # Orphaned Communications: Comm references project_id that is not in the projects table
        for comm in valid_communications:
            if comm.project_id and comm.project_id not in all_raw_project_ids:
                logs.append({
                    "table": "communications",
                    "row_id": None,
                    "entity_id": comm.message_id,
                    "level": "WARNING",
                    "type": "RELATIONAL",
                    "message": f"Orphaned Communication: Message references project_id '{comm.project_id}', which does not exist in projects."
                })
            elif not comm.project_id:
                logs.append({
                    "table": "communications",
                    "row_id": None,
                    "entity_id": comm.message_id,
                    "level": "WARNING",
                    "type": "RELATIONAL",
                    "message": "Missing Project Reference: Communication lacks a referenced project_id."
                })

        # 3. SEMANTIC AUDIT & CONTEXT-DATA GAP AUDIT
        # Rule A: Incomplete Tasks in Completed Project
        for project_id, project in valid_projects.items():
            if project.status.upper() == "COMPLETED":
                # Find all tasks for this project
                project_tasks = [t for t in valid_tasks if t.project_id == project_id]
                incomplete = [t for t in project_tasks if t.status.upper() != "COMPLETED"]
                if incomplete:
                    incomplete_ids = ", ".join(f"'{t.task_id}'" for t in incomplete)
                    logs.append({
                        "table": "projects",
                        "row_id": None,
                        "entity_id": project_id,
                        "level": "WARNING",
                        "type": "SEMANTIC",
                        "message": f"Contradictory Signal: Project '{project.name}' is marked COMPLETED, but contains incomplete tasks: {incomplete_ids}."
                    })

        # Rule B: Negative Communication in Active Project
        for project_id, project in valid_projects.items():
            if project.status.upper() == "ACTIVE":
                project_comms = [c for c in valid_communications if c.project_id == project_id]
                negative_comms = [c for c in project_comms if c.sentiment <= -0.5]
                if negative_comms:
                    logs.append({
                        "table": "projects",
                        "row_id": None,
                        "entity_id": project_id,
                        "level": "WARNING",
                        "type": "SEMANTIC",
                        "message": f"Contradictory Signal: Project '{project.name}' status is ACTIVE, but unstructured communications report high negative sentiment (e.g. message '{negative_comms[0].message_id}' sentiment: {negative_comms[0].sentiment})."
                    })

        # Rule C: Stagnant Blocked Tasks
        for task in valid_tasks:
            if task.status.upper() == "BLOCKED":
                try:
                    updated_dt = datetime.fromisoformat(task.updated_at)
                    delta = self.reference_date - updated_dt
                    if delta.days > 30:
                        logs.append({
                            "table": "tasks",
                            "row_id": None,
                            "entity_id": task.task_id,
                            "level": "WARNING",
                            "type": "SEMANTIC",
                            "message": f"Operational Risk: Task '{task.task_id}' assigned to {task.assignee} is BLOCKED and has not been updated for {delta.days} days."
                        })
                except ValueError:
                    pass # Handled by structural check if updated_at is invalid

        # 4. CALCULATE DATA QUALITY SCORE
        # Deduct score:
        # - Structural error: -15
        # - Relational error: -10 (tasks), -5 (comms warning)
        # - Semantic warning: -5
        quality_score = 100.0
        
        for log in logs:
            if log["type"] == "STRUCTURAL":
                quality_score -= 15.0
            elif log["type"] == "RELATIONAL":
                if log["level"] == "ERROR":
                    quality_score -= 10.0
                else:
                    quality_score -= 5.0
            elif log["type"] == "SEMANTIC":
                quality_score -= 5.0
                
        quality_score = max(0.0, quality_score)
        
        summary = {
            "total_records": total_records,
            "failed_records": failed_records_count,
            "passed_records": total_records - failed_records_count,
            "total_issues": len(logs)
        }
        
        return {
            "quality_score": quality_score,
            "summary": summary,
            "logs": logs
        }
