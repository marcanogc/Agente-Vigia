"""
vigia.audit.generic_engine
------------------------------
Motor de auditoría genérico que evalúa calidad de datos sobre cualquier
esquema usando reglas pluggables y metadatos del SchemaInspector.
"""

from __future__ import annotations

from vigia.connectors.base import BaseConnector
from vigia.audit.rules import AuditRule, DEFAULT_RULES
from vigia.models.schema_models import (
    AuditCategory,
    AuditFinding,
    AuditLevel,
    AuditReport,
    SchemaMetadata,
    TableAuditSummary,
)


# Pesos de penalización por nivel/categoría para el Data Quality Score
_SCORE_PENALTIES = {
    (AuditLevel.CRITICAL, AuditCategory.STRUCTURAL): 20.0,
    (AuditLevel.CRITICAL, AuditCategory.RELATIONAL): 15.0,
    (AuditLevel.CRITICAL, AuditCategory.CONSISTENCY): 15.0,
    (AuditLevel.CRITICAL, AuditCategory.COMPLETENESS): 10.0,
    (AuditLevel.CRITICAL, AuditCategory.STATISTICAL): 10.0,
    (AuditLevel.ERROR, AuditCategory.STRUCTURAL): 10.0,
    (AuditLevel.ERROR, AuditCategory.RELATIONAL): 8.0,
    (AuditLevel.ERROR, AuditCategory.CONSISTENCY): 8.0,
    (AuditLevel.ERROR, AuditCategory.COMPLETENESS): 5.0,
    (AuditLevel.ERROR, AuditCategory.STATISTICAL): 5.0,
    (AuditLevel.WARNING, AuditCategory.STRUCTURAL): 3.0,
    (AuditLevel.WARNING, AuditCategory.RELATIONAL): 3.0,
    (AuditLevel.WARNING, AuditCategory.CONSISTENCY): 3.0,
    (AuditLevel.WARNING, AuditCategory.COMPLETENESS): 2.0,
    (AuditLevel.WARNING, AuditCategory.STATISTICAL): 2.0,
    (AuditLevel.INFO, AuditCategory.STRUCTURAL): 0.0,
    (AuditLevel.INFO, AuditCategory.RELATIONAL): 0.0,
    (AuditLevel.INFO, AuditCategory.CONSISTENCY): 0.0,
    (AuditLevel.INFO, AuditCategory.COMPLETENESS): 0.0,
    (AuditLevel.INFO, AuditCategory.STATISTICAL): 0.0,
}


