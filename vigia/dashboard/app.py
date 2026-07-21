"""
vigia/dashboard/app.py
--------------------------
Dashboard Universal de Agente Vigía — Agente Autónomo de Integridad Decisional.

Este dashboard es completamente dinámico: se adapta a cualquier fuente de datos
sin asumir un esquema predefinido. El usuario carga su base de datos y el sistema
descubre, audita y genera insights automáticamente.

Powered by Amazon Bedrock (Claude) / NVIDIA NIM / OpenAI + Streamlit
"""
import sys
import os

# Añadir el root del proyecto al path para que los imports funcionen
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import streamlit as st
from dotenv import load_dotenv

# Cargar .env si existe (desarrollo local)
load_dotenv(os.path.join(root_dir, ".env"))


# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agente Vigía — Integridad Decisional",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS personalizado
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5986 100%);
        border-radius: 12px;
        padding: 20px;
        color: white;
        text-align: center;
        margin: 4px;
    }
    .metric-card h1 { margin: 0; font-size: 2.5rem; }
    .metric-card p  { margin: 4px 0 0; font-size: 0.85rem; opacity: 0.85; }
    .badge-secure   { background:#1a7a4a; color:white; padding:4px 12px; border-radius:20px; font-weight:bold; }
    .badge-caution  { background:#b38600; color:white; padding:4px 12px; border-radius:20px; font-weight:bold; }
    .badge-corrupt  { background:#cc0000; color:white; padding:4px 12px; border-radius:20px; font-weight:bold; }
    .llm-badge-bedrock { background:#ff9900; color:#000; padding:3px 10px; border-radius:12px; font-size:0.8rem; font-weight:bold; }
    .llm-badge-nvidia  { background:#76b900; color:#fff; padding:3px 10px; border-radius:12px; font-size:0.8rem; font-weight:bold; }
    .llm-badge-openai  { background:#10a37f; color:#fff; padding:3px 10px; border-radius:12px; font-size:0.8rem; font-weight:bold; }
    .llm-badge-mock    { background:#6c757d; color:#fff; padding:3px 10px; border-radius:12px; font-size:0.8rem; font-weight:bold; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# DETECCIÓN DEL MODO LLM ACTIVO
# ─────────────────────────────────────────────────────────────────────────────

def detect_llm_mode() -> tuple[str, str]:
    """Devuelve (modo_label, badge_class) según las variables de entorno."""
    aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    has_bedrock = bool(aws_key and aws_secret and aws_key != "your_access_key_id_here")

    if not has_bedrock:
        try:
            import boto3
            session = boto3.session.Session()
            creds = session.get_credentials()
            has_bedrock = creds is not None
        except Exception:
            has_bedrock = False

    if has_bedrock:
        model = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
        return f"🟠 Amazon Bedrock ({model.split('.')[1].split('-')[0].title()})", "llm-badge-bedrock"

    if os.environ.get("NVIDIA_API_KEY"):
        model = os.environ.get("NVIDIA_MODEL_ID", "deepseek-ai/deepseek-v4-pro")
        short = model.split("/")[-1]
        return f"🟢 NVIDIA NIM ({short})", "llm-badge-nvidia"

    if os.environ.get("OPENAI_API_KEY"):
        model = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o-mini")
        return f"🔵 OpenAI ({model})", "llm-badge-openai"

    return "⚫ Modo Local (sin API)", "llm-badge-mock"


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

llm_label, llm_badge_class = detect_llm_mode()

with st.sidebar:
    st.markdown("## 🛡️ Agente Vigía")
    st.caption("Agente Universal de Integridad de Datos")
    st.markdown("---")

    st.markdown(f'**Motor IA:** <span class="{llm_badge_class}">{llm_label}</span>', unsafe_allow_html=True)
    st.markdown("")

    # Fuente de datos activa
    source_name = st.session_state.get("source_name", None)
    if source_name:
        st.markdown(f"**Fuente activa:** `{source_name}`")
        if st.button("🔄 Cambiar fuente de datos"):
            # Limpiar estado
            for key in ["connection_config", "analysis_ready", "source_name",
                        "analysis_results", "connector_instance",
                        "trace_flow_state", "selected_trace_step"]:
                st.session_state.pop(key, None)
            st.rerun()
    
    st.markdown("---")

    # Configuración de LLM
    with st.expander("⚙️ Configurar Amazon Bedrock", expanded=False):
        st.caption("Credenciales de AWS para usar Claude como motor de IA.")
        ui_aws_key = st.text_input("AWS Access Key ID", type="password", placeholder="AKIA...")
        ui_aws_secret = st.text_input("AWS Secret Access Key", type="password", placeholder="wJalr...")
        ui_aws_region = st.selectbox(
            "Región",
            ["us-east-1", "us-west-2", "eu-central-1", "ap-southeast-1"],
            index=0,
        )
        ui_model = st.selectbox(
            "Modelo Bedrock",
            [
                "anthropic.claude-3-haiku-20240307-v1:0",
                "anthropic.claude-3-sonnet-20240229-v1:0",
                "anthropic.claude-instant-v1",
            ],
            index=0,
        )
        if st.button("💾 Aplicar Bedrock"):
            if ui_aws_key and ui_aws_secret:
                os.environ["AWS_ACCESS_KEY_ID"] = ui_aws_key
                os.environ["AWS_SECRET_ACCESS_KEY"] = ui_aws_secret
                os.environ["AWS_DEFAULT_REGION"] = ui_aws_region
                os.environ["BEDROCK_MODEL_ID"] = ui_model
                st.session_state.pop("analysis_results", None)
                st.success("✅ Credenciales aplicadas.")
                st.rerun()
            else:
                st.warning("Ingresa Access Key ID y Secret Access Key.")

    with st.expander("⚙️ Configurar NVIDIA NIM", expanded=False):
        st.caption("API gratuita en [build.nvidia.com](https://build.nvidia.com)")
        ui_nvidia_key = st.text_input("NVIDIA API Key", type="password", placeholder="nvapi-...", key="nv_key")
        ui_nvidia_model = st.selectbox(
            "Modelo NVIDIA",
            [
                "deepseek-ai/deepseek-v4-pro",
                "deepseek-ai/deepseek-v4-flash",
                "meta/llama-3.3-70b-instruct",
                "nvidia/llama-3.1-nemotron-ultra-253b-v1",
            ],
            index=0,
            key="nv_model",
        )
        if st.button("💾 Aplicar NVIDIA", key="btn_nv"):
            if ui_nvidia_key:
                os.environ["NVIDIA_API_KEY"] = ui_nvidia_key
                os.environ["NVIDIA_MODEL_ID"] = ui_nvidia_model
                os.environ.pop("AWS_ACCESS_KEY_ID", None)
                os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
                os.environ.pop("OPENAI_API_KEY", None)
                st.session_state.pop("analysis_results", None)
                st.success("✅ NVIDIA NIM configurado.")
                st.rerun()
            else:
                st.warning("Ingresa tu NVIDIA API Key.")

    # Mostrar score si hay análisis
    if "analysis_results" in st.session_state:
        results = st.session_state["analysis_results"]
        score = results["audit_report"].global_quality_score
        st.markdown("---")
        st.subheader("Score de Confianza")
        if score >= 80:
            score_color, badge_label = "#1a7a4a", "🛡️ SEGURO"
        elif score >= 50:
            score_color, badge_label = "#b38600", "⚠️ PRECAUCIÓN"
        else:
            score_color, badge_label = "#cc0000", "🚨 COMPROMETIDO"

        st.markdown(
            f"""<div style="background:#f0f2f6;padding:18px;border-radius:10px;
                            border-left:8px solid {score_color};text-align:center;">
                <h1 style="color:{score_color};margin:0;font-size:3rem;">{score:.1f}</h1>
                <p style="color:#555;margin:4px 0 0;font-weight:bold;">{badge_label}</p>
                <p style="color:#888;font-size:0.75rem;margin:0;">/ 100 puntos</p>
            </div>""",
            unsafe_allow_html=True,
        )

        st.markdown("---")
        if st.button("🧠 Regenerar Reporte IA"):
            st.session_state.pop("analysis_results", None)
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# LÓGICA PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def run_analysis(config):
    """Ejecuta el pipeline completo: connect → inspect → audit → insights."""
    import time
    from vigia.connectors.base import ConnectorType
    from vigia.connectors.sqlite_connector import SQLiteConnector
    from vigia.connectors.csv_connector import CSVConnector
    from vigia.inspector.schema_inspector import SchemaInspector
    from vigia.audit.generic_engine import GenericAuditEngine
    from vigia.insight.generic_engine import GenericInsightEngine
    from vigia.tracing import TraceCollector, EventType

    trace = TraceCollector()
    trace.start_pipeline()

    # ─── Stage 1: Connector ──────────────────────────────────────────────
    with trace.stage("connector", "Conexión a Fuente de Datos", "🔌"):
        t0 = time.time()
        if config.connector_type == ConnectorType.SQLITE:
            connector = SQLiteConnector(config)
            trace.info("connector", f"Tipo: SQLite")
        elif config.connector_type in (ConnectorType.CSV, ConnectorType.EXCEL):
            connector = CSVConnector(config)
            trace.info("connector", f"Tipo: CSV/Excel")
        else:
            trace.error("connector", f"Conector '{config.connector_type}' no soportado")
            raise ValueError(f"Conector '{config.connector_type}' no soportado aún.")

        connector.connect()
        tables = connector.get_tables()
        trace.tool("connector", "connect", 
                   inputs={"type": config.connector_type.value},
                   outputs={"tables_found": len(tables), "table_names": tables},
                   duration_ms=(time.time() - t0) * 1000)
        trace.decision("connector", "Fuente conectada exitosamente",
                       reasoning=f"Se detectaron {len(tables)} tablas",
                       outcome="Proceder a inspección de esquema")

    # ─── Stage 2: Schema Inspector ───────────────────────────────────────
    with trace.stage("inspector", "Inspección de Esquema", "🔍"):
        t0 = time.time()
        inspector = SchemaInspector(connector)
        schema_metadata = inspector.inspect()

        trace.tool("inspector", "inspect_schema",
                   inputs={"tables": [t.name for t in schema_metadata.tables]},
                   outputs={
                       "total_tables": schema_metadata.total_tables,
                       "total_columns": schema_metadata.total_columns,
                       "total_rows": schema_metadata.total_rows,
                       "declared_relationships": len(schema_metadata.declared_relationships),
                       "inferred_relationships": len(schema_metadata.inferred_relationships),
                   },
                   duration_ms=(time.time() - t0) * 1000)

        # Log semantic classifications
        classified = [p for p in schema_metadata.column_profiles 
                      if p.semantic_label and p.semantic_label.confidence >= 0.6]
        trace.info("inspector", f"Clasificación semántica: {len(classified)} columnas clasificadas")
        for p in classified[:10]:
            trace.finding("inspector", 
                         f"{p.table_name}.{p.column_name} → {p.semantic_label.semantic_type.value} ({p.semantic_label.confidence:.0%})",
                         details={"table": p.table_name, "column": p.column_name,
                                  "type": p.semantic_label.semantic_type.value,
                                  "confidence": p.semantic_label.confidence})

        # Log inferred relationships
        for rel in schema_metadata.inferred_relationships:
            trace.finding("inspector",
                         f"Relación inferida: {rel.source_table}.{rel.source_column} → {rel.target_table}.{rel.target_column}",
                         details={"confidence": rel.confidence, "method": rel.method})

        if schema_metadata.limitations:
            for lim in schema_metadata.limitations:
                trace.warning("inspector", lim)

        trace.decision("inspector", "Esquema descubierto completamente",
                       reasoning=f"{schema_metadata.total_tables} tablas, {schema_metadata.total_columns} columnas, "
                                 f"{len(schema_metadata.inferred_relationships)} relaciones inferidas",
                       outcome="Proceder a auditoría de calidad")

    # ─── Stage 3: Audit Engine ───────────────────────────────────────────
    with trace.stage("audit", "Auditoría de Calidad", "🔍"):
        t0 = time.time()
        audit_engine = GenericAuditEngine(connector, schema_metadata)
        audit_report = audit_engine.run_audit()

        trace.tool("audit", "run_audit",
                   inputs={"rules_count": len(audit_engine.rules),
                           "rules": [r.name for r in audit_engine.rules]},
                   outputs={
                       "global_score": audit_report.global_quality_score,
                       "total_findings": audit_report.total_findings,
                       "critical": audit_report.critical_findings,
                       "errors": audit_report.error_findings,
                       "warnings": audit_report.warning_findings,
                   },
                   duration_ms=(time.time() - t0) * 1000)

        # Log per-table results
        for s in audit_report.table_summaries:
            trace.metric("audit", f"Score: {s.table_name}", s.quality_score)
            if s.findings_count > 0:
                trace.finding("audit", 
                             f"{s.table_name}: {s.quality_score:.1f}/100 ({s.findings_count} hallazgos)",
                             details={"table": s.table_name, "score": s.quality_score,
                                      "critical": s.critical_count, "errors": s.error_count})

        # Log top findings
        for f in sorted(audit_report.findings, 
                        key=lambda x: {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}.get(x.level.value, 4))[:8]:
            trace.finding("audit",
                         f"[{f.level.value}] {f.table}.{f.column}: {f.message}",
                         details={"level": f.level.value, "category": f.category.value,
                                  "rule": f.rule_name, "affected_rows": f.affected_rows})

        trace.metric("audit", "Data Quality Score", audit_report.global_quality_score)
        trace.decision("audit", f"Auditoría completada — Score: {audit_report.global_quality_score:.1f}/100",
                       reasoning=f"{audit_report.total_findings} hallazgos detectados en {audit_report.total_tables_audited} tablas",
                       outcome="Proceder a generación de insights")

    # ─── Stage 4: Insight Engine ─────────────────────────────────────────
    with trace.stage("insight", "Generación de Insights", "💡"):
        t0 = time.time()
        insight_engine = GenericInsightEngine(connector, schema_metadata, audit_report)
        insight_report = insight_engine.run_analysis()

        trace.tool("insight", "detect_risks",
                   inputs={"audit_score": audit_report.global_quality_score},
                   outputs={"risks_detected": len(insight_report.risks)},
                   duration_ms=(time.time() - t0) * 1000)

        # Log risks
        for risk in insight_report.risks[:5]:
            trace.finding("insight",
                         f"[{risk.priority.value}] {risk.risk_type} — {risk.table}",
                         details={"priority": risk.priority.value, "table": risk.table,
                                  "description": risk.description})

    # ─── Stage 5: LLM Report ────────────────────────────────────────────
    with trace.stage("llm", "Generación de Reporte IA", "🧠"):
        trace.info("llm", f"Proveedor utilizado: {insight_report.llm_provider_used}")
        trace.tool("llm", f"generate_report ({insight_report.llm_provider_used})",
                   inputs={"provider": insight_report.llm_provider_used,
                           "context_keys": ["schema_summary", "quality_summary", "findings", "risks"]},
                   outputs={"report_length": len(insight_report.report_markdown),
                            "provider_used": insight_report.llm_provider_used})
        
        if insight_report.llm_provider_used == "mock":
            trace.info("llm", "Usando generador local (no hay API keys configuradas)")
        else:
            trace.info("llm", f"Reporte generado con {insight_report.llm_provider_used}")

        trace.decision("llm", "Reporte ejecutivo generado",
                       reasoning=f"Proveedor: {insight_report.llm_provider_used}, "
                                 f"Longitud: {len(insight_report.report_markdown)} caracteres",
                       outcome="Pipeline completo")

    trace.end_pipeline(success=True)

    return {
        "connector": connector,
        "schema_metadata": schema_metadata,
        "audit_report": audit_report,
        "insight_report": insight_report,
        "trace": trace,
    }


# ─────────────────────────────────────────────────────────────────────────────
# FLUJO DE LA APLICACIÓN
# ─────────────────────────────────────────────────────────────────────────────

# Header principal
st.markdown("## 🛡️ Agente Vigía: Agente Universal de Integridad de Datos")
st.markdown(
    "*\"La mayoría de los agentes IA analizan datos. "
    "Agente Vigía primero determina si esos datos merecen ser analizados.\"*"
)

# ¿Hay una fuente configurada?
config = st.session_state.get("connection_config", None)

if config is None:
    # Mostrar página de upload
    st.markdown("---")
    from vigia.dashboard.views.upload import render_upload_page
    render_upload_page()

else:
    # Ejecutar análisis si no está cacheado
    if "analysis_results" not in st.session_state:
        with st.spinner("🛡️ Agente Vigía analizando datos... Esto puede tomar unos segundos."):
            try:
                results = run_analysis(config)
                st.session_state["analysis_results"] = results
                st.rerun()
            except Exception as e:
                st.error(f"Error durante el análisis: {e}")
                import traceback
                with st.expander("Detalles del error"):
                    st.code(traceback.format_exc())
                if st.button("⬅️ Volver a carga de datos"):
                    for key in ["connection_config", "analysis_ready", "source_name",
                                "analysis_results", "trace_flow_state", "selected_trace_step"]:
                        st.session_state.pop(key, None)
                    st.rerun()
                st.stop()

    # Mostrar resultados
    results = st.session_state["analysis_results"]
    schema_metadata = results["schema_metadata"]
    audit_report = results["audit_report"]
    insight_report = results["insight_report"]
    connector = results["connector"]
    trace = results.get("trace")

    # KPIs rápidos en la parte superior
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Score Global", f"{audit_report.global_quality_score:.1f}%")
    k2.metric("Tablas", schema_metadata.total_tables)
    k3.metric("Filas Totales", f"{schema_metadata.total_rows:,}")
    k4.metric("Hallazgos", audit_report.total_findings)
    k5.metric("Riesgos", len(insight_report.risks), delta_color="inverse")
    st.markdown("---")

    # Tabs principales
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📂 Datos",
        "🗂️ Esquema",
        "🔍 Auditoría",
        "💡 Insights",
        "⚡ Execution Trace",
        "📋 Resumen",
    ])

    with tab1:
        from vigia.dashboard.views.data_view import render_data_page
        render_data_page(connector, schema_metadata)

    with tab2:
        from vigia.dashboard.views.schema_view import render_schema_page
        render_schema_page(schema_metadata)

    with tab3:
        from vigia.dashboard.views.audit_view import render_audit_page
        render_audit_page(audit_report)

    with tab4:
        from vigia.dashboard.views.insights_view import render_insights_page
        render_insights_page(insight_report)

    with tab5:
        if trace:
            from vigia.dashboard.views.trace_view import render_trace_page
            render_trace_page(trace)
        else:
            st.info("No hay datos de traza disponibles para esta ejecución.")

    with tab6:
        # Resumen ejecutivo rápido
        st.header("📋 Resumen Ejecutivo")
        st.markdown(f"**Fuente:** `{st.session_state.get('source_name', 'Desconocida')}`")
        st.markdown(f"**Score de Confianza:** {audit_report.global_quality_score:.1f}/100")
        st.markdown(f"**Tablas auditadas:** {audit_report.total_tables_audited}")
        st.markdown(f"**Registros totales:** {audit_report.total_rows_audited:,}")
        st.markdown(f"**Hallazgos:** {audit_report.total_findings} "
                    f"({audit_report.critical_findings} críticos, "
                    f"{audit_report.error_findings} errores, "
                    f"{audit_report.warning_findings} advertencias)")
        st.markdown(f"**Riesgos detectados:** {len(insight_report.risks)}")
        st.markdown(f"**Motor IA usado:** {insight_report.llm_provider_used}")

        # Reporte inline
        if insight_report.report_markdown:
            st.markdown("---")
            st.markdown(insight_report.report_markdown)
