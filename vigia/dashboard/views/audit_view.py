"""
vigia.dashboard.pages.audit_view
-------------------------------------
Visualización de resultados de auditoría: hallazgos, scores,
desglose por tabla y categoría.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from vigia.models.schema_models import AuditReport, AuditLevel, AuditCategory


def render_audit_page(audit_report: AuditReport):
    """Renderiza los resultados de la auditoría de calidad de datos."""
    st.header("🔍 Auditoría de Calidad de Datos")

    # KPIs principales
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Score Global", f"{audit_report.global_quality_score:.1f}/100")
    k2.metric("Tablas Auditadas", audit_report.total_tables_audited)
    k3.metric("Filas Totales", f"{audit_report.total_rows_audited:,}")
    k4.metric("Hallazgos", audit_report.total_findings)
    k5.metric("Críticos + Errores", audit_report.critical_findings + audit_report.error_findings, delta_color="inverse")

    st.markdown("---")

    # Score por tabla
    st.subheader("📊 Calidad por Tabla")

    if audit_report.table_summaries:
        table_data = []
        for s in sorted(audit_report.table_summaries, key=lambda x: x.quality_score):
            if s.quality_score >= 80:
                status = "✅ Bueno"
                color = "green"
            elif s.quality_score >= 50:
                status = "⚠️ Precaución"
                color = "orange"
            else:
                status = "🚨 Crítico"
                color = "red"

            table_data.append({
                "Tabla": s.table_name,
                "Score": s.quality_score,
                "Filas": s.row_count,
                "Columnas": s.column_count,
                "Critical": s.critical_count,
                "Error": s.error_count,
                "Warning": s.warning_count,
                "Estado": status,
            })

        df_tables = pd.DataFrame(table_data)

        # Barra de progreso visual por tabla
        for _, row in df_tables.iterrows():
            col1, col2, col3 = st.columns([2, 4, 1])
            with col1:
                st.markdown(f"**`{row['Tabla']}`**")
            with col2:
                st.progress(row["Score"] / 100.0)
            with col3:
                st.markdown(f"**{row['Score']:.0f}**/100")

        st.markdown("")
        st.dataframe(df_tables, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Explicación del score
    st.subheader("📐 Cómo se calcula el Score")
    with st.expander("Ver fórmula de penalización", expanded=False):
        st.markdown("""
| Nivel + Categoría | Penalización |
|---|---|
| CRITICAL + Structural | -20 pts |
| CRITICAL + Relational/Consistency | -15 pts |
| CRITICAL + Completeness/Statistical | -10 pts |
| ERROR + Structural | -10 pts |
| ERROR + Relational/Consistency | -8 pts |
| ERROR + Completeness/Statistical | -5 pts |
| WARNING (cualquier categoría) | -2 a -3 pts |
| INFO | 0 pts |

El score inicia en 100 para cada tabla. El score global es el promedio ponderado por número de filas.
        """)

    if audit_report.score_explanation:
        st.markdown("**Desglose del Score Global:**")
        for exp in audit_report.score_explanation[:10]:
            st.caption(f"• {exp}")

    st.markdown("---")

    # Detalle de hallazgos
    st.subheader("📋 Detalle de Hallazgos")

    if audit_report.findings:
        # Filtros
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            level_filter = st.multiselect(
                "Nivel",
                options=["CRITICAL", "ERROR", "WARNING", "INFO"],
                default=["CRITICAL", "ERROR", "WARNING"],
            )
        with fc2:
            category_filter = st.multiselect(
                "Categoría",
                options=["STRUCTURAL", "RELATIONAL", "STATISTICAL", "COMPLETENESS", "CONSISTENCY"],
                default=["STRUCTURAL", "RELATIONAL", "STATISTICAL", "COMPLETENESS", "CONSISTENCY"],
            )
        with fc3:
            table_names = list({f.table for f in audit_report.findings})
            table_filter = st.multiselect(
                "Tabla",
                options=sorted(table_names),
                default=sorted(table_names),
            )

        # Construir DataFrame de hallazgos
        findings_data = []
        for f in audit_report.findings:
            if f.level.value not in level_filter:
                continue
            if f.category.value not in category_filter:
                continue
            if f.table not in table_filter:
                continue

            findings_data.append({
                "Nivel": f.level.value,
                "Categoría": f.category.value,
                "Tabla": f.table,
                "Columna": f.column or "—",
                "Regla": f.rule_name,
                "Mensaje": f.message,
                "Filas Afectadas": f.affected_rows,
            })

        if findings_data:
            df_findings = pd.DataFrame(findings_data)

            # Colorear por nivel
            def _style_level(val):
                styles = {
                    "CRITICAL": "background-color: #ff4444; color: white; font-weight: bold;",
                    "ERROR": "background-color: #ffcccc; color: #cc0000; font-weight: bold;",
                    "WARNING": "background-color: #fff2cc; color: #b38600; font-weight: bold;",
                    "INFO": "background-color: #e8f4fd; color: #1976d2;",
                }
                return styles.get(val, "")

            styled = df_findings.style.map(_style_level, subset=["Nivel"])
            st.dataframe(styled, use_container_width=True, hide_index=True)

            st.caption(f"Mostrando {len(findings_data)} de {audit_report.total_findings} hallazgos.")
        else:
            st.info("No hay hallazgos que coincidan con los filtros seleccionados.")
    else:
        st.success("🎉 No se detectaron hallazgos de calidad. Los datos están en excelente estado.")

    # Limitaciones
    if audit_report.limitations:
        st.markdown("---")
        st.subheader("⚠️ Limitaciones")
        for lim in audit_report.limitations:
            st.caption(f"• {lim}")