class GenericAuditEngine:
    """
    Motor de auditoría genérico.
    
    Evalúa un conjunto de reglas pluggables sobre cada tabla del esquema
    y genera un AuditReport con score de calidad global y por tabla.
    
    Las reglas se pueden personalizar al instanciar el motor.
    """

    def __init__(
        self,
        connector: BaseConnector,
        schema_metadata: SchemaMetadata,
        rules: list[AuditRule] | None = None,
    ):
        """
        Args:
            connector: Conector activo a la fuente de datos.
            schema_metadata: Metadatos completos del esquema (generados por SchemaInspector).
            rules: Lista de reglas a evaluar. Si es None, usa DEFAULT_RULES.
        """
        self.connector = connector
        self.schema_metadata = schema_metadata
        self.rules = rules if rules is not None else list(DEFAULT_RULES)

    def run_audit(self) -> AuditReport:
        """
        Ejecuta todas las reglas sobre todas las tablas y genera el reporte.
        
        Returns:
            AuditReport con hallazgos, scores y explicaciones.
        """
        all_findings: list[AuditFinding] = []
        table_summaries: list[TableAuditSummary] = []

        for table_info in self.schema_metadata.tables:
            table_findings: list[AuditFinding] = []

            for rule in self.rules:
                try:
                    findings = rule.evaluate(
                        self.connector, table_info, self.schema_metadata
                    )
                    table_findings.extend(findings)
                except Exception as e:
                    # Las reglas no deben romper la auditoría completa
                    table_findings.append(AuditFinding(
                        table=table_info.name,
                        column=None,
                        level=AuditLevel.INFO,
                        category=rule.category,
                        rule_name=rule.name,
                        message=f"Error al evaluar regla '{rule.name}': {str(e)}",
                    ))

            # Calcular score por tabla
            table_score, score_explanation = self._calculate_table_score(table_findings)
            
            summary = TableAuditSummary(
                table_name=table_info.name,
                row_count=table_info.row_count,
                column_count=len(table_info.columns),
                findings_count=len(table_findings),
                critical_count=sum(1 for f in table_findings if f.level == AuditLevel.CRITICAL),
                error_count=sum(1 for f in table_findings if f.level == AuditLevel.ERROR),
                warning_count=sum(1 for f in table_findings if f.level == AuditLevel.WARNING),
                info_count=sum(1 for f in table_findings if f.level == AuditLevel.INFO),
                quality_score=table_score,
                score_explanation=score_explanation,
            )
            table_summaries.append(summary)
            all_findings.extend(table_findings)

        # Calcular score global (promedio ponderado por filas)
        global_score, global_explanation = self._calculate_global_score(table_summaries)

        # Conteos globales
        critical_count = sum(1 for f in all_findings if f.level == AuditLevel.CRITICAL)
        error_count = sum(1 for f in all_findings if f.level == AuditLevel.ERROR)
        warning_count = sum(1 for f in all_findings if f.level == AuditLevel.WARNING)
        info_count = sum(1 for f in all_findings if f.level == AuditLevel.INFO)

        return AuditReport(
            findings=all_findings,
            table_summaries=table_summaries,
            global_quality_score=global_score,
            score_explanation=global_explanation,
            total_tables_audited=len(table_summaries),
            total_rows_audited=self.schema_metadata.total_rows,
            total_findings=len(all_findings),
            critical_findings=critical_count,
            error_findings=error_count,
            warning_findings=warning_count,
            info_findings=info_count,
            limitations=list(self.schema_metadata.limitations),
        )

    def _calculate_table_score(
        self, findings: list[AuditFinding]
    ) -> tuple[float, list[str]]:
        """
        Calcula el score de calidad para una tabla.
        Inicia en 100 y descuenta por cada hallazgo según su severidad y categoría.
        """
        score = 100.0
        explanations: list[str] = []

        for finding in findings:
            penalty = _SCORE_PENALTIES.get((finding.level, finding.category), 0.0)
            if penalty > 0:
                score -= penalty
                explanations.append(
                    f"-{penalty:.0f} pts: [{finding.level.value}] {finding.rule_name} en '{finding.column or 'tabla'}'"
                )

        score = max(score, 0.0)
        
        if not explanations:
            explanations.append("Sin hallazgos significativos. Score perfecto.")

        return round(score, 1), explanations

    def _calculate_global_score(
        self, summaries: list[TableAuditSummary]
    ) -> tuple[float, list[str]]:
        """
        Calcula el score global como promedio ponderado de los scores por tabla.
        Las tablas con más filas tienen más peso.
        """
        if not summaries:
            return 100.0, ["No hay tablas para auditar."]

        total_rows = sum(s.row_count for s in summaries)
        explanations: list[str] = []

        if total_rows == 0:
            # Si todas las tablas están vacías, promedio simple
            avg_score = sum(s.quality_score for s in summaries) / len(summaries)
            explanations.append(f"Promedio simple de {len(summaries)} tablas (todas vacías).")
            return round(avg_score, 1), explanations

        # Promedio ponderado por número de filas
        weighted_sum = 0.0
        for s in summaries:
            weight = s.row_count / total_rows if total_rows > 0 else 1.0 / len(summaries)
            weighted_sum += s.quality_score * weight
            if s.quality_score < 100:
                explanations.append(
                    f"Tabla '{s.table_name}': {s.quality_score:.1f}/100 "
                    f"({s.row_count} filas, {s.findings_count} hallazgos)"
                )

        if not explanations:
            explanations.append("Todas las tablas tienen score perfecto.")

        return round(weighted_sum, 1), explanations
