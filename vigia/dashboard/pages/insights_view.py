"""
vigia.dashboard.pages.insights_view
----------------------------------------
Visualización de insights, riesgos, recomendaciones y reporte ejecutivo.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from vigia.models.schema_models import InsightReport, RiskPriority


def render_insights_page(insight_report: InsightReport):
    """Renderiza insights, riesgos y recomendaciones."""
    st.header("💡 Insights y Recomendaciones")

    # Badge del proveedor LLM utilizado
    provider = insight_report.llm_provider_used
    provider_badges = {
        "bedrock": ("🟠 Amazon Bedrock", "llm-badge-bedrock"),
        "nvidia": ("🟢 NVIDIA NIM", "llm-badge-nvidia"),
        "openai": ("🔵 OpenAI", "llm-badge-openai"),
        "mock": ("⚫ Motor Local", "llm-badge-mock"),
    }
    label, badge_class = provider_badges.get(provider, ("⚪ Desconocido", ""))
    st.caption(f"Generado por: **{label}**")

    # Estadísticas de datos limpios
    clean_stats = insight_report.clean_data_stats
    if clean_stats:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tablas Confiables", f"{clean_stats.get('clean_tables_count', 0)}/{clean_stats.get('total_tables', 0)}")
        c2.metric("Filas Confiables", f"{clean_stats.get('clean_rows', 0):,}")
        c3.metric("Riesgos Detectados", len(insight_report.risks))
        c4.metric("Score Global", f"{insight_report.audit_report.global_quality_score:.1f}")

    st.markdown("---")

    # Tabs: Riesgos | Reporte IA | Exportar
    tab_risks, tab_report, tab_export = st.tabs([
        "🚨 Riesgos", "📄 Reporte Ejecutivo", "📥 Exportar"
    ])

    with tab_risks:
        _render_risks(insight_report)

    with tab_report:
        _render_report(insight_report)

    with tab_export:
        _render_export(insight_report)


def _render_risks(insight_report: InsightReport):
    """Renderiza la tabla de riesgos."""
    risks = insight_report.risks

    if not risks:
        st.success("🎉 No se detectaron riesgos significativos en los datos validados.")
        return

    st.subheader(f"Se detectaron {len(risks)} riesgos")

    # Resumen por prioridad
    priority_counts = {}
    for r in risks:
        p = r.priority.value
        priority_counts[p] = priority_counts.get(p, 0) + 1

    cols = st.columns(4)
    for i, (priority, label, color) in enumerate([
        ("CRITICAL", "🔴 Críticos", "#ff4444"),
        ("HIGH", "🟠 Altos", "#ff8800"),
        ("MEDIUM", "🟡 Medios", "#ffcc00"),
        ("LOW", "🟢 Bajos", "#44bb44"),
    ]):
        with cols[i]:
            count = priority_counts.get(priority, 0)
            st.metric(label, count)

    st.markdown("")

    # Detalle de riesgos
    for i, risk in enumerate(risks, 1):
        priority_icon = {
            "CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"
        }.get(risk.priority.value, "⚪")

        with st.expander(
            f"{priority_icon} [{risk.priority.value}] {risk.risk_type} — `{risk.table}`"
            f"{('.' + risk.column) if risk.column else ''}",
            expanded=(risk.priority in (RiskPriority.CRITICAL, RiskPriority.HIGH)),
        ):
            st.markdown(f"**Descripción:** {risk.description}")
            if risk.evidence:
                st.markdown(f"**Evidencia:** `{', '.join(str(e) for e in risk.evidence[:5])}`")
            if risk.recommendation:
                st.info(f"💡 **Recomendación:** {risk.recommendation}")


def _render_report(insight_report: InsightReport):
    """Renderiza el reporte Markdown generado por el LLM."""
    st.subheader("Reporte Ejecutivo de Integridad")

    report = insight_report.report_markdown

    if report:
        # Contenedor scrolleable
        st.markdown(
            f'<div style="border:1px solid #dde; padding:24px; border-radius:10px; '
            f'background:#fafbfc; max-height:600px; overflow-y:auto; '
            f'font-size:0.9rem; line-height:1.6;">{_md_to_styled(report)}</div>',
            unsafe_allow_html=True,
        )

        # También mostrar como Markdown nativo
        with st.expander("Ver Markdown sin formato"):
            st.code(report, language="markdown")
    else:
        st.warning("No se pudo generar el reporte. Verifica la configuración del LLM.")


def _render_export(insight_report: InsightReport):
    """Opciones de exportación del reporte."""
    st.subheader("📥 Exportar Reporte")

    st.markdown("Descarga el reporte en diferentes formatos:")

    col1, col2 = st.columns(2)

    with col1:
        # Markdown
        if insight_report.report_markdown:
            st.download_button(
                label="📄 Descargar Markdown (.md)",
                data=insight_report.report_markdown,
                file_name="agente_vigia_report.md",
                mime="text/markdown",
                use_container_width=True,
            )

    with col2:
        # CSV de hallazgos
        if insight_report.audit_report.findings:
            findings_data = []
            for f in insight_report.audit_report.findings:
                findings_data.append({
                    "nivel": f.level.value,
                    "categoria": f.category.value,
                    "tabla": f.table,
                    "columna": f.column or "",
                    "regla": f.rule_name,
                    "mensaje": f.message,
                    "filas_afectadas": f.affected_rows,
                })
            df = pd.DataFrame(findings_data)
            csv_data = df.to_csv(index=False)
            st.download_button(
                label="📊 Descargar Hallazgos (.csv)",
                data=csv_data,
                file_name="agente_vigia_findings.csv",
                mime="text/csv",
                use_container_width=True,
            )

    # Resumen JSON
    st.markdown("")
    if st.button("📋 Copiar resumen al portapapeles", use_container_width=True):
        summary = {
            "score_global": insight_report.audit_report.global_quality_score,
            "tablas_auditadas": insight_report.audit_report.total_tables_audited,
            "filas_totales": insight_report.audit_report.total_rows_audited,
            "hallazgos_totales": insight_report.audit_report.total_findings,
            "riesgos": len(insight_report.risks),
            "proveedor_ia": insight_report.llm_provider_used,
        }
        import json
        st.code(json.dumps(summary, indent=2, ensure_ascii=False), language="json")


def _md_to_styled(md_text: str) -> str:
    """Convierte Markdown básico a HTML para renderizado inline."""
    # Streamlit renderiza markdown nativamente, pero para el container usamos st.markdown
    # Retornamos el texto para uso en el div styled
    import html
    escaped = html.escape(md_text)
    # Convertir headers básicos
    lines = escaped.split("\n")
    html_lines = []
    for line in lines:
        if line.startswith("# "):
            html_lines.append(f"<h2>{line[2:]}</h2>")
        elif line.startswith("## "):
            html_lines.append(f"<h3>{line[3:]}</h3>")
        elif line.startswith("### "):
            html_lines.append(f"<h4>{line[4:]}</h4>")
        elif line.startswith("- "):
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.startswith("&gt;"):
            html_lines.append(f"<blockquote>{line[4:]}</blockquote>")
        elif line.strip() == "":
            html_lines.append("<br/>")
        else:
            html_lines.append(f"<p>{line}</p>")
    return "\n".join(html_lines)
