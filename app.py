
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

from utils.procesamiento import (
    leer_archivo,
    preparar_marcaciones,
    analizar_asistencia
)
from utils.validaciones import detectar_columnas, validar_base
from utils.configuracion import DEFAULT_CONFIG, generar_medio_dia_default
from utils.reportes import excel_consolidado, excel_individual


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

st.set_page_config(
    page_title="Control de Asistencia | RH",
    page_icon="🗓️",
    layout="wide"
)

st.title("Control de asistencia")
st.caption("Sistema de control de asistencia, incidencias y vacaciones de Recursos Humanos")


# ============================================================
# INICIALIZACIÓN DE SESSION STATE
# ============================================================

if "config" not in st.session_state:
    st.session_state.config = DEFAULT_CONFIG.copy()

if "results" not in st.session_state:
    st.session_state.results = None

if "empleados_config" not in st.session_state:
    st.session_state.empleados_config = pd.DataFrame(
        columns=[
            "Empleado",
            "Fecha de alta",
            "Fecha de baja",
            "Hora de entrada especial",
            "Hora de salida especial",
            "Vacaciones acumuladas"
        ]
    )


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def convertir_hora(valor):
    """
    Convierte valores de hora a formato HH:MM.
    """
    if pd.isna(valor) or valor == "":
        return None

    try:
        return pd.to_datetime(str(valor)).strftime("%H:%M")
    except Exception:
        try:
            return str(valor)[:5]
        except Exception:
            return None


def normalizar_nombre(nombre):
    """
    Normaliza nombres para comparaciones.
    """
    if pd.isna(nombre):
        return ""

    return (
        str(nombre)
        .strip()
        .upper()
    )


