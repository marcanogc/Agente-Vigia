"""
vigia.dashboard.views.trace_view
---------------------------------
Visualización interactiva del flujo de ejecución del agente.
Usa streamlit-flow-component (React Flow) para renderizar un grafo
interactivo donde cada nodo representa una etapa del pipeline.

Inspirado en Google AI Studio, LangGraph Studio, LangSmith y Flowise.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from vigia.tracing import TraceCollector, EventType

try:
    from streamlit_flow import streamlit_flow
    from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
    from streamlit_flow.state import StreamlitFlowState
    from streamlit_flow.layouts import LayeredLayout
    HAS_FLOW_COMPONENT = True
except ImportError:
    HAS_FLOW_COMPONENT = False


# ─────────────────────────────────────────────────────────────────────────────
# Configuración de estilos por stage
# ─────────────────────────────────────────────────────────────────────────────

_STAGE_STYLES = {
    "completed": {
        "border": "2px solid #28a745",
        "background": "linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%)",
        "boxShadow": "0 4px 12px rgba(40,167,69,0.3)",
    },
    "error": {
        "border": "2px solid #dc3545",
        "background": "linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%)",
        "boxShadow": "0 4px 12px rgba(220,53,69,0.3)",
    },
    "running": {
        "border": "2px solid #007bff",
        "background": "linear-gradient(135deg, #cce5ff 0%, #b8daff 100%)",
        "boxShadow": "0 4px 12px rgba(0,123,255,0.3)",
    },
    "pending": {
        "border": "2px solid #6c757d",
        "background": "linear-gradient(135deg, #e9ecef 0%, #dee2e6 100%)",
        "boxShadow": "none",
    },
}

_EDGE_COLORS = {
    "completed": "#28a745",
    "error": "#dc3545",
    "running": "#007bff",
    "pending": "#6c757d",
}


def render_trace_page(trace: TraceCollector):
    """Renderiza la vista de ejecución del agente con grafo interactivo."""
    st.header("⚡ Agent Execution Trace")
    st.markdown(
        "Visualización interactiva del razonamiento del agente. "
        "**Haz clic en cualquier nodo** para ver los detalles de esa etapa."
    )

    # ─── Métricas de resumen ─────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("⏱️ Duración Total", trace.total_duration_str)
    col2.metric("📦 Etapas", len(trace.steps))
    col3.metric("📊 Eventos", len(trace.events))
    status_text = "✅ Exitoso" if trace._pipeline_end else "🔄 En curso"
    col4.metric("Estado", status_text)

    st.markdown("---")

    # ─── Grafo interactivo ───────────────────────────────────────────────
    if HAS_FLOW_COMPONENT and trace.steps:
        _render_interactive_graph(trace)
    else:
        if not HAS_FLOW_COMPONENT:
            st.warning(
                "Instala `streamlit-flow-component` para ver el grafo interactivo: "
                "`pip install streamlit-flow-component`"
            )
        _render_fallback_timeline(trace)

    st.markdown("---")

    # ─── Panel de detalle del nodo seleccionado ──────────────────────────
    _render_detail_panel(trace)

    # ─── Tabla de eventos completa ───────────────────────────────────────
    st.markdown("---")
    _render_events_table(trace)


def _render_interactive_graph(trace: TraceCollector):
    """Renderiza el grafo con React Flow (streamlit-flow-component)."""
    st.subheader("🗺️ Pipeline de Ejecución")
    st.caption("Haz clic en un nodo para ver los detalles de la etapa.")

    nodes = []
    edges = []

    for i, step in enumerate(trace.steps):
        node_id = f"node_{i}"
        status_icon = {"completed": "✅", "error": "❌", "running": "🔄", "pending": "⏳"}.get(step.status, "⚪")
        
        # Construir contenido HTML del nodo
        style = _STAGE_STYLES.get(step.status, _STAGE_STYLES["pending"])
        
        node_content = (
            f"<div style='padding:8px;text-align:center;min-width:180px;'>"
            f"<div style='font-size:1.5rem;'>{step.icon}</div>"
            f"<div style='font-weight:bold;font-size:0.9rem;margin:4px 0;'>{step.display_name}</div>"
            f"<div style='font-size:0.75rem;color:#555;'>{status_icon} {step.duration_str}</div>"
            f"<div style='font-size:0.7rem;color:#888;margin-top:2px;'>"
            f"{len(step.events)} eventos</div>"
            f"</div>"
        )

        node = StreamlitFlowNode(
            id=node_id,
            pos=(0, 0),  # Layout engine handles positioning
            data={"content": node_content},
            node_type="default",
            source_position="right",
            target_position="left",
            style={
                "border": style["border"],
                "borderRadius": "12px",
                "padding": "0",
                "fontSize": "12px",
                "background": "#ffffff",
                "boxShadow": style.get("boxShadow", "none"),
            },
        )
        nodes.append(node)

        # Arista hacia el siguiente nodo
        if i > 0:
            prev_status = trace.steps[i - 1].status
            edge_color = _EDGE_COLORS.get(prev_status, "#6c757d")
            edge = StreamlitFlowEdge(
                id=f"edge_{i-1}_{i}",
                source=f"node_{i-1}",
                target=node_id,
                animated=(prev_status == "completed"),
                style={"stroke": edge_color, "strokeWidth": 2},
                marker_end={"type": "arrowclosed", "color": edge_color},
            )
            edges.append(edge)

    # Renderizar el componente — IMPORTANTE: solo crear el state una vez
    # para evitar el loop infinito de re-renders (ver docs v1.6.1)
    state_key = "trace_flow_state"
    if state_key not in st.session_state:
        st.session_state[state_key] = StreamlitFlowState(nodes, edges)

    st.session_state[state_key] = streamlit_flow(
        "agent_execution_trace",
        st.session_state[state_key],
        layout=LayeredLayout(direction="right"),
        fit_view=True,
        height=280,
        enable_node_menu=False,
        enable_edge_menu=False,
        enable_pane_menu=False,
        hide_watermark=True,
        allow_new_edges=False,
        style={"backgroundColor": "#fafbfc"},
    )

    # Capturar click en nodo
    selected = st.session_state[state_key].selected_id
    if selected and selected.startswith("node_"):
        idx = int(selected.replace("node_", ""))
        if 0 <= idx < len(trace.steps):
            st.session_state["selected_trace_step"] = idx


def _render_detail_panel(trace: TraceCollector):
    """Panel de detalle cuando se selecciona un nodo."""
    selected_idx = st.session_state.get("selected_trace_step", None)

    if selected_idx is None:
        # Mostrar resumen por defecto
        st.subheader("📋 Selecciona una etapa para ver detalles")
        st.caption("Haz clic en cualquier nodo del grafo para inspeccionar su ejecución.")
        
        # Vista compacta de todos los stages
        for i, step in enumerate(trace.steps):
            status_icon = {"completed": "✅", "error": "❌", "running": "🔄", "pending": "⏳"}.get(step.status, "⚪")
            col1, col2, col3 = st.columns([0.5, 4, 1.5])
            with col1:
                st.markdown(f"**{step.icon}**")
            with col2:
                st.markdown(f"**{step.display_name}** — {status_icon} {len(step.events)} eventos")
            with col3:
                st.markdown(f"`{step.duration_str}`")
            
            if st.button(f"Ver detalles", key=f"btn_step_{i}", use_container_width=True):
                st.session_state["selected_trace_step"] = i
                st.rerun()
        return

    # Detalle del step seleccionado
    step = trace.steps[selected_idx]
    status_icon = {"completed": "✅", "error": "❌", "running": "🔄", "pending": "⏳"}.get(step.status, "⚪")

    # Header del detalle
    col1, col2 = st.columns([5, 1])
    with col1:
        st.subheader(f"{step.icon} {step.display_name} {status_icon}")
    with col2:
        if st.button("✖️ Cerrar", key="close_detail"):
            st.session_state.pop("selected_trace_step", None)
            st.rerun()

    # Métricas del step
    m1, m2, m3 = st.columns(3)
    m1.metric("Duración", step.duration_str)
    m2.metric("Eventos", len(step.events))
    m3.metric("Estado", step.status.upper())

    if step.summary:
        st.markdown("**Resumen:**")
        cols = st.columns(min(len(step.summary), 4))
        for col, (key, val) in zip(cols, list(step.summary.items())[:4]):
            if not isinstance(val, (dict, list)):
                col.metric(key.replace("_", " ").title(), val)

    # Eventos categorizados
    st.markdown("---")

    # Agrupar eventos por tipo
    tools = [e for e in step.events if e.event_type == EventType.TOOL_CALL]
    decisions = [e for e in step.events if e.event_type == EventType.DECISION]
    findings = [e for e in step.events if e.event_type == EventType.FINDING]
    metrics = [e for e in step.events if e.event_type == EventType.METRIC]
    infos = [e for e in step.events if e.event_type == EventType.INFO]
    warnings = [e for e in step.events if e.event_type == EventType.WARNING]
    errors = [e for e in step.events if e.event_type == EventType.ERROR]

    # Tools
    if tools:
        st.markdown("#### 🔧 Herramientas Ejecutadas")
        for t in tools:
            with st.expander(f"**{t.title}** {f'`{t.duration_str}`' if t.duration_str else ''}", expanded=True):
                inputs = t.details.get("inputs", {})
                outputs = t.details.get("outputs", {})
                col_in, col_out = st.columns(2)
                with col_in:
                    st.markdown("**📥 Inputs**")
                    if inputs:
                        st.json(inputs)
                    else:
                        st.caption("Sin inputs")
                with col_out:
                    st.markdown("**📤 Outputs**")
                    if outputs:
                        st.json(outputs)
                    else:
                        st.caption("Sin outputs")

    # Decisions
    if decisions:
        st.markdown("#### 🧠 Decisiones del Agente")
        for d in decisions:
            reasoning = d.details.get("reasoning", "")
            outcome = d.details.get("outcome", "")
            st.markdown(
                f'<div style="background:#e8f4fd;border-left:4px solid #007bff;'
                f'padding:12px 16px;border-radius:0 8px 8px 0;margin:8px 0;">'
                f'<strong>{d.title}</strong><br/>'
                f'<span style="color:#555;">💭 {reasoning}</span><br/>'
                f'<span style="color:#28a745;">➡️ {outcome}</span></div>',
                unsafe_allow_html=True,
            )

    # Findings
    if findings:
        st.markdown("#### 🔎 Hallazgos Detectados")
        for f in findings:
            details_str = ""
            if f.details:
                relevant = {k: v for k, v in f.details.items() if v and k not in ("title",)}
                if relevant:
                    details_str = " — " + ", ".join(f"`{k}: {v}`" for k, v in list(relevant.items())[:3])
            st.markdown(f"- {f.title}{details_str}")

    # Metrics
    if metrics:
        st.markdown("#### 📊 Métricas")
        metric_cols = st.columns(min(len(metrics), 4))
        for col, m in zip(metric_cols, metrics[:4]):
            value = m.details.get("value", "")
            name = m.details.get("metric", m.title)
            col.metric(name, value)

    # Info
    if infos:
        st.markdown("#### ℹ️ Información")
        for info in infos:
            st.caption(f"• {info.title}")

    # Warnings / Errors
    if warnings:
        st.markdown("#### ⚠️ Advertencias")
        for w in warnings:
            st.warning(w.title)

    if errors:
        st.markdown("#### ❌ Errores")
        for e in errors:
            st.error(e.title)


def _render_events_table(trace: TraceCollector):
    """Tabla cronológica completa de eventos."""
    with st.expander("📊 Registro Completo de Eventos", expanded=False):
        events_data = []
        for evt in trace.events:
            if evt.event_type in (EventType.PIPELINE_START, EventType.PIPELINE_END,
                                   EventType.STAGE_START, EventType.STAGE_END):
                continue  # Omitir eventos de lifecycle en la tabla

            type_labels = {
                EventType.TOOL_CALL: "🔧 Tool",
                EventType.DECISION: "🧠 Decisión",
                EventType.FINDING: "🔎 Hallazgo",
                EventType.METRIC: "📊 Métrica",
                EventType.INFO: "ℹ️ Info",
                EventType.WARNING: "⚠️ Warning",
                EventType.ERROR: "❌ Error",
                EventType.LLM_CALL: "🤖 LLM",
                EventType.LLM_RESPONSE: "🤖 LLM Resp",
            }

            events_data.append({
                "Tiempo": evt.timestamp_str,
                "Tipo": type_labels.get(evt.event_type, evt.event_type.value),
                "Etapa": evt.stage,
                "Descripción": evt.title[:80],
                "Duración": evt.duration_str or "—",
            })

        if events_data:
            df = pd.DataFrame(events_data)
            st.dataframe(df, use_container_width=True, hide_index=True, height=400)
            st.caption(f"Total: {len(events_data)} eventos registrados.")


def _render_fallback_timeline(trace: TraceCollector):
    """Fallback visual cuando streamlit-flow-component no está instalado."""
    st.subheader("🗺️ Pipeline de Ejecución")

    for i, step in enumerate(trace.steps):
        status_icon = {"completed": "✅", "error": "❌", "running": "🔄", "pending": "⏳"}.get(step.status, "⚪")
        status_color = {"completed": "#28a745", "error": "#dc3545", "running": "#007bff", "pending": "#6c757d"}.get(step.status, "#6c757d")

        st.markdown(
            f'<div style="display:flex;align-items:center;padding:16px;margin:8px 0;'
            f'background:white;border:2px solid {status_color};border-radius:12px;'
            f'box-shadow:0 2px 8px rgba(0,0,0,0.08);">'
            f'<div style="font-size:2rem;margin-right:16px;">{step.icon}</div>'
            f'<div style="flex:1;">'
            f'<div style="font-weight:bold;font-size:1rem;">{step.display_name}</div>'
            f'<div style="color:#666;font-size:0.85rem;">{len(step.events)} eventos</div>'
            f'</div>'
            f'<div style="text-align:right;">'
            f'<div style="font-size:1.1rem;">{status_icon}</div>'
            f'<div style="font-size:0.8rem;color:#888;">{step.duration_str}</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        if i < len(trace.steps) - 1:
            st.markdown(
                '<div style="text-align:center;color:#28a745;font-size:1.5rem;margin:-4px 0;">↓</div>',
                unsafe_allow_html=True,
            )
