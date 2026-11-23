import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import time
from utils.procesamiento import leer_archivo, preparar_marcaciones, analizar_asistencia
from utils.validaciones import detectar_columnas, validar_base
from utils.configuracion import DEFAULT_CONFIG, generar_medio_dia_default
from utils.reportes import excel_consolidado, excel_individual


st.set_page_config(page_title="Control de Asistencia | RH", page_icon="🗓️", layout="wide")
st.title("Control de asistencia")
st.caption("Análisis de marcaciones, incidencias y reportes de recursos humanos")

if "config" not in st.session_state: st.session_state.config = DEFAULT_CONFIG.copy()

with st.sidebar:
    st.header("Configuración de horario")
    cfg = st.session_state.config
    entrada = st.time_input("Hora de entrada", value=cfg["hora_entrada"])
    salida = st.time_input("Hora de salida", value=cfg["hora_salida"])
    tolerancia = st.number_input("Tolerancia de entrada (minutos)", min_value=0, max_value=120, value=int(cfg["tolerancia_minutos"]))
    medio_salida = st.time_input("Hora esperada de salida en medio día", value=cfg["medio_dia_hora_salida"])
    cfg.update(hora_entrada=entrada, hora_salida=salida, tolerancia_minutos=tolerancia, medio_dia_hora_salida=medio_salida)
    st.info("Días laborales configurados: lunes a viernes. Las salidas se infieren emparejando marcaciones cronológicamente; el Estado del CSV no se toma como confiable.")

st.subheader("1. Cargar archivo de asistencia")
attendance_file = st.file_uploader("CSV, XLSX o XLS", type=["csv", "xlsx", "xls"], key="attendance")

vac_file = st.file_uploader("2. Archivo de vacaciones autorizadas (Excel/CSV)", type=["xlsx", "xls", "csv"], key="vac")
holiday_file = st.file_uploader("3. Archivo de días festivos (Excel/CSV)", type=["xlsx", "xls", "csv"], key="holiday")
half_file = st.file_uploader("4. Archivo de días de medio horario (Excel/CSV)", type=["xlsx", "xls", "csv"], key="half")

if attendance_file:
    try:
        raw = leer_archivo(attendance_file)
        st.success(f"Archivo cargado: {len(raw):,} registros | {len(raw.columns)} columnas")
        with st.expander("Vista previa y estructura", expanded=True):
            st.dataframe(raw.head(20), use_container_width=True)
            st.write(pd.DataFrame({"Columna":raw.columns, "Tipo":raw.dtypes.astype(str).values, "Vacíos":raw.isna().sum().values}))
        auto = detectar_columnas(raw)
        st.subheader("Mapeo de columnas")
        cols = list(raw.columns)
        col_emp = st.selectbox("Columna de empleado", cols, index=cols.index(auto.get("empleado", cols[0])) if auto.get("empleado", cols[0]) in cols else 0)
        col_dt = st.selectbox("Columna fecha y hora", cols, index=cols.index(auto.get("tiempo", cols[0])) if auto.get("tiempo", cols[0]) in cols else 0)
        col_id = st.selectbox("ID de empleado (opcional)", ["-- No usar --"] + cols, index=(cols.index(auto["id"])+1 if auto.get("id") in cols else 0))
        avisos, errores = validar_base(raw, col_emp, col_dt)
        for e in errores: st.error(e)
        for a in avisos: st.warning(a)
        vac, fest, medio = None, None, None
        if vac_file:
            vac = leer_archivo(vac_file)
            st.caption(f"Vacaciones: {len(vac)} filas")
        if holiday_file:
            fest = leer_archivo(holiday_file)
            st.caption(f"Festivos: {len(fest)} filas")
        if half_file:
            medio = leer_archivo(half_file)
        else:
            years = pd.to_datetime(raw[col_dt], errors="coerce", dayfirst=True).dt.year.dropna().unique()
            medio = pd.DataFrame(generar_medio_dia_default(years if len(years) else [pd.Timestamp.now().year]))
        st.subheader("Administración de medio horario")
        if medio is not None:
            medio_edit = st.data_editor(medio, num_rows="dynamic", use_container_width=True, key="medio_editor")
            medio = medio_edit
        if st.button("Analizar asistencia", type="primary", use_container_width=True):
            try:
                marc = preparar_marcaciones(raw, col_emp, col_dt, None if col_id == "-- No usar --" else col_id)
                resumen, detalle, incid = analizar_asistencia(marc, vac, fest, medio, cfg)
                st.session_state["results"] = (marc, resumen, detalle, incid)
                st.success("Análisis completado.")
            except Exception as ex:
                st.error(f"No fue posible analizar el archivo: {ex}")
    except Exception as ex:
        st.error(f"Error al leer el archivo: {ex}")

