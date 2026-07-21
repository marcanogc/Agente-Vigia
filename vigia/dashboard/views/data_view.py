"""
vigia.dashboard.pages.data_view
------------------------------------
Exploración de los datos crudos cargados por el usuario.
Muestra las tablas detectadas con sus datos.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from vigia.connectors.base import BaseConnector
from vigia.models.schema_models import SchemaMetadata


def render_data_page(connector: BaseConnector, schema: SchemaMetadata):
    """Renderiza la vista de datos crudos."""
    st.header("📂 Explorador de Datos")
    st.markdown(
        "Visualiza los datos crudos tal como fueron cargados. "
        "Utiliza los filtros para navegar por las diferentes tablas."
    )

    tables = connector.get_tables()
    if not tables:
        st.warning("No se encontraron tablas en la fuente de datos.")
        return

    # Selector de tabla
    selected_table = st.selectbox(
        "Seleccionar tabla",
        options=tables,
        format_func=lambda t: f"{t} ({_get_row_count(schema, t)} filas)",
    )

    if selected_table:
        table_info = schema.get_table(selected_table)
        row_count = table_info.row_count if table_info else 0

        # Info de la tabla
        st.caption(
            f"Tabla: **{selected_table}** | "
            f"Filas: **{row_count:,}** | "
            f"Columnas: **{len(table_info.columns) if table_info else 0}**"
        )

        # Controles de paginación
        col1, col2 = st.columns([3, 1])
        with col2:
            rows_to_show = st.selectbox(
                "Filas a mostrar",
                [25, 50, 100, 250, 500],
                index=1,
            )

        # Cargar datos
        try:
            data = connector.sample_data(selected_table, limit=rows_to_show)
            if data:
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True, hide_index=True)

                if row_count > rows_to_show:
                    st.caption(
                        f"Mostrando las primeras {rows_to_show} filas de {row_count:,} totales."
                    )
            else:
                st.info("La tabla está vacía.")
        except Exception as e:
            st.error(f"Error al cargar datos: {e}")

        # Estadísticas rápidas
        st.markdown("---")
        st.subheader("📊 Estadísticas Rápidas")

        if table_info:
            stats_data = []
            for col in table_info.columns:
                profile = schema.get_column_profile(selected_table, col.name)
                if profile:
                    stats_data.append({
                        "Columna": col.name,
                        "Tipo": col.generic_type.value,
                        "Nulls": profile.null_count,
                        "Nulls %": f"{profile.null_percentage:.1f}%",
                        "Distintos": profile.distinct_count,
                        "Unicidad %": f"{profile.uniqueness:.1f}%",
                    })

            if stats_data:
                st.dataframe(
                    pd.DataFrame(stats_data),
                    use_container_width=True,
                    hide_index=True,
                )


def _get_row_count(schema: SchemaMetadata, table_name: str) -> int:
    """Helper para obtener conteo de filas."""
    table_info = schema.get_table(table_name)
    return table_info.row_count if table_info else 0
