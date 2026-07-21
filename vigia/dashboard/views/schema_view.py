"""
vigia.dashboard.pages.schema_view
--------------------------------------
Visualización del esquema detectado: tablas, columnas, tipos,
relaciones declaradas e inferidas, clasificación semántica.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from vigia.models.schema_models import SchemaMetadata, SemanticType


def render_schema_page(schema: SchemaMetadata):
    """Renderiza la vista del esquema detectado."""
    st.header("🗂️ Esquema Detectado")
    st.markdown(
        f"Se descubrieron **{schema.total_tables} tablas**, "
        f"**{schema.total_columns} columnas** y "
        f"**{schema.total_rows:,} filas** en total."
    )

    # Métricas rápidas
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tablas", schema.total_tables)
    m2.metric("Columnas", schema.total_columns)
    m3.metric("Filas Totales", f"{schema.total_rows:,}")
    rel_count = len(schema.declared_relationships) + len(schema.inferred_relationships)
    m4.metric("Relaciones", rel_count)

    st.markdown("---")

    # Detalle por tabla
    st.subheader("📋 Detalle de Tablas")

    for table in schema.tables:
        with st.expander(f"**{table.name}** — {len(table.columns)} columnas, {table.row_count:,} filas", expanded=False):
            # Construir DataFrame de columnas
            col_data = []
            for col in table.columns:
                profile = schema.get_column_profile(table.name, col.name)
                semantic = ""
                confidence = ""
                if profile and profile.semantic_label and profile.semantic_label.confidence >= 0.5:
                    semantic = profile.semantic_label.semantic_type.value
                    confidence = f"{profile.semantic_label.confidence:.0%}"

                col_data.append({
                    "Columna": col.name,
                    "Tipo": col.raw_type,
                    "Tipo Genérico": col.generic_type.value,
                    "Nullable": "✓" if col.nullable else "✗",
                    "PK": "🔑" if col.is_primary_key else "",
                    "Unique": "✓" if col.is_unique else "",
                    "Semántica": semantic,
                    "Confianza": confidence,
                })

            df = pd.DataFrame(col_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Mostrar PKs y FKs
            if table.primary_keys:
                st.caption(f"🔑 Clave Primaria: `{', '.join(table.primary_keys)}`")
            if table.foreign_keys:
                st.caption("🔗 Claves Foráneas:")
                for fk in table.foreign_keys:
                    st.caption(f"  • `{fk.column}` → `{fk.referenced_table}.{fk.referenced_column}`")

    # Relaciones
    st.markdown("---")
    st.subheader("🔗 Relaciones")

    if schema.declared_relationships or schema.inferred_relationships:
        tab_declared, tab_inferred = st.tabs(["Declaradas", "Inferidas"])

        with tab_declared:
            if schema.declared_relationships:
                rel_data = [{
                    "Origen": f"{fk.column}",
                    "Destino": f"{fk.referenced_table}.{fk.referenced_column}",
                    "Constraint": fk.constraint_name or "—",
                } for fk in schema.declared_relationships]
                st.dataframe(pd.DataFrame(rel_data), use_container_width=True, hide_index=True)
            else:
                st.info("No se encontraron claves foráneas declaradas en el esquema.")

        with tab_inferred:
            if schema.inferred_relationships:
                rel_data = [{
                    "Origen": f"{r.source_table}.{r.source_column}",
                    "Destino": f"{r.target_table}.{r.target_column}",
                    "Confianza": f"{r.confidence:.0%}",
                    "Método": r.method,
                    "Razonamiento": r.reasoning,
                } for r in schema.inferred_relationships]
                st.dataframe(pd.DataFrame(rel_data), use_container_width=True, hide_index=True)
            else:
                st.info("No se pudieron inferir relaciones adicionales.")
    else:
        st.info("No se detectaron relaciones entre tablas.")

    # Limitaciones
    if schema.limitations:
        st.markdown("---")
        st.subheader("⚠️ Limitaciones del Descubrimiento")
        for lim in schema.limitations:
            st.warning(lim)
