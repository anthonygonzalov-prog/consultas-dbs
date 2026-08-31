import streamlit as st
import duckdb
import pandas as pd
import os
import gdown

DRIVE_FILE_ID = "1EyrwzIzyHRyEhlJvReBRGmBCYG7Q28gN"
DB_FILENAME = "dbs_database.duckdb"

@st.cache_resource
def get_connection():
    if not os.path.exists(DB_FILENAME):
        url = f"https://drive.google.com/uc?id={DRIVE_FILE_ID}"
        gdown.download(url, DB_FILENAME, quiet=False, fuzzy=True)
    return duckdb.connect(DB_FILENAME, read_only=True)

st.set_page_config(
    page_title="Consultas DBS (AQ - LJ - CR)",
    page_icon="🚜",
    layout="wide"
)

st.title("🚜 Consultas DBS (AQ - LJ - CR) - Consumo de repuestos y horas")
st.markdown("Consulta en tiempo real entre más de **2.8 millones de registros**.")

try:
    conn = get_connection()
except Exception as e:
    st.error("No se pudo descargar o conectar a la base de datos de Google Drive.")
    st.stop()

# Panel lateral de filtros
st.sidebar.header("🔍 Filtros de Búsqueda")

plaqueteo_input = st.sidebar.text_input("PLAQUETEO:", placeholder="Ej. FDB100072706").strip()
np_input = st.sidebar.text_input("Número de Parte (NP):", placeholder="Ej. 1714571 o 7W3193").strip()

search_btn = st.sidebar.button("🔎 Buscar", type="primary", use_container_width=True)

if search_btn or plaqueteo_input or np_input:
    # ---------------------------------------------------------
    # TABLA 1: Coincidencias en Repuestos (Búsqueda Principal)
    # ---------------------------------------------------------
    where_clauses = []
    if plaqueteo_input:
        where_clauses.append(f"UPPER(CAST(r.PLAQUETEO AS VARCHAR)) LIKE UPPER('%{plaqueteo_input}%')")
    if np_input:
        where_clauses.append(f"UPPER(CAST(r.NP AS VARCHAR)) LIKE UPPER('%{np_input}%')")
        
    where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    query1 = f"""
        SELECT 
            r.OT_MAIN,
            r.OT_CHILD,
            r.FEC_APERTURA_OT_DBS,
            r.COMPONENTE,
            r.MAQ,
            r.PLAQUETEO,
            r.DES_CLIENTE,
            r.NP,
            r."DESCRIPCION RPTO",
            r.NUM_CANTIDAD,
            h.HORAS
        FROM repuestos r
        LEFT JOIN horas h
            ON UPPER(TRIM(CAST(r.OT_MAIN AS VARCHAR))) = UPPER(TRIM(CAST(h."OT SUCURSAL" AS VARCHAR)))
           AND UPPER(TRIM(CAST(r.OT_CHILD AS VARCHAR))) = UPPER(TRIM(CAST(h."OT TALLER" AS VARCHAR)))
        {where_str}
        LIMIT 2000
    """
    
    with st.spinner("Consultando registros..."):
        try:
            df_result1 = conn.execute(query1).df()
            
            st.subheader("📋 Tabla 1: Repuestos Utilizados y Horas")
            if not df_result1.empty:
                st.success(f"Se encontraron **{len(df_result1)}** registros coincidentes.")
                styler1 = df_result1.style.map(
                    lambda v: 'font-weight: bold; background-color: #f0f2f6;', subset=['HORAS']
                )
                st.dataframe(styler1, use_container_width=True, height=300, hide_index=True)
            else:
                st.warning("⚠️ No se encontraron coincidencias directas en repuestos.")
                
            # ---------------------------------------------------------
            # TABLA 2: Registro completo de Horas + Clasificación
            # ---------------------------------------------------------
            st.markdown("---")
            st.subheader("📊 Tabla 2: Historial de Horas y Estado del Repuesto")
            
            # Filtro opcional por Plaqueteo si fue ingresado
            horas_filter = ""
            if plaqueteo_input:
                horas_filter = f"""
                WHERE UPPER(TRIM(CAST(h."OT SUCURSAL" AS VARCHAR))) IN (
                    SELECT UPPER(TRIM(CAST(OT_MAIN AS VARCHAR))) 
                    FROM repuestos 
                    WHERE UPPER(CAST(PLAQUETEO AS VARCHAR)) LIKE UPPER('%{plaqueteo_input}%')
                )
                """

            query2 = f"""
                SELECT 
                    h."OT TALLER",
                    h."OT SUCURSAL",
                    h.COMPONENTE,
                    h.HORAS,
                    '{np_input}' AS NP,
                    CASE 
                        WHEN '{np_input}' != '' AND COUNT(r.NP) FILTER (WHERE UPPER(TRIM(CAST(r.NP AS VARCHAR))) = UPPER('{np_input}')) > 0 THEN 'SE PIDIO'
                        WHEN COUNT(r.OT_MAIN) > 0 THEN 'SE REUTILIZO'
                        ELSE 'SIN REGISTRO'
                    END AS ESTADO,
                    MAX(r.FEC_APERTURA_OT_DBS) AS DESPACHO
                FROM horas h
                LEFT JOIN repuestos r
                    ON UPPER(TRIM(CAST(h."OT SUCURSAL" AS VARCHAR))) = UPPER(TRIM(CAST(r.OT_MAIN AS VARCHAR)))
                   AND UPPER(TRIM(CAST(h."OT TALLER" AS VARCHAR))) = UPPER(TRIM(CAST(r.OT_CHILD AS VARCHAR)))
                {horas_filter}
                GROUP BY h."OT TALLER", h."OT SUCURSAL", h.COMPONENTE, h.HORAS
                ORDER BY h.HORAS DESC
                LIMIT 2000
            """
            
            df_result2 = conn.execute(query2).df()
            
            if not df_result2.empty:
                def highlight_estado(val):
                    if val in ['SE PIDIO', 'SE REUTILIZO']:
                        return 'background-color: #fff2cc; font-weight: bold; color: #7f6000;'
                    return ''

                styler2 = df_result2.style.map(highlight_estado, subset=['ESTADO'])
                st.dataframe(styler2, use_container_width=True, height=450, hide_index=True)
            else:
                st.info("No hay registros en la tabla de horas.")
                    
        except Exception as e:
            st.error(f"Error en la consulta: {e}")
else:
    st.info("👈 Ingresa un **Plaqueteo** o **Número de Parte (NP)** en el menú lateral para realizar una búsqueda.")
