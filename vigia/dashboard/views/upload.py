"""
vigia.dashboard.pages.upload
--------------------------------
Página de carga de fuente de datos.
Soporta: SQLite, CSV, Excel.
Futuro: PostgreSQL, MySQL, SQL Server.
"""

from __future__ import annotations

import os
import tempfile

import streamlit as st

from vigia.connectors.base import ConnectionConfig, ConnectorType


def render_upload_page():
    """Renderiza la interfaz de carga/conexión de datos."""
    st.header("📤 Cargar Fuente de Datos")
    st.markdown(
        "Sube tu base de datos o archivo de datos para que Agente Vigía "
        "la inspeccione y audite automáticamente."
    )

    # Tabs por tipo de fuente
    tab_file, tab_db = st.tabs(["📁 Archivo", "🔌 Base de Datos Remota"])

    with tab_file:
        _render_file_upload()

    with tab_db:
        _render_remote_connection()


def _render_file_upload():
    """Upload de archivos locales (SQLite, CSV, Excel)."""
    st.subheader("Subir archivo")
    st.caption("Formatos soportados: SQLite (.db, .sqlite), CSV (.csv), Excel (.xlsx, .xls)")

    uploaded_file = st.file_uploader(
        "Selecciona tu archivo",
        type=["db", "sqlite", "sqlite3", "csv", "xlsx", "xls"],
        help="Arrastra un archivo o haz clic para seleccionar.",
    )

    if uploaded_file is not None:
        file_name = uploaded_file.name
        file_ext = os.path.splitext(file_name)[1].lower()
        file_bytes = uploaded_file.read()
        file_size_mb = len(file_bytes) / (1024 * 1024)

        st.success(f"Archivo cargado: **{file_name}** ({file_size_mb:.2f} MB)")

        # Opciones según tipo
        config = None

        if file_ext in (".db", ".sqlite", ".sqlite3"):
            st.info("Tipo detectado: **SQLite Database**")
            config = ConnectionConfig(
                connector_type=ConnectorType.SQLITE,
                file_bytes=file_bytes,
            )

        elif file_ext == ".csv":
            st.info("Tipo detectado: **CSV**")
            col1, col2 = st.columns(2)
            with col1:
                encoding = st.selectbox(
                    "Encoding", 
                    ["utf-8", "latin-1", "iso-8859-1", "cp1252", "ascii"],
                    index=0,
                )
            with col2:
                delimiter = st.selectbox(
                    "Delimitador",
                    ["Auto-detectar", ",", ";", "\\t (tab)", "|"],
                    index=0,
                )

            delim_map = {"Auto-detectar": None, ",": ",", ";": ";", "\\t (tab)": "\t", "|": "|"}
            actual_delimiter = delim_map.get(delimiter)

            table_name = st.text_input(
                "Nombre para la tabla (opcional)",
                value=os.path.splitext(file_name)[0].replace(" ", "_"),
            )

            config = ConnectionConfig(
                connector_type=ConnectorType.CSV,
                file_bytes=file_bytes,
                options={
                    "encoding": encoding,
                    "delimiter": actual_delimiter,
                    "table_name": table_name,
                    "file_extension": file_ext,
                },
            )

        elif file_ext in (".xlsx", ".xls"):
            st.info("Tipo detectado: **Excel**")
            sheet_name = st.text_input(
                "Nombre de hoja (vacío = todas las hojas)", value=""
            )
            config = ConnectionConfig(
                connector_type=ConnectorType.CSV,  # CSVConnector maneja Excel internamente
                file_bytes=file_bytes,
                options={
                    "file_extension": file_ext,
                    "sheet_name": sheet_name if sheet_name else None,
                },
            )

        if config:
            if st.button("🚀 Analizar Datos", type="primary", use_container_width=True):
                st.session_state["connection_config"] = config
                st.session_state["analysis_ready"] = False
                st.session_state["source_name"] = file_name
                st.rerun()

    # Demo mode
    st.markdown("---")
    st.subheader("🎮 Modo Demo")
    st.caption(
        "Carga la base de datos de demostración con datos intencionalmente corruptos "
        "para ver las capacidades de Agente Vigía."
    )
    if st.button("Cargar Demo (SQLite)", use_container_width=True):
        from vigia.database.connection import DEFAULT_DB_PATH
        from vigia.database.seed import seed_data

        # Re-sembrar para asegurar datos frescos
        seed_data(DEFAULT_DB_PATH)

        config = ConnectionConfig(
            connector_type=ConnectorType.SQLITE,
            file_path=DEFAULT_DB_PATH,
        )
        st.session_state["connection_config"] = config
        st.session_state["analysis_ready"] = False
        st.session_state["source_name"] = "Demo: vigia.db"
        st.rerun()


def _render_remote_connection():
    """Formulario de conexión a bases de datos remotas."""
    st.subheader("Conexión a Base de Datos Remota")
    st.caption("Conecta directamente a tu motor de base de datos.")

    db_type = st.selectbox(
        "Motor de Base de Datos",
        ["PostgreSQL", "MySQL", "SQL Server (próximamente)", "Oracle (próximamente)"],
        index=0,
    )

    if "próximamente" in db_type:
        st.warning(f"{db_type} estará disponible en una versión futura.")
        return

    col1, col2 = st.columns(2)
    with col1:
        host = st.text_input("Host", value="localhost")
        database = st.text_input("Base de datos", placeholder="mi_base_datos")
        username = st.text_input("Usuario", placeholder="admin")
    with col2:
        port_default = 5432 if "PostgreSQL" in db_type else 3306
        port = st.number_input("Puerto", value=port_default, min_value=1, max_value=65535)
        password = st.text_input("Contraseña", type="password")
        ssl = st.checkbox("Usar SSL", value=False)

    connector_type = ConnectorType.POSTGRESQL if "PostgreSQL" in db_type else ConnectorType.MYSQL

    if st.button("🔌 Conectar y Analizar", type="primary", use_container_width=True):
        if not database or not username:
            st.error("Base de datos y usuario son requeridos.")
            return

        config = ConnectionConfig(
            connector_type=connector_type,
            host=host,
            port=int(port),
            database=database,
            username=username,
            password=password,
            options={"ssl": ssl},
        )
        st.session_state["connection_config"] = config
        st.session_state["analysis_ready"] = False
        st.session_state["source_name"] = f"{db_type}: {database}@{host}"
        st.rerun()
