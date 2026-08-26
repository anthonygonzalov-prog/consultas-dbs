import streamlit as st
import duckdb
import pandas as pd
import os
import gdown

# ID extraído de tu enlace de Google Drive
DRIVE_FILE_ID = "1ZIVfT0629q69uXEUPxI0gdTxYgQW0bYB"
DB_FILENAME = "dbs_database.duckdb"

# Función con caché para descargar la base de datos si no existe en la nube
@st.cache_resource
def get_connection():
    if not os.path.exists(DB_FILENAME):
        url = f"https://drive.google.com/uc?id={DRIVE_FILE_ID}"
        gdown.download(url, DB_FILENAME, quiet=False)
    return duckdb.connect(DB_FILENAME, read_only=True)

# Configuración de la página Streamlit
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
np_input = st.sidebar.text_input("Número de Parte (NP):", placeholder="Ej. 1714571").strip()

search_btn = st.sidebar.button("🔎 Buscar", type="primary", use_container_width=True)

if search_btn or plaqueteo_input or np_input:
    where_clauses = []
    
    if plaqueteo_input:
        where_clauses.append(f"UPPER(CAST(r.PLAQUETEO AS VARCHAR)) LIKE UPPER('%{plaqueteo_input}%')")
    if np_input:
        where_clauses.append(f"UPPER(CAST(r.NP AS VARCHAR)) LIKE UPPER('%{np_input}%')")
        
    where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    query = f"""
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
            df_result = conn.execute(query).df()
            
            if not df_result.empty:
                st.success(f"Se encontraron **{len(df_result)}** registros coincidentes.")
                
                # Resaltar en negrita la columna HORAS
                styler = df_result.style.map(
                    lambda v: 'font-weight: bold; background-color: #f0f2f6;', subset=['HORAS']
                )
                
                st.dataframe(styler, use_container_width=True, height=450, hide_index=True)
                
                csv = df_result.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar resultados en CSV",
                    data=csv,
                    file_name="resultado_consulta_dbs.csv",
                    mime="text/csv"
                )
            else:
                st.warning("⚠️ No se encontraron coincidencias para los datos ingresados.")
        except Exception as e:
            st.error(f"Error en la consulta: {e}")
else:
    st.info("👈 Ingresa un **Plaqueteo** o **Número de Parte (NP)** en el menú lateral para realizar una búsqueda.")
