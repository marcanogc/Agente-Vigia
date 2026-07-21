"""
vigia.insight.generic_engine
--------------------------------
Motor de Insights genérico que trabaja con cualquier esquema.
Genera riesgos, oportunidades y recomendaciones basándose en los resultados
de auditoría y los metadatos del esquema, sin asumir dominio de negocio.
"""

from __future__ import annotations

import json
from typing import Any

from vigia.connectors.base import BaseConnector, DataTypeCategory
from vigia.models.schema_models import (
    AuditCategory,
    AuditFinding,
    AuditLevel,
    AuditReport,
    ColumnProfile,
    InsightReport,
    RiskEntry,
    RiskPriority,
    SchemaMetadata,
    SemanticType,
)


class GenericInsightEngine:
    """
    Motor de Insights genérico para Agente Vigía.
    
    A diferencia del motor legacy (que asume tablas de projects/tasks/communications),
    este motor trabaja sobre cualquier esquema usando:
    - AuditReport: hallazgos de calidad
    - SchemaMetadata: estructura y perfiles estadísticos
    - BaseConnector: acceso a datos validados
    
    Genera:
    - Risk register genérico (basado en hallazgos de auditoría)
    - Prompt dinámico para el LLM adaptado al esquema
    - Reporte ejecutivo (via LLM o generador local)
    """

    def __init__(
        self,
        connector: BaseConnector,
        schema_metadata: SchemaMetadata,
        audit_report: AuditReport,
    ):
        self.connector = connector
        self.schema_metadata = schema_metadata
        self.audit_report = audit_report

    def run_analysis(self) -> InsightReport:
        """
        Ejecuta el análisis completo:
        1. Detecta riesgos operacionales genéricos
        2. Construye prompt dinámico con contexto del esquema
        3. Genera reporte via LLM o mock
        """
        # 1. Detectar riesgos
        risks = self._detect_risks()

        # 2. Generar reporte
        from vigia.insight.llm_dynamic import generate_dynamic_report
        
        prompt_context = self._build_prompt_context(risks)
        report_markdown, provider_used = generate_dynamic_report(prompt_context)

        # 3. Estadísticas de datos limpios
        clean_stats = self._compute_clean_stats()

        return InsightReport(
            audit_report=self.audit_report,
            schema_metadata=self.schema_metadata,
            risks=risks,
            report_markdown=report_markdown,
            llm_provider_used=provider_used,
            clean_data_stats=clean_stats,
        )

    # ─── Detección de riesgos ────────────────────────────────────────────

    def _detect_risks(self) -> list[RiskEntry]:
        """
        Genera un risk register basado en los hallazgos de auditoría.
        Agrupa y prioriza los problemas en riesgos accionables.
        """
        risks: list[RiskEntry] = []

        # Riesgo 1: Tablas con calidad crítica
        for summary in self.audit_report.table_summaries:
            if summary.quality_score < 30:
                risks.append(RiskEntry(
                    risk_type="Critical Data Quality",
                    priority=RiskPriority.CRITICAL,
                    table=summary.table_name,
                    description=(
                        f"Tabla '{summary.table_name}' tiene un score de calidad de "
                        f"{summary.quality_score:.1f}/100 con {summary.critical_count} hallazgos críticos "
                        f"y {summary.error_count} errores. Los datos de esta tabla no son confiables para análisis."
                    ),
                    evidence=[f"{summary.critical_count} CRITICAL, {summary.error_count} ERROR"],
                    recommendation=f"Revisar y corregir los datos fuente de '{summary.table_name}' antes de usar en decisiones.",
                ))
            elif summary.quality_score < 60:
                risks.append(RiskEntry(
                    risk_type="Low Data Quality",
                    priority=RiskPriority.HIGH,
                    table=summary.table_name,
                    description=(
                        f"Tabla '{summary.table_name}' tiene calidad baja ({summary.quality_score:.1f}/100). "
                        f"Se detectaron {summary.findings_count} problemas."
                    ),
                    evidence=[f"Score: {summary.quality_score:.1f}"],
                    recommendation=f"Priorizar limpieza de datos en '{summary.table_name}'.",
                ))

        # Riesgo 2: Integridad referencial rota
        relational_findings = self.audit_report.get_findings_by_category(AuditCategory.RELATIONAL)
        for finding in relational_findings:
            if finding.level in (AuditLevel.CRITICAL, AuditLevel.ERROR):
                risks.append(RiskEntry(
                    risk_type="Broken Referential Integrity",
                    priority=RiskPriority.HIGH,
                    table=finding.table,
                    column=finding.column,
                    description=finding.message,
                    evidence=finding.sample_values[:5] if finding.sample_values else [],
                    recommendation=(
                        f"Verificar la fuente de datos que alimenta '{finding.table}.{finding.column}'. "
                        f"Los registros huérfanos pueden causar errores en reportes y análisis downstream."
                    ),
                ))

        # Riesgo 3: Outliers significativos
        outlier_findings = [
            f for f in self.audit_report.findings 
            if f.rule_name == "outlier_detection" and f.details.get("outlier_percentage", 0) > 5
        ]
        for finding in outlier_findings:
            risks.append(RiskEntry(
                risk_type="Significant Outliers",
                priority=RiskPriority.MEDIUM,
                table=finding.table,
                column=finding.column,
                description=finding.message,
                evidence=[str(v) for v in finding.sample_values[:5]],
                recommendation=(
                    f"Investigar si los outliers en '{finding.table}.{finding.column}' "
                    f"son errores de entrada o eventos legítimos del negocio."
                ),
            ))

        # Riesgo 4: Columnas con alta tasa de NULL
        null_findings = [
            f for f in self.audit_report.findings
            if f.rule_name == "high_null_rate" and f.details.get("null_percentage", 0) > 80
        ]
        for finding in null_findings:
            risks.append(RiskEntry(
                risk_type="Data Completeness Issue",
                priority=RiskPriority.MEDIUM,
                table=finding.table,
                column=finding.column,
                description=finding.message,
                recommendation=(
                    f"La columna '{finding.column}' está casi vacía. "
                    f"Evaluar si es un campo opcional o si hay un problema de ingesta."
                ),
            ))

        # Riesgo 5: PKs con problemas (nulls o duplicados)
        pk_findings = [
            f for f in self.audit_report.findings
            if f.rule_name in ("null_primary_key", "duplicate_primary_key")
        ]
        for finding in pk_findings:
            risks.append(RiskEntry(
                risk_type="Primary Key Integrity",
                priority=RiskPriority.CRITICAL,
                table=finding.table,
                column=finding.column,
                description=finding.message,
                evidence=[str(finding.affected_rows)],
                recommendation=(
                    f"Las claves primarias deben ser únicas y no-nulas. "
                    f"Corregir inmediatamente en '{finding.table}' para garantizar integridad."
                ),
            ))

        # Riesgo 6: Valores negativos en campos que no lo permiten
        neg_findings = [
            f for f in self.audit_report.findings if f.rule_name == "negative_value"
        ]
        for finding in neg_findings:
            risks.append(RiskEntry(
                risk_type="Invalid Negative Values",
                priority=RiskPriority.HIGH,
                table=finding.table,
                column=finding.column,
                description=finding.message,
                recommendation=(
                    f"Verificar la fuente de datos. Valores negativos en "
                    f"'{finding.column}' pueden distorsionar cálculos y reportes."
                ),
            ))

        # Ordenar por prioridad
        priority_order = {
            RiskPriority.CRITICAL: 0,
            RiskPriority.HIGH: 1,
            RiskPriority.MEDIUM: 2,
            RiskPriority.LOW: 3,
        }
        risks.sort(key=lambda r: priority_order.get(r.priority, 99))

        return risks

    # ─── Construcción del contexto para el prompt ────────────────────────

    def _build_prompt_context(self, risks: list[RiskEntry]) -> dict[str, Any]:
        """
        Construye el contexto completo que el módulo LLM usará para generar el prompt.
        Incluye toda la información necesaria para un reporte ejecutivo adaptado al esquema.
        """
        # Resumen del esquema
        schema_summary = self._summarize_schema()
        
        # Resumen de calidad
        quality_summary = self._summarize_quality()

        # Hallazgos más importantes (top 20)
        top_findings = self._get_top_findings(20)

        # Riesgos serializados
        risks_data = [
            {
                "risk_type": r.risk_type,
                "priority": r.priority.value,
                "table": r.table,
                "column": r.column,
                "description": r.description,
                "recommendation": r.recommendation,
            }
            for r in risks
        ]

        # Limitaciones
        limitations = list(self.schema_metadata.limitations)
        if not self.schema_metadata.declared_relationships and not self.schema_metadata.inferred_relationships:
            limitations.append("No se detectaron relaciones entre tablas (declaradas ni inferidas).")

        return {
            "schema_summary": schema_summary,
            "quality_summary": quality_summary,
            "global_score": self.audit_report.global_quality_score,
            "total_tables": self.audit_report.total_tables_audited,
            "total_rows": self.audit_report.total_rows_audited,
            "total_findings": self.audit_report.total_findings,
            "critical_findings": self.audit_report.critical_findings,
            "error_findings": self.audit_report.error_findings,
            "warning_findings": self.audit_report.warning_findings,
            "top_findings": top_findings,
            "risks": risks_data,
            "limitations": limitations,
            "table_scores": [
                {"table": s.table_name, "score": s.quality_score, "rows": s.row_count, "findings": s.findings_count}
                for s in self.audit_report.table_summaries
            ],
        }

    def _summarize_schema(self) -> str:
        """Genera un resumen legible del esquema detectado."""
        lines = []
        lines.append(f"Base de datos con {self.schema_metadata.total_tables} tablas, "
                     f"{self.schema_metadata.total_columns} columnas, "
                     f"{self.schema_metadata.total_rows} filas totales.")
        lines.append("")
        lines.append("Tablas:")
        for table in self.schema_metadata.tables:
            pk_str = f" [PK: {', '.join(table.primary_keys)}]" if table.primary_keys else ""
            lines.append(f"  - {table.name} ({len(table.columns)} cols, {table.row_count} filas){pk_str}")
            for col in table.columns[:10]:  # Limitar a 10 columnas por tabla
                profile = self.schema_metadata.get_column_profile(table.name, col.name)
                sem = ""
                if profile and profile.semantic_label and profile.semantic_label.confidence >= 0.6:
                    sem = f" → {profile.semantic_label.semantic_type.value} ({profile.semantic_label.confidence:.0%})"
                lines.append(f"    • {col.name} ({col.raw_type}){sem}")
            if len(table.columns) > 10:
                lines.append(f"    ... y {len(table.columns) - 10} columnas más")

        # Relaciones
        if self.schema_metadata.declared_relationships:
            lines.append("")
            lines.append("Relaciones declaradas:")
            for fk in self.schema_metadata.declared_relationships:
                lines.append(f"  - {fk.column} → {fk.referenced_table}.{fk.referenced_column}")

        if self.schema_metadata.inferred_relationships:
            lines.append("")
            lines.append("Relaciones inferidas:")
            for rel in self.schema_metadata.inferred_relationships:
                lines.append(
                    f"  - {rel.source_table}.{rel.source_column} → "
                    f"{rel.target_table}.{rel.target_column} "
                    f"(confianza: {rel.confidence:.0%}, método: {rel.method})"
                )

        return "\n".join(lines)

    def _summarize_quality(self) -> str:
        """Genera un resumen de calidad por tabla."""
        lines = []
        for summary in sorted(self.audit_report.table_summaries, key=lambda s: s.quality_score):
            status = "OK" if summary.quality_score >= 80 else "PRECAUCION" if summary.quality_score >= 50 else "CRITICO"
            lines.append(
                f"  - {summary.table_name}: {summary.quality_score:.1f}/100 [{status}] "
                f"({summary.critical_count}C/{summary.error_count}E/{summary.warning_count}W)"
            )
        return "\n".join(lines)

    def _get_top_findings(self, limit: int) -> list[dict[str, Any]]:
        """Obtiene los hallazgos más relevantes serializados."""
        # Priorizar por nivel
        sorted_findings = sorted(
            self.audit_report.findings,
            key=lambda f: (
                {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}.get(f.level.value, 4),
                -f.affected_rows,
            ),
        )
        
        return [
            {
                "table": f.table,
                "column": f.column,
                "level": f.level.value,
                "category": f.category.value,
                "rule": f.rule_name,
                "message": f.message,
                "affected_rows": f.affected_rows,
            }
            for f in sorted_findings[:limit]
        ]

    def _compute_clean_stats(self) -> dict[str, int]:
        """Calcula estadísticas de datos limpios (tablas con score > 60)."""
        clean_tables = [s for s in self.audit_report.table_summaries if s.quality_score >= 60]
        return {
            "clean_tables_count": len(clean_tables),
            "total_tables": self.audit_report.total_tables_audited,
            "clean_rows": sum(s.row_count for s in clean_tables),
            "total_rows": self.audit_report.total_rows_audited,
        }
