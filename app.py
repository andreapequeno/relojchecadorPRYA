
import streamlit as st
import pandas as pd
import plotly.express as px

from utils.procesamiento import (
    leer_archivo,
    preparar_marcaciones,
    analizar_asistencia
)
from utils.validaciones import detectar_columnas, validar_base
from utils.configuracion import DEFAULT_CONFIG, generar_medio_dia_default
from utils.reportes import excel_consolidado, excel_individual


# ============================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# ============================================================

st.set_page_config(
    page_title="Control de Asistencia | RH",
    page_icon="🗓️",
    layout="wide"
)

st.title("Control de asistencia")
st.caption("Análisis de marcaciones, incidencias y reportes de recursos humanos")


# ============================================================
# CONFIGURACIÓN INICIAL
# ============================================================

if "config" not in st.session_state:
    st.session_state.config = DEFAULT_CONFIG.copy()


# ============================================================
# SIDEBAR - CONFIGURACIÓN DE HORARIOS
# ============================================================

with st.sidebar:

    st.header("Configuración de horario")

    cfg = st.session_state.config

    entrada = st.time_input(
        "Hora de entrada",
        value=cfg["hora_entrada"]
    )

    salida = st.time_input(
        "Hora de salida",
        value=cfg["hora_salida"]
    )

    tolerancia = st.number_input(
        "Tolerancia de entrada (minutos)",
        min_value=0,
        max_value=120,
        value=int(cfg["tolerancia_minutos"])
    )

    cfg.update(
        hora_entrada=entrada,
        hora_salida=salida,
        tolerancia_minutos=tolerancia,
    )

    st.info(
        """
        **Días laborales:** lunes a viernes.

        **Marcaciones esperadas:**
        - Entrada por la mañana.
        - Salida al finalizar la jornada.

        No se consideran marcaciones de comida.

        Las entradas y salidas se identifican mediante
        la primera y última marcación del día.
        """
    )

    st.divider()

    st.subheader("Días de medio horario")

    st.write(
        """
        Los días de medio horario se generan automáticamente:
        - 10 de mayo
        - 2 de noviembre
        - 24 de diciembre
        - 31 de diciembre
        """
    )


# ============================================================
# CARGA DE ARCHIVOS
# ============================================================

st.subheader("1. Cargar archivo de asistencia")

attendance_file = st.file_uploader(
    "Archivo de asistencia (CSV, XLSX o XLS)",
    type=["csv", "xlsx", "xls"],
    key="attendance"
)

st.subheader("2. Archivos complementarios")

vac_file = st.file_uploader(
    "Archivo de vacaciones autorizadas (Excel o CSV)",
    type=["xlsx", "xls", "csv"],
    key="vac"
)

holiday_file = st.file_uploader(
    "Archivo de días festivos (Excel o CSV)",
    type=["xlsx", "xls", "csv"],
    key="holiday"
)


# ============================================================
# PROCESAMIENTO DEL ARCHIVO
# ============================================================

