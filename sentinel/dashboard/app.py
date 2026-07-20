"""
sentinel/dashboard/app.py
--------------------------
Dashboard principal de Agente Vigía - Agente Autónomo de Integridad Decisional
Powered by Amazon Bedrock (Claude) + Streamlit
"""
import sys
import os

# Añadir el root del proyecto al path para que los imports funcionen
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# Cargar .env si existe (desarrollo local)
load_dotenv(os.path.join(root_dir, ".env"))

from sentinel.database.connection import DEFAULT_DB_PATH, get_connection
from sentinel.database.seed import seed_data
from sentinel.audit.engine import AuditEngine
from sentinel.insight.engine import InsightEngine

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
    .report-box {
        border: 1px solid #dde; padding: 24px; border-radius: 10px;
        background: #fafbfc; max-height: 520px; overflow-y: auto;
        font-size: 0.9rem; line-height: 1.6;
    }
    .llm-badge-bedrock { background:#ff9900; color:#000; padding:3px 10px; border-radius:12px; font-size:0.8rem; font-weight:bold; }
    .llm-badge-nvidia  { background:#76b900; color:#fff; padding:3px 10px; border-radius:12px; font-size:0.8rem; font-weight:bold; }
    .llm-badge-openai  { background:#10a37f; color:#fff; padding:3px 10px; border-radius:12px; font-size:0.8rem; font-weight:bold; }
    .llm-badge-mock    { background:#6c757d; color:#fff; padding:3px 10px; border-radius:12px; font-size:0.8rem; font-weight:bold; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# INICIALIZACIÓN DB
# ─────────────────────────────────────────────────────────────────────────────
if not os.path.exists(DEFAULT_DB_PATH):
    seed_data(DEFAULT_DB_PATH)

def load_table(table_name: str) -> pd.DataFrame:
    with get_connection(DEFAULT_DB_PATH) as conn:
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)


# ─────────────────────────────────────────────────────────────────────────────
# DETECCIÓN DEL MODO LLM ACTIVO
# ─────────────────────────────────────────────────────────────────────────────
def detect_llm_mode() -> tuple[str, str]:
    """Devuelve (modo_label, badge_class) según las variables de entorno."""
    aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    has_bedrock = bool(aws_key and aws_secret and aws_key != "your_access_key_id_here")

    # También puede haber perfil ~/.aws configurado — boto3 lo detecta automáticamente
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

llm_label, llm_badge_class = detect_llm_mode()

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ Agente Vigía")
    st.caption("Agente Autónomo de Integridad Decisional")
    st.markdown("---")

    st.markdown(f'**Motor IA:** <span class="{llm_badge_class}">{llm_label}</span>', unsafe_allow_html=True)
    st.markdown("")

    # Configuración de Bedrock desde la UI (útil en Streamlit Cloud)
    with st.expander("⚙️ Configurar Amazon Bedrock", expanded=False):
        st.caption("Rellena estos campos si no tienes un archivo .env. Los valores no se guardan entre sesiones.")
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
        if st.button("💾 Aplicar credenciales"):
            if ui_aws_key and ui_aws_secret:
                os.environ["AWS_ACCESS_KEY_ID"] = ui_aws_key
                os.environ["AWS_SECRET_ACCESS_KEY"] = ui_aws_secret
                os.environ["AWS_DEFAULT_REGION"] = ui_aws_region
                os.environ["BEDROCK_MODEL_ID"] = ui_model
                st.cache_data.clear()
                st.success("✅ Credenciales aplicadas. Recarga la página para usar Bedrock.")
                st.rerun()
            else:
                st.warning("Ingresa Access Key ID y Secret Access Key.")

    # Configuración de NVIDIA NIM desde la UI
    with st.expander("⚙️ Configurar NVIDIA NIM", expanded=False):
        st.caption(
            "API gratuita en [build.nvidia.com](https://build.nvidia.com). "
            "DeepSeek-V4-Pro es un modelo MoE de 1.6T parámetros ideal para análisis de datos complejos."
        )
        ui_nvidia_key = st.text_input(
            "NVIDIA API Key", type="password", placeholder="nvapi-...",
            key="nvidia_key_input"
        )
        ui_nvidia_model = st.selectbox(
            "Modelo NVIDIA NIM",
            [
                "deepseek-ai/deepseek-v4-pro",
                "deepseek-ai/deepseek-v4-flash",
                "meta/llama-3.3-70b-instruct",
                "nvidia/llama-3.1-nemotron-ultra-253b-v1",
                "mistralai/mistral-large-2-instruct",
            ],
            index=0,
            key="nvidia_model_select",
        )
        st.caption("🔗 Modelos disponibles: [build.nvidia.com](https://build.nvidia.com)")
        if st.button("💾 Aplicar NVIDIA API Key", key="btn_nvidia"):
            if ui_nvidia_key:
                os.environ["NVIDIA_API_KEY"] = ui_nvidia_key
                os.environ["NVIDIA_MODEL_ID"] = ui_nvidia_model
                # Limpiar otras APIs para que NVIDIA tenga prioridad
                os.environ.pop("AWS_ACCESS_KEY_ID", None)
                os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
                os.environ.pop("OPENAI_API_KEY", None)
                st.cache_data.clear()
                st.success(f"✅ NVIDIA NIM configurado con `{ui_nvidia_model}`. Recarga la página.")
                st.rerun()
            else:
                st.warning("Ingresa tu NVIDIA API Key.")

    st.markdown("---")
    st.subheader("Base de Datos")
    if st.button("🔄 Reiniciar & Resembrar DB", help="Limpia la BD SQLite y carga datos de demo"):
        seed_data(DEFAULT_DB_PATH)
        st.cache_data.clear()
        st.success("Base de datos re-sembrada exitosamente.")
        st.rerun()

    if st.button("🧠 Regenerar Reporte IA", help="Fuerza una nueva llamada al LLM ignorando el caché"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")

    # Ejecutar análisis (cacheado hasta que cambie el estado de la BD)
    # cache_key cambia cuando cambian las credenciales configuradas, invalidando el caché
    _cache_key = (
        os.environ.get("AWS_ACCESS_KEY_ID", "")[:8],
        os.environ.get("NVIDIA_API_KEY", "")[:8],
        os.environ.get("OPENAI_API_KEY", "")[:8],
        os.environ.get("BEDROCK_MODEL_ID", ""),
        os.environ.get("NVIDIA_MODEL_ID", ""),
    )

    @st.cache_data(ttl=30, show_spinner="Agente Vigía auditando datos...")
    def run_analysis_cached(_key):
        ref_date = os.environ.get("SENTINEL_REFERENCE_DATE", "2026-07-20T00:00:00")
        engine = InsightEngine(DEFAULT_DB_PATH, reference_date_str=ref_date)
        return engine.run_analysis()

    results = run_analysis_cached(_cache_key)
    audit_report = results["audit_report"]
    risk_register = results["risk_register"]
    report_markdown = results["report_markdown"]
    quality_score = audit_report["quality_score"]
    summary = audit_report["summary"]

    # Score visual en sidebar
    st.subheader("Score de Confianza")
    if quality_score >= 80:
        score_color, badge_label = "#1a7a4a", "🛡️ SEGURO"
    elif quality_score >= 50:
        score_color, badge_label = "#b38600", "⚠️ PRECAUCIÓN"
    else:
        score_color, badge_label = "#cc0000", "🚨 COMPROMETIDO"

    st.markdown(
        f"""<div style="background:#f0f2f6;padding:18px;border-radius:10px;
                        border-left:8px solid {score_color};text-align:center;">
            <h1 style="color:{score_color};margin:0;font-size:3rem;">{quality_score:.1f}</h1>
            <p style="color:#555;margin:4px 0 0;font-weight:bold;">{badge_label}</p>
            <p style="color:#888;font-size:0.75rem;margin:0;">/ 100 puntos</p>
        </div>""",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# HEADER PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("## 🛡️ Agente Vigía: Agente Autónomo de Integridad Decisional")
st.markdown(
    "*\"La mayoría de los agentes IA analizan datos. Agente Vigía primero determina si esos datos "
    "merecen ser analizados.\"*"
)

# KPIs rápidos en la parte superior
k1, k2, k3, k4 = st.columns(4)
k1.metric("Score de Confianza", f"{quality_score:.1f}%")
k2.metric("Registros Totales", summary.get("total_records", 0))
k3.metric("Errores Críticos", summary.get("failed_records", 0), delta_color="inverse")
k4.metric("Riesgos Detectados", len(risk_register), delta_color="inverse")
st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# TABS PRINCIPALES
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📂 Datos Crudos",
    "🔍 Auditoría",
    "💡 Insights",
    "📋 Acciones",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — DATOS CRUDOS
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    st.header("Datos Empresariales Crudos")
    st.markdown(
        "Datos sin validar ingeridos desde sistemas externos (ERP, Jira, Slack). "
        "Observa los defectos estructurales: presupuestos negativos, fechas inválidas, IDs nulos."
    )

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Proyectos")
        df_proj = load_table("projects")
        st.dataframe(df_proj, use_container_width=True, hide_index=True)

        st.subheader("Comunicaciones")
        df_comms = load_table("communications")
        st.dataframe(df_comms, use_container_width=True, hide_index=True)

    with col_right:
        st.subheader("Tareas")
        df_tasks = load_table("tasks")
        st.dataframe(df_tasks, use_container_width=True, hide_index=True)

        st.info(
            "**Registros corruptos visibles:**\n"
            "- `P004` tiene presupuesto de `-50,000`\n"
            "- `P005` tiene fecha inválida `2026-13-45`\n"
            "- Una tarea tiene `task_id = NULL`\n"
            "- `T004` referencia el proyecto `P009` (inexistente)"
        )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — AUDITORÍA
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.header("Logs de Auditoría de Calidad de Datos")
    st.markdown(
        "El Motor de Auditoría evalúa cada registro contra reglas estructurales, relacionales "
        "y semánticas. Los registros que fallan son bloqueados antes del análisis."
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Score de Calidad", f"{quality_score:.1f} / 100")
    m2.metric("Registros Ingresados", summary.get("total_records", 0))
    m3.metric("Registros Fallidos", summary.get("failed_records", 0))
    m4.metric("Issues Totales", summary.get("total_issues", 0))

    st.markdown("---")
    st.subheader("Detalle de Logs de Auditoría")

    logs_data = audit_report.get("logs", [])
    if logs_data:
        df_logs = pd.DataFrame(logs_data)

        fc1, fc2 = st.columns(2)
        with fc1:
            level_filter = st.multiselect(
                "Filtrar por Nivel",
                options=["ERROR", "WARNING"],
                default=["ERROR", "WARNING"],
            )
        with fc2:
            type_filter = st.multiselect(
                "Filtrar por Tipo",
                options=["STRUCTURAL", "RELATIONAL", "SEMANTIC"],
                default=["STRUCTURAL", "RELATIONAL", "SEMANTIC"],
            )

        df_filtered = df_logs[
            df_logs["level"].isin(level_filter) & df_logs["type"].isin(type_filter)
        ]

        def color_level(val):
            if val == "ERROR":
                return "background-color:#ffcccc;color:#cc0000;font-weight:bold;"
            if val == "WARNING":
                return "background-color:#fff2cc;color:#b38600;font-weight:bold;"
            return ""

        styled = df_filtered.style.map(color_level, subset=["level"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Explicación de la penalización
        with st.expander("ℹ️ Cómo se calcula el Score de Confianza"):
            st.markdown("""
| Tipo de Issue | Nivel | Penalización |
|---|---|---|
| Structural | ERROR | -15 puntos |
| Relational | ERROR | -10 puntos |
| Relational | WARNING | -5 puntos |
| Semantic | WARNING | -5 puntos |

El score comienza en 100 y se descuenta por cada issue detectado (mínimo 0).
            """)
    else:
        st.success("¡Sin errores detectados! El Score de Confianza es 100/100.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — INSIGHTS
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.header("Insights de Negocio Validados")
    st.markdown(
        "Agente Vigía **filtra todos los registros corruptos** antes del análisis. "
        "Solo datos validados alimentan el motor de IA."
    )

    stats = results["clean_stats"]
    st.success(
        f"**Dataset validado analizado:** {stats['projects_count']} proyectos · "
        f"{stats['tasks_count']} tareas · {stats['communications_count']} comunicaciones. "
        f"*(Registros corruptos bloqueados.)*"
    )

    st.markdown("---")

    col_risk, col_report = st.columns([1, 1])

    with col_risk:
        st.subheader("Registro de Riesgos Operacionales")
        if risk_register:
            df_risks = pd.DataFrame(risk_register)[
                ["risk_type", "priority", "project_id", "description", "evidence_reference"]
            ]

            def color_priority(val):
                if val == "HIGH":
                    return "background-color:#ffe6e6;color:#cc0000;font-weight:bold;"
                if val == "MEDIUM":
                    return "background-color:#e6f2ff;color:#0055cc;font-weight:bold;"
                return ""

            styled_risks = df_risks.style.map(color_priority, subset=["priority"])
            st.dataframe(styled_risks, use_container_width=True, hide_index=True)
        else:
            st.success("No se detectaron riesgos operacionales.")

    with col_report:
        st.subheader("Reporte Ejecutivo Agente Vigía")
        st.markdown(f'**Generado por:** <span class="{llm_badge_class}">{llm_label}</span>', unsafe_allow_html=True)
        st.markdown("")
        st.markdown(
            f'<div class="report-box">{report_markdown}</div>',
            unsafe_allow_html=True,
        )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — ACCIONES
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.header("Plan de Acciones y Decisiones")
    st.markdown(
        "Cada acción está vinculada a IDs específicos de registros validados, "
        "garantizando que las decisiones tengan trazabilidad completa."
    )

    stagnant = [r for r in risk_register if r["risk_type"] == "Stagnant Blocked Task"]
    sentiment = [r for r in risk_register if r["risk_type"] == "Negative Communication Sentiment"]
    deadline = [r for r in risk_register if r["risk_type"] == "Close Deadline Risk"]

    action_idx = 1
    checkboxes = {}

    if stagnant:
        t = stagnant[0]
        checkboxes["act_stagnant"] = st.checkbox(
            f"**Acción {action_idx}** 🔴 Desbloquear tarea **{t['evidence_reference']}** "
            f"en proyecto **{t['project_id']}**",
            key="act_stagnant",
            help=t["description"],
        )
        action_idx += 1

    if sentiment:
        s = sentiment[0]
        checkboxes["act_sentiment"] = st.checkbox(
            f"**Acción {action_idx}** 🔴 Investigar comunicación **{s['evidence_reference']}** "
            f"— Brecha Contexto-Datos en **{s['project_id']}**",
            key="act_sentiment",
            help=s["description"],
        )
        action_idx += 1

    if deadline:
        d = deadline[0]
        checkboxes["act_deadline"] = st.checkbox(
            f"**Acción {action_idx}** 🟡 Revisar deadline del proyecto **{d['project_id']}**",
            key="act_deadline",
            help=d["description"],
        )
        action_idx += 1

    checkboxes["act_data"] = st.checkbox(
        f"**Acción {action_idx}** ⚪ Corregir errores estructurales en datos de origen "
        f"(`P004`, `P005`, tarea con ID nulo)",
        key="act_data",
        help="Restora el Score de Confianza de datos al 100%.",
    )

    st.markdown("---")

    # Progreso de resolución
    total_actions = len(checkboxes)
    done_actions = sum(1 for v in checkboxes.values() if v)
    progress_pct = done_actions / total_actions if total_actions else 0

    st.markdown(f"**Progreso de resolución:** {done_actions}/{total_actions} acciones completadas")
    st.progress(progress_pct)

    if done_actions == total_actions:
        st.balloons()
        st.success(
            "🎉 ¡Todas las acciones completadas! La integridad operacional ha sido restaurada. "
            "Agente Vigía puede generar el próximo ciclo de insights con datos 100% confiables."
        )
    elif done_actions > 0:
        st.info(f"Buen progreso. Quedan {total_actions - done_actions} acciones pendientes.")

    # Sección de arquitectura / créditos
    st.markdown("---")
    with st.expander("🏗️ Arquitectura de Agente Vigía"):
        st.markdown("""
```
Sistemas Origen (ERP / Jira / Slack)
          │
          ▼
   ┌─────────────────┐
   │   SQLite DB     │  ← Ingesta de datos crudos (con errores intencionales)
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │  Audit Engine   │  ← Pydantic validation + reglas STRUCTURAL/RELATIONAL/SEMANTIC
   │  (Python)       │  → Produce: quality_score, audit_logs
   └────────┬────────┘
            │ Solo datos validados
            ▼
   ┌─────────────────┐
   │ Insight Engine  │  ← Detección programática de riesgos operacionales
   └────────┬────────┘
            │
            ▼
   ┌─────────────────────────────────┐
   │         LLM Layer               │
   │  1. Amazon Bedrock (Claude 3)   │  ← Motor IA principal (AWS Free Tier)
   │  2. OpenAI API (fallback)       │
   │  3. Mock local (sin API)        │
   └────────┬────────────────────────┘
            │
            ▼
   ┌─────────────────┐
   │  Streamlit UI   │  ← Dashboard interactivo (deploy en Streamlit Cloud)
   └─────────────────┘
```
        """)

    with st.expander("ℹ️ Acerca de Agente Vigía"):
        st.markdown("""
**Agente Vigía** es un agente especializado de integridad decisional desarrollado para el
**Hackathon IA Masivo Online AWS por Código Facilito 2026**.

- **Problema que resuelve:** La mayoría de los agentes IA razonan sobre todos los datos disponibles
  sin validar su integridad. Agente Vigía introduce una capa de auditoría obligatoria antes de generar
  cualquier insight, detectando la *Brecha Contexto-Datos* entre sistemas estructurados y comunicaciones.

- **Stack:** Python · SQLite · Pydantic · Amazon Bedrock (Claude 3) · Streamlit

- **Repositorio:** [github.com/marcanogc/Agente-Vigia](https://github.com)
        """)
