import os
from datetime import datetime
from typing import List, Dict
from vigia.database.connection import DEFAULT_DB_PATH
from vigia.audit.engine import AuditEngine
from vigia.insight.llm import generate_insights_report

class InsightEngine:
    """
    Motor de Insights y Detección de Riesgos Operacionales de Agente Vigía.
    Filtra datos crudos para analizar solo registros validados y detecta riesgos críticos de negocio.
    """
    def __init__(self, db_path=DEFAULT_DB_PATH, reference_date_str="2026-06-12T16:00:00"):
        self.db_path = db_path
        self.reference_date = datetime.fromisoformat(reference_date_str)
        self.audit_engine = AuditEngine(db_path, reference_date_str)
        
    def run_analysis(self) -> dict:
        """
        Executes data audit, filters out corrupted data, detects operational risks,
        and generates an executive markdown insight report using the LLM/mock client.
        """
        # 1. Run audit engine
        audit_report = self.audit_engine.run_audit()
        raw_data = self.audit_engine.load_raw_data()
        
        # 2. Extract invalid entity IDs from audit logs
        invalid_project_ids = set()
        invalid_task_ids = set()
        invalid_message_ids = set()
        
        for log in audit_report["logs"]:
            if log["level"] == "ERROR":
                if log["table"] == "projects" and log["entity_id"]:
                    invalid_project_ids.add(log["entity_id"])
                elif log["table"] == "tasks":
                    # Note: entity_id could be None if task_id is NULL
                    if log["entity_id"]:
                        invalid_task_ids.add(log["entity_id"])
                elif log["table"] == "communications" and log["entity_id"]:
                    invalid_message_ids.add(log["entity_id"])
                    
        # 3. Filter raw data to obtain clean/validated dataset
        clean_projects = [
            p for p in raw_data["projects"]
            if p.get("project_id") not in invalid_project_ids and p.get("project_id") is not None
        ]
        
        # Tasks are clean if task_id is valid, task is not flagged, and references a clean project
        clean_tasks = [
            t for t in raw_data["tasks"]
            if t.get("task_id") not in invalid_task_ids 
            and t.get("task_id") is not None 
            and t.get("project_id") not in invalid_project_ids
        ]
        
        clean_comms = [
            c for c in raw_data["communications"]
            if c.get("message_id") not in invalid_message_ids and c.get("message_id") is not None
        ]
        
        # 4. Programmatic Operational Risk Detection (Only on Clean/Validated Data!)
        risks = []
        
        # Risk A: Stagnant Blocked Tasks
        for task in clean_tasks:
            if task.get("status", "").upper() == "BLOCKED":
                try:
                    updated_dt = datetime.fromisoformat(task.get("updated_at"))
                    delta = self.reference_date - updated_dt
                    if delta.days > 30:
                        risks.append({
                            "risk_type": "Stagnant Blocked Task",
                            "priority": "HIGH",
                            "project_id": task.get("project_id"),
                            "description": f"Task '{task.get('task_id')}' assigned to {task.get('assignee')} is BLOCKED and stagnant (no updates in {delta.days} days).",
                            "evidence_reference": task.get("task_id")
                        })
                except ValueError:
                    pass

        # Risk B: Negative Communication Sentiment in Active Projects
        active_project_ids = {p["project_id"] for p in clean_projects if p.get("status", "").upper() == "ACTIVE"}
        for comm in clean_comms:
            p_id = comm.get("project_id")
            if p_id in active_project_ids and comm.get("sentiment", 0.0) <= -0.5:
                risks.append({
                    "risk_type": "Negative Communication Sentiment",
                    "priority": "HIGH",
                    "project_id": p_id,
                    "description": f"Communication '{comm.get('message_id')}' in active project reports highly negative sentiment ({comm.get('sentiment')}): '{comm.get('summary')}'",
                    "evidence_reference": comm.get("message_id")
                })
                
        # Risk C: Close Deadline Risk
        for project in clean_projects:
            if project.get("status", "").upper() == "ACTIVE" and project.get("deadline"):
                try:
                    deadline_dt = datetime.strptime(project.get("deadline"), "%Y-%m-%d")
                    # Make deadline dateless time compatible with reference date
                    deadline_dt = datetime(deadline_dt.year, deadline_dt.month, deadline_dt.day, 16, 0, 0)
                    delta = deadline_dt - self.reference_date
                    
                    # If deadline is within 45 days
                    if 0 <= delta.days <= 45:
                        # Check if project has incomplete tasks
                        project_tasks = [t for t in clean_tasks if t.get("project_id") == project.get("project_id")]
                        incomplete_tasks = [t for t in project_tasks if t.get("status", "").upper() != "COMPLETED"]
                        
                        if incomplete_tasks:
                            has_blocked = any(t.get("status", "").upper() == "BLOCKED" for t in incomplete_tasks)
                            priority = "HIGH" if has_blocked else "MEDIUM"
                            risks.append({
                                "risk_type": "Close Deadline Risk",
                                "priority": priority,
                                "project_id": project.get("project_id"),
                                "description": f"Project '{project.get('name')}' deadline ({project.get('deadline')}) is approaching in {delta.days} days with {len(incomplete_tasks)} incomplete tasks.",
                                "evidence_reference": project.get("project_id")
                            })
                except ValueError:
                    pass

        # 5. Generate executive report using LLM module
        insight_report_markdown = generate_insights_report(risks, audit_report)
        
        return {
            "audit_report": audit_report,
            "risk_register": risks,
            "report_markdown": insight_report_markdown,
            "clean_stats": {
                "projects_count": len(clean_projects),
                "tasks_count": len(clean_tasks),
                "communications_count": len(clean_comms)
            }
        }