if attendance_file:

    try:

        raw = leer_archivo(attendance_file)

        st.success(
            f"Archivo cargado correctamente: "
            f"{len(raw):,} registros | {len(raw.columns)} columnas"
        )

        # ----------------------------------------------------
        # VISTA PREVIA
        # ----------------------------------------------------

        with st.expander("Vista previa y estructura del archivo", expanded=True):

            st.dataframe(
                raw.head(20),
                use_container_width=True
            )

            estructura = pd.DataFrame({
                "Columna": raw.columns,
                "Tipo de dato": raw.dtypes.astype(str).values,
                "Valores vacíos": raw.isna().sum().values
            })

            st.dataframe(
                estructura,
                use_container_width=True
            )

        # ----------------------------------------------------
        # DETECCIÓN AUTOMÁTICA DE COLUMNAS
        # ----------------------------------------------------

        auto = detectar_columnas(raw)

        st.subheader("3. Mapeo de columnas")

        cols = list(raw.columns)

        empleado_default = auto.get("empleado", cols[0])
        tiempo_default = auto.get("tiempo", cols[0])

        col_emp = st.selectbox(
            "Columna del empleado",
            cols,
            index=(
                cols.index(empleado_default)
                if empleado_default in cols
                else 0
            )
        )

        col_dt = st.selectbox(
            "Columna de fecha y hora",
            cols,
            index=(
                cols.index(tiempo_default)
                if tiempo_default in cols
                else 0
            )
        )

        col_id = st.selectbox(
            "ID del empleado (opcional)",
            ["-- No usar --"] + cols,
            index=(
                cols.index(auto["id"]) + 1
                if auto.get("id") in cols
                else 0
            )
        )

        # ----------------------------------------------------
        # VALIDACIÓN
        # ----------------------------------------------------

        avisos, errores = validar_base(
            raw,
            col_emp,
            col_dt
        )

        for error in errores:
            st.error(error)

        for aviso in avisos:
            st.warning(aviso)

        # ----------------------------------------------------
        # VACACIONES
        # ----------------------------------------------------

        vac = None

        if vac_file:

            vac = leer_archivo(vac_file)

            st.success(
                f"Vacaciones cargadas: {len(vac):,} registros"
            )

            with st.expander("Vista previa de vacaciones"):

                st.dataframe(
                    vac.head(20),
                    use_container_width=True
                )

        # ----------------------------------------------------
        # DÍAS FESTIVOS
        # ----------------------------------------------------

        fest = None

        if holiday_file:

            fest = leer_archivo(holiday_file)

            st.success(
                f"Días festivos cargados: {len(fest):,} registros"
            )

            with st.expander("Vista previa de días festivos"):

                st.dataframe(
                    fest.head(20),
                    use_container_width=True
                )

        # ----------------------------------------------------
        # MEDIO HORARIO AUTOMÁTICO
        # ----------------------------------------------------

        fechas = pd.to_datetime(
            raw[col_dt],
            errors="coerce",
            dayfirst=True
        )

        years = fechas.dropna().dt.year.unique()

        if len(years) > 0:

            medio = pd.DataFrame(
                generar_medio_dia_default(years)
            )

        else:

            medio = pd.DataFrame(
                generar_medio_dia_default(
                    [pd.Timestamp.now().year]
                )
            )

        st.subheader("4. Días de medio horario automáticos")

        st.info(
            "Los días de medio horario se generan automáticamente. "
            "No es necesario cargar ningún archivo."
        )

        st.dataframe(
            medio,
            use_container_width=True
        )

        # ----------------------------------------------------
        # BOTÓN DE ANÁLISIS
        # ----------------------------------------------------

        if st.button(
            "Analizar asistencia",
            type="primary",
            use_container_width=True
        ):

            if errores:

                st.error(
                    "Corrige los errores detectados antes de analizar."
                )

            else:

                try:

                    marc = preparar_marcaciones(
                        raw,
                        col_emp,
                        col_dt,
                        None if col_id == "-- No usar --" else col_id
                    )

                    resumen, detalle, incid = analizar_asistencia(
                        marc,
                        vac,
                        fest,
                        medio,
                        cfg
                    )

                    st.session_state["results"] = (
                        marc,
                        resumen,
                        detalle,
                        incid
                    )

                    st.success(
                        "Análisis de asistencia completado correctamente."
                    )

                except Exception as ex:

                    st.error(
                        f"No fue posible analizar el archivo: {ex}"
                    )

    except Exception as ex:

        st.error(
            f"Error al leer el archivo: {ex}"
        )


# ============================================================
# DASHBOARD Y REPORTES
# ============================================================