if "results" in st.session_state:
    marc, resumen, detalle, incid = st.session_state["results"]
    st.divider()
    st.subheader("Dashboard ejecutivo")
    total_emp = marc["EmpleadoNorm"].nunique() if not marc.empty else 0
faltas = int(detalle["Faltas"].sum()) if not detalle.empty else 0
retardos = int(detalle["Retardos"].sum()) if not detalle.empty else 0
incompletos = int(detalle["Registros Incompletos"].sum()) if not detalle.empty else 0
dias = int(detalle["Días Trabajados"].sum()) if not detalle.empty else 0
c1,c2,c3,c4,c5=st.columns(5)
c1.metric("Empleados", total_emp); c2.metric("Faltas", faltas); c3.metric("Retardos", retardos); c4.metric("Registros incompletos", incompletos); c5.metric("Días trabajados", dias)
if not detalle.empty:
    monthly = detalle.groupby("Mes", as_index=False).agg(Faltas=("Faltas","sum"), Retardos=("Retardos","sum"), Trabajados=("Días Trabajados","sum"))
    c1,c2=st.columns(2)
    with c1: st.plotly_chart(px.bar(monthly, x="Mes", y="Faltas", title="Faltas por mes"), use_container_width=True)
    with c2: st.plotly_chart(px.bar(monthly, x="Mes", y="Retardos", title="Retardos por mes"), use_container_width=True)
    emp_inc = incid.groupby("Empleado").size().reset_index(name="Incidencias") if not incid.empty else pd.DataFrame(columns=["Empleado","Incidencias"])
    if not emp_inc.empty:
        st.plotly_chart(px.bar(emp_inc.sort_values("Incidencias", ascending=False), x="Empleado", y="Incidencias", title="Incidencias por empleado"), use_container_width=True)
        st.plotly_chart(px.bar(emp_inc.sort_values("Incidencias", ascending=False).head(10), x="Empleado", y="Incidencias", title="Top empleados con incidencias"), use_container_width=True)
    if not incid.empty:
        dist=incid["Tipo de Incidencia"].value_counts().reset_index()
        dist.columns=["Incidencia","Cantidad"]
        st.plotly_chart(px.pie(dist, names="Incidencia", values="Cantidad", title="Distribución de incidencias"), use_container_width=True)
    st.subheader("Reportes")
    tab1,tab2,tab3=st.tabs(["Resumen mensual","Detalle diario","Incidencias"])
    with tab1: st.dataframe(resumen, use_container_width=True)
    with tab2: st.dataframe(detalle, use_container_width=True)
    with tab3: st.dataframe(incid, use_container_width=True)
    st.subheader("Exportaciones")
    st.download_button("Descargar Excel de resumen mensual", excel_individual(resumen,"Resumen mensual"), "resumen_mensual.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("Descargar Excel de detalle diario", excel_individual(detalle,"Detalle diario"), "detalle_diario.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("Descargar Excel de incidencias", excel_individual(incid,"Incidencias"), "incidencias.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("Descargar Excel consolidado", excel_consolidado(resumen,detalle,incid), "control_asistencia_consolidado.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("Carga el archivo de asistencia y presiona **Analizar asistencia** para generar el dashboard y los reportes.")
