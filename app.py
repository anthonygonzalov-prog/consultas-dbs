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

# ---------------------------------------------------------
# IMAGEN SUPERIOR EN EL MENÚ LATERAL
# ---------------------------------------------------------
st.sidebar.image(
    "https://drive.google.com/uc?export=view&id=1gqbPrRs2E4ibPv8Ief5TAqMLO6UMJOoO",
    use_container_width=True
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
ot_taller_input = st.sidebar.text_input("OT TALLER:", placeholder="Ej. AQ01969").strip()
ot_sucursal_input = st.sidebar.text_input("OT SUCURSAL:", placeholder="Ej. PC18504").strip()
desc_rpto_input = st.sidebar.text_input("DESCRIPCION RPTO:", placeholder="Ej. BEARING o SEAL").strip()
maq_input = st.sidebar.text_input("MAQ:", placeholder="Ej. 793D").strip()

search_btn = st.sidebar.button("🔎 Buscar", type="primary", use_container_width=True)

has_filter = any([plaqueteo_input, np_input, ot_taller_input, ot_sucursal_input, desc_rpto_input, maq_input])

if search_btn or has_filter:
    # ---------------------------------------------------------
    # CONDICIONES DE FILTRADO UNIFICADAS
    # ---------------------------------------------------------
    where_repuestos = []
    if plaqueteo_input:
        where_repuestos.append(f"UPPER(CAST(r.PLAQUETEO AS VARCHAR)) LIKE UPPER('%{plaqueteo_input}%')")
    if np_input:
        where_repuestos.append(f"UPPER(CAST(r.NP AS VARCHAR)) LIKE UPPER('%{np_input}%')")
    if ot_taller_input:
        where_repuestos.append(f"UPPER(CAST(r.OT_CHILD AS VARCHAR)) LIKE UPPER('%{ot_taller_input}%')")
    if ot_sucursal_input:
        where_repuestos.append(f"UPPER(CAST(r.OT_MAIN AS VARCHAR)) LIKE UPPER('%{ot_sucursal_input}%')")
    if desc_rpto_input:
        where_repuestos.append(f"UPPER(CAST(r.\"DESCRIPCION RPTO\" AS VARCHAR)) LIKE UPPER('%{desc_rpto_input}%')")
    if maq_input:
        where_repuestos.append(f"UPPER(CAST(r.MAQ AS VARCHAR)) LIKE UPPER('%{maq_input}%')")

    where_rep_str = " WHERE " + " AND ".join(where_repuestos) if where_repuestos else ""

    # ---------------------------------------------------------
    # TABLA 1: Coincidencias en Repuestos (Cruce de Horas por Sucursal/Taller)
    # ---------------------------------------------------------
    query1 = f"""
        SELECT 
            r.OT_CHILD AS "OT TALLER",
            r.OT_MAIN AS "OT SUCURSAL",
            CAST(r.FEC_APERTURA_OT_DBS AS DATE) AS "FECHA DBS",
            r.COMPONENTE,
            r.MAQ,
            r.PLAQUETEO,
            r.DES_CLIENTE,
            r.NP,
            r."DESCRIPCION RPTO",
            r.NUM_CANTIDAD,
            COALESCE(h1.HORAS, h2.HORAS) AS HORAS
        FROM repuestos r
        LEFT JOIN horas h1
            ON UPPER(TRIM(CAST(r.OT_MAIN AS VARCHAR))) = UPPER(TRIM(CAST(h1."OT SUCURSAL" AS VARCHAR)))
           AND UPPER(TRIM(CAST(r.OT_CHILD AS VARCHAR))) = UPPER(TRIM(CAST(h1."OT TALLER" AS VARCHAR)))
        LEFT JOIN horas h2
            ON UPPER(TRIM(CAST(r.OT_MAIN AS VARCHAR))) = UPPER(TRIM(CAST(h2."OT SUCURSAL" AS VARCHAR)))
        {where_rep_str}
        ORDER BY CAST(r.FEC_APERTURA_OT_DBS AS DATE) ASC
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
                st.dataframe(styler1, use_container_width=True, height=350, hide_index=True)
            else:
                st.warning("⚠️ No se encontraron coincidencias directas en repuestos.")

            # ---------------------------------------------------------
            # TABLA 2: Historial de Horas (Solo si se ingresa Número de Parte)
            # ---------------------------------------------------------
            if np_input:
                st.markdown("---")
                st.subheader(f"📊 Tabla 2: Historial de Horas y Estado para NP ({np_input})")

                query2 = f"""
                    SELECT 
                        h."OT TALLER",
                        h."OT SUCURSAL",
                        h.COMPONENTE,
                        h.HORAS,
                        '{np_input}' AS NP,
                        CASE 
                            WHEN COUNT(r.NP) FILTER (WHERE UPPER(TRIM(CAST(r.NP AS VARCHAR))) = UPPER('{np_input}')) > 0 THEN 'SE PIDIO'
                            WHEN COUNT(r.OT_MAIN) > 0 THEN 'SE REUTILIZO'
                            ELSE 'SIN REGISTRO'
                        END AS ESTADO,
                        CAST(MAX(r.FEC_APERTURA_OT_DBS) AS DATE) AS "FECHA DBS"
                    FROM horas h
                    INNER JOIN repuestos r
                        ON UPPER(TRIM(CAST(h."OT SUCURSAL" AS VARCHAR))) = UPPER(TRIM(CAST(r.OT_MAIN AS VARCHAR)))
                    {where_rep_str}
                    GROUP BY h."OT TALLER", h."OT SUCURSAL", h.COMPONENTE, h.HORAS
                    ORDER BY "FECHA DBS" ASC NULLS LAST
                    LIMIT 2000
                """

                df_result2 = conn.execute(query2).df()

                if not df_result2.empty:
                    def highlight_estado(val):
                        if val == 'SE PIDIO':
                            return 'background-color: #d4edda; font-weight: bold; color: #155724;'
                        elif val == 'SE REUTILIZO':
                            return 'background-color: #fff2cc; font-weight: bold; color: #7f6000;'
                        return ''

                    styler2 = df_result2.style.map(highlight_estado, subset=['ESTADO'])
                    st.dataframe(styler2, use_container_width=True, height=450, hide_index=True)
                else:
                    st.info("No hay registros de horas vinculados a estos filtros exactos.")

        except Exception as e:
            st.error(f"Error en la consulta: {e}")
else:
    st.info("👈 Ingresa al menos un filtro en el menú lateral para realizar una búsqueda.")