if "results" in st.session_state:

    marc, resumen, detalle, incid = st.session_state["results"]

    st.divider()

    st.subheader("Dashboard ejecutivo")

    # --------------------------------------------------------
    # MÉTRICAS
    # --------------------------------------------------------

    total_emp = (
        marc["EmpleadoNorm"].nunique()
        if not marc.empty and "EmpleadoNorm" in marc.columns
        else 0
    )

    # IMPORTANTE:
    # Las métricas acumuladas se calculan desde RESUMEN,
    # no desde DETALLE DIARIO.

    faltas = (
        int(resumen["Faltas"].sum())
        if not resumen.empty and "Faltas" in resumen.columns
        else 0
    )

    retardos = (
        int(resumen["Retardos"].sum())
        if not resumen.empty and "Retardos" in resumen.columns
        else 0
    )

    incompletos = (
        int(resumen["Registros Incompletos"].sum())
        if not resumen.empty and "Registros Incompletos" in resumen.columns
        else 0
    )

    dias = (
        int(resumen["Días Trabajados"].sum())
        if not resumen.empty and "Días Trabajados" in resumen.columns
        else 0
    )

    # --------------------------------------------------------
    # TARJETAS KPI
    # --------------------------------------------------------

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Empleados",
        total_emp
    )

    c2.metric(
        "Faltas",
        faltas
    )

    c3.metric(
        "Retardos",
        retardos
    )

    c4.metric(
        "Registros incompletos",
        incompletos
    )

    c5.metric(
        "Días trabajados",
        dias
    )

    # --------------------------------------------------------
    # GRÁFICAS MENSUALES
    # --------------------------------------------------------

    if not resumen.empty:

        columnas_mensuales = [
            columna
            for columna in [
                "Mes",
                "Faltas",
                "Retardos",
                "Días Trabajados"
            ]
            if columna in resumen.columns
        ]

        if "Mes" in columnas_mensuales:

            monthly = resumen.groupby(
                "Mes",
                as_index=False
            ).agg({
                columna: "sum"
                for columna in columnas_mensuales
                if columna != "Mes"
            })

            st.subheader("Indicadores mensuales")

            c1, c2 = st.columns(2)

            if "Faltas" in monthly.columns:

                with c1:

                    st.plotly_chart(
                        px.bar(
                            monthly,
                            x="Mes",
                            y="Faltas",
                            title="Faltas por mes",
                            labels={
                                "Mes": "Mes",
                                "Faltas": "Total de faltas"
                            }
                        ),
                        use_container_width=True
                    )

            if "Retardos" in monthly.columns:

                with c2:

                    st.plotly_chart(
                        px.bar(
                            monthly,
                            x="Mes",
                            y="Retardos",
                            title="Retardos por mes",
                            labels={
                                "Mes": "Mes",
                                "Retardos": "Total de retardos"
                            }
                        ),
                        use_container_width=True
                    )

    # --------------------------------------------------------
    # INCIDENCIAS POR EMPLEADO
    # --------------------------------------------------------

    if not incid.empty and "Empleado" in incid.columns:

        emp_inc = (
            incid.groupby("Empleado")
            .size()
            .reset_index(name="Incidencias")
        )

        emp_inc = emp_inc.sort_values(
            "Incidencias",
            ascending=False
        )

        st.subheader("Incidencias por empleado")

        st.plotly_chart(
            px.bar(
                emp_inc,
                x="Empleado",
                y="Incidencias",
                title="Incidencias acumuladas por empleado"
            ),
            use_container_width=True
        )

        st.subheader("Top 10 empleados con más incidencias")

        top10 = emp_inc.head(10)

        st.plotly_chart(
            px.bar(
                top10,
                x="Empleado",
                y="Incidencias",
                title="Top 10 empleados con más incidencias"
            ),
            use_container_width=True
        )

    # --------------------------------------------------------
    # DISTRIBUCIÓN DE INCIDENCIAS
    # --------------------------------------------------------

    if (
        not incid.empty
        and "Tipo de Incidencia" in incid.columns
    ):

        dist = (
            incid["Tipo de Incidencia"]
            .value_counts()
            .reset_index()
        )

        dist.columns = [
            "Incidencia",
            "Cantidad"
        ]

        st.subheader("Distribución de incidencias")

        st.plotly_chart(
            px.pie(
                dist,
                names="Incidencia",
                values="Cantidad",
                title="Distribución de incidencias"
            ),
            use_container_width=True
        )

    # ========================================================
    # REPORTES
    # ========================================================

    st.divider()

    st.subheader("Reportes")

    tab1, tab2, tab3 = st.tabs(
        [
            "Resumen mensual",
            "Detalle diario",
            "Incidencias"
        ]
    )

    with tab1:

        st.dataframe(
            resumen,
            use_container_width=True,
            hide_index=True
        )

    with tab2:

        st.dataframe(
            detalle,
            use_container_width=True,
            hide_index=True
        )

    with tab3:

        st.dataframe(
            incid,
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # EXPORTACIONES
    # ========================================================

    st.divider()

    st.subheader("Exportaciones")

    c1, c2 = st.columns(2)

    with c1:

        st.download_button(
            label="Descargar Excel de resumen mensual",
            data=excel_individual(
                resumen,
                "Resumen mensual"
            ),
            file_name="resumen_mensual.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        st.download_button(
            label="Descargar Excel de detalle diario",
            data=excel_individual(
                detalle,
                "Detalle diario"
            ),
            file_name="detalle_diario.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with c2:

        st.download_button(
            label="Descargar Excel de incidencias",
            data=excel_individual(
                incid,
                "Incidencias"
            ),
            file_name="incidencias.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        st.download_button(
            label="Descargar Excel consolidado",
            data=excel_consolidado(
                resumen,
                detalle,
                incid
            ),
            file_name="control_asistencia_consolidado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )


# ============================================================
# MENSAJE INICIAL
# ============================================================

else:

    st.info(
        """
        Carga el archivo de asistencia y presiona
        **Analizar asistencia** para generar el dashboard
        y los reportes.
        """
    )