def preparar_empleados_detectados(marcaciones):
    """
    Genera un listado de empleados detectados en las marcaciones.
    """
    if marcaciones is None or marcaciones.empty:
        return []

    if "EmpleadoNorm" in marcaciones.columns:
        return sorted(
            marcaciones["EmpleadoNorm"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

    if "Empleado" in marcaciones.columns:
        return sorted(
            marcaciones["Empleado"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

    return []


def generar_medio_dia_por_anio(years):
    """
    Genera automáticamente las fechas de medio horario.
    """
    fechas = []

    for year in years:

        fechas.extend([
            {
                "Fecha": pd.Timestamp(year=int(year), month=5, day=10),
                "Motivo": "Día de las Madres"
            },
            {
                "Fecha": pd.Timestamp(year=int(year), month=11, day=2),
                "Motivo": "Día de Muertos"
            },
            {
                "Fecha": pd.Timestamp(year=int(year), month=12, day=24),
                "Motivo": "Nochebuena"
            },
            {
                "Fecha": pd.Timestamp(year=int(year), month=12, day=31),
                "Motivo": "Fin de Año"
            }
        ])

    return pd.DataFrame(fechas)


def calcular_antiguedad(fecha_ingreso, fecha_calculo=None):
    """
    Calcula antigüedad en años completos.
    """
    if fecha_calculo is None:
        fecha_calculo = date.today()

    if pd.isna(fecha_ingreso):
        return 0

    fecha_ingreso = pd.to_datetime(fecha_ingreso).date()

    years = fecha_calculo.year - fecha_ingreso.year

    if (
        fecha_calculo.month,
        fecha_calculo.day
    ) < (
        fecha_ingreso.month,
        fecha_ingreso.day
    ):
        years -= 1

    return max(years, 0)


def dias_vacaciones_ley(antiguedad):
    """
    Días de vacaciones de referencia conforme al esquema mexicano
    posterior a la reforma de vacaciones dignas.

    Esta tabla es una referencia para antigüedad cumplida.
    """
    tabla = {
        1: 12,
        2: 14,
        3: 16,
        4: 18,
        5: 20,
        6: 22,
        7: 22,
        8: 22,
        9: 22,
        10: 22,
        11: 24,
        12: 24,
        13: 24,
        14: 24,
        15: 24,
        16: 26,
        17: 26,
        18: 26,
        19: 26,
        20: 26,
        21: 28,
        22: 28,
        23: 28,
        24: 28,
        25: 28,
        26: 30,
        27: 30,
        28: 30,
        29: 30,
        30: 30
    }

    if antiguedad <= 0:
        return 0

    if antiguedad in tabla:
        return tabla[antiguedad]

    if antiguedad > 30:
        return 32

    return 0


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

cfg = st.session_state.config


# ============================================================
# MENÚ LATERAL
# ============================================================

with st.sidebar:

    st.header("Configuración general")

    entrada = st.time_input(
        "Hora de entrada general",
        value=cfg["hora_entrada"]
    )

    salida = st.time_input(
        "Hora de salida general",
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
        tolerancia_minutos=tolerancia
    )

    st.info(
        """
        **Horario general**

        Lunes a viernes.

        Entrada: 08:00 AM

        Salida: 06:30 PM

        Las marcaciones de comida no se consideran.
        """
    )

    st.divider()

    st.subheader("Días de medio horario")

    st.write(
        """
        - 10 de mayo
        - 2 de noviembre
        - 24 de diciembre
        - 31 de diciembre
        """
    )


# ============================================================
# NAVEGACIÓN
# ============================================================

seccion = st.radio(
    "Sección",
    [
        "Analizar asistencia",
        "Dashboard",
        "Administración de colaboradores",
        "Vacaciones",
        "Reportes"
    ],
    horizontal=True
)

st.divider()


# ============================================================
# CARGA DE ARCHIVOS DE ASISTENCIA
# ============================================================

if seccion == "Analizar asistencia":

    st.header("Análisis de asistencia")

    attendance_file = st.file_uploader(
        "Archivo de asistencia (CSV, XLSX o XLS)",
        type=["csv", "xlsx", "xls"],
        key="attendance"
    )

    vac_file = st.file_uploader(
        "Archivo de vacaciones autorizadas",
        type=["xlsx", "xls", "csv"],
        key="vac"
    )

    holiday_file = st.file_uploader(
        "Archivo de días festivos",
        type=["xlsx", "xls", "csv"],
        key="holiday"
    )

    if attendance_file:

        try:

            raw = leer_archivo(attendance_file)

            st.success(
                f"Archivo cargado: {len(raw):,} registros | "
                f"{len(raw.columns)} columnas"
            )

            with st.expander("Vista previa y estructura del archivo"):

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


            vac = None
            fest = None

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

            if holiday_file:

                fest = leer_archivo(holiday_file)

                st.success(
                    f"Días festivos cargados: {len(fest):,} registros"
                )

                with st.expander("Vista previa de festivos"):
                    st.dataframe(
                        fest.head(20),
                        use_container_width=True
                    )

            fechas = pd.to_datetime(
                raw[col_dt],
                errors="coerce",
                dayfirst=True
            )

            years = fechas.dropna().dt.year.unique()

            if len(years):
                medio = generar_medio_dia_por_anio(years)
            else:
                medio = generar_medio_dia_por_anio(
                    [pd.Timestamp.now().year]
                )

            if st.button(
                "Analizar asistencia",
                type="primary",
                use_container_width=True
            ):

                if errores:

                    st.error(
                        "Corrige los errores antes de continuar."
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

                        st.session_state.results = (
                            marc,
                            resumen,
                            detalle,
                            incid
                        )

                        st.success(
                            "Análisis completado correctamente."
                        )

                        st.info(
                            "Ve a Dashboard o Reportes para consultar resultados."
                        )

                    except Exception as ex:

                        st.error(
                            f"Error al analizar asistencia: {ex}"
                        )

        except Exception as ex:

            st.error(
                f"Error al procesar archivo: {ex}"
            )


# ============================================================
# ADMINISTRACIÓN DE COLABORADORES
# ============================================================

elif seccion == "Administración de colaboradores":

    st.header("Administración de colaboradores")

    st.caption(
        "Configura fechas de ingreso, baja, horarios especiales "
        "y vacaciones acumuladas."
    )

    if st.session_state.results is not None:

        marc, resumen, detalle, incid = st.session_state.results

        empleados_detectados = preparar_empleados_detectados(marc)

        actuales = st.session_state.empleados_config.copy()

        existentes = (
            actuales["Empleado"].astype(str).tolist()
            if not actuales.empty
            else []
        )

        nuevos = [
            empleado
            for empleado in empleados_detectados
            if empleado not in existentes
        ]

        if nuevos:

            nuevos_df = pd.DataFrame({
                "Empleado": nuevos,
                "Fecha de alta": pd.NaT,
                "Fecha de baja": pd.NaT,
                "Hora de entrada especial": None,
                "Hora de salida especial": None,
                "Vacaciones acumuladas": 0
            })

            st.session_state.empleados_config = pd.concat(
                [actuales, nuevos_df],
                ignore_index=True
            )

    st.subheader("Listado de colaboradores")

    empleados_editados = st.data_editor(
        st.session_state.empleados_config,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Empleado": st.column_config.TextColumn(
                "Empleado",
                required=True
            ),
            "Fecha de alta": st.column_config.DateColumn(
                "Fecha de alta"
            ),
            "Fecha de baja": st.column_config.DateColumn(
                "Fecha de baja"
            ),
            "Hora de entrada especial": st.column_config.TextColumn(
                "Entrada especial (HH:MM)"
            ),
            "Hora de salida especial": st.column_config.TextColumn(
                "Salida especial (HH:MM)"
            ),
            "Vacaciones acumuladas": st.column_config.NumberColumn(
                "Vacaciones acumuladas",
                min_value=0,
                step=1
            )
        },
        key="empleados_editor"
    )

    if st.button(
        "Guardar configuración de colaboradores",
        type="primary"
    ):

        st.session_state.empleados_config = empleados_editados.copy()

        st.success(
            "Configuración guardada durante esta sesión."
        )

    st.warning(
        "La configuración de colaboradores actualmente se conserva "
        "durante la sesión. Para almacenamiento permanente será "
        "necesario conectar una base de datos."
    )

    st.subheader("Horarios especiales")

    empleados_especiales = empleados_editados[
        empleados_editados["Hora de salida especial"].notna()
        & (
            empleados_editados["Hora de salida especial"]
            .astype(str)
            .str.strip()
            != ""
        )
    ]

    if not empleados_especiales.empty:

        st.dataframe(
            empleados_especiales[
                [
                    "Empleado",
                    "Hora de entrada especial",
                    "Hora de salida especial"
                ]
            ],
            use_container_width=True
        )

    else:

        st.info(
            "No hay empleados configurados con horario especial."
        )


# ============================================================
# VACACIONES
# ============================================================

elif seccion == "Vacaciones":

    st.header("Control de vacaciones")

    st.caption(
        "Consulta vacaciones acumuladas, utilizadas y disponibles."
    )

    empleados = st.session_state.empleados_config.copy()

    if empleados.empty:

        st.warning(
            "Primero carga y analiza un archivo de asistencia "
            "para identificar empleados o registra a tus colaboradores."
        )

    else:

        empleados["Antigüedad"] = empleados["Fecha de alta"].apply(
            lambda x: calcular_antiguedad(x)
            if pd.notna(x)
            else 0
        )

        empleados["Vacaciones correspondientes"] = (
            empleados["Antigüedad"].apply(dias_vacaciones_ley)
        )

        empleados["Vacaciones acumuladas"] = pd.to_numeric(
            empleados["Vacaciones acumuladas"],
            errors="coerce"
        ).fillna(0)

        empleados["Vacaciones pendientes"] = (
            empleados["Vacaciones acumuladas"]
        )

        st.subheader("Saldo de vacaciones por empleado")

        st.dataframe(
            empleados[
                [
                    "Empleado",
                    "Fecha de alta",
                    "Antigüedad",
                    "Vacaciones correspondientes",
                    "Vacaciones acumuladas",
                    "Vacaciones pendientes"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Resumen general")

        total_acumuladas = empleados[
            "Vacaciones acumuladas"
        ].sum()

        c1, c2 = st.columns(2)

        c1.metric(
            "Total de vacaciones acumuladas",
            int(total_acumuladas)
        )

        c2.metric(
            "Total de colaboradores",
            len(empleados)
        )

        st.subheader("Exportar vacaciones")

        vacaciones_export = excel_individual(
            empleados,
            "Vacaciones"
        )

        st.download_button(
            "Descargar reporte de vacaciones",
            data=vacaciones_export,
            file_name="reporte_vacaciones.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        st.warning(
            "El saldo de vacaciones debe actualizarse con los días "
            "realmente disfrutados. Este módulo todavía no descuenta "
            "automáticamente vacaciones tomadas desde el historial."
        )


# ============================================================
# DASHBOARD
# ============================================================

elif seccion == "Dashboard":

    st.header("Dashboard ejecutivo")

    if st.session_state.results is None:

        st.info(
            "Primero carga y analiza un archivo de asistencia."
        )

    else:

        marc, resumen, detalle, incid = st.session_state.results

        total_emp = (
            marc["EmpleadoNorm"].nunique()
            if not marc.empty
            else 0
        )

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
            if not resumen.empty
            and "Registros Incompletos" in resumen.columns
            else 0
        )

        dias = (
            int(resumen["Días Trabajados"].sum())
            if not resumen.empty
            and "Días Trabajados" in resumen.columns
            else 0
        )

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric("Empleados", total_emp)
        c2.metric("Faltas", faltas)
        c3.metric("Retardos", retardos)
        c4.metric("Registros incompletos", incompletos)
        c5.metric("Días trabajados", dias)

        if not resumen.empty and "Mes" in resumen.columns:

            monthly = resumen.groupby(
                "Mes",
                as_index=False
            ).agg({
                "Faltas": "sum",
                "Retardos": "sum",
                "Días Trabajados": "sum"
            })

            st.subheader("Faltas y retardos por mes")

            c1, c2 = st.columns(2)

            with c1:

                st.plotly_chart(
                    px.bar(
                        monthly,
                        x="Mes",
                        y="Faltas",
                        title="Faltas por mes"
                    ),
                    use_container_width=True
                )

            with c2:

                st.plotly_chart(
                    px.bar(
                        monthly,
                        x="Mes",
                        y="Retardos",
                        title="Retardos por mes"
                    ),
                    use_container_width=True
                )

        if not incid.empty:

            emp_inc = incid.groupby(
                "Empleado"
            ).size().reset_index(name="Incidencias")

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

            st.plotly_chart(
                px.bar(
                    emp_inc.head(10),
                    x="Empleado",
                    y="Incidencias",
                    title="Top 10 empleados"
                ),
                use_container_width=True
            )

            if "Tipo de Incidencia" in incid.columns:

                dist = incid[
                    "Tipo de Incidencia"
                ].value_counts().reset_index()

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


# ============================================================
# REPORTES
# ============================================================

elif seccion == "Reportes":

    st.header("Reportes de asistencia")

    if st.session_state.results is None:

        st.info(
            "Primero analiza un archivo de asistencia."
        )

    else:

        marc, resumen, detalle, incid = st.session_state.results

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

        st.subheader("Exportaciones")

        c1, c2 = st.columns(2)

        with c1:

            st.download_button(
                "Descargar resumen mensual",
                data=excel_individual(
                    resumen,
                    "Resumen mensual"
                ),
                file_name="resumen_mensual.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            st.download_button(
                "Descargar detalle diario",
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
                "Descargar incidencias",
                data=excel_individual(
                    incid,
                    "Incidencias"
                ),
                file_name="incidencias.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            st.download_button(
                "Descargar Excel consolidado",
                data=excel_consolidado(
                    resumen,
                    detalle,
                    incid
                ),
                file_name="control_asistencia_consolidado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
