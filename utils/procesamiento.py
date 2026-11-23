import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from utils.validaciones import normalizar_texto



def convertir_datetime(serie):
    s = serie.astype(str).str.strip()
    # Normaliza abreviaturas AM/PM usadas por exportaciones regionales de reloj.
    s = s.str.replace("a. m.", "AM", regex=False).str.replace("p. m.", "PM", regex=False)
    return pd.to_datetime(s, dayfirst=True, errors="coerce")

def leer_archivo(uploaded):
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        raw = uploaded.getvalue()
        for enc in ["utf-8-sig", "cp1252", "latin1"]:
            try:
                from io import BytesIO
                return pd.read_csv(BytesIO(raw), encoding=enc)
            except UnicodeDecodeError:
                continue
        from io import BytesIO
        return pd.read_csv(BytesIO(raw), encoding_errors="replace")
    return pd.read_excel(uploaded)

def preparar_marcaciones(df, col_empleado, col_tiempo, col_id=None):
    out = df.copy()
    out["Empleado"] = out[col_empleado].astype(str).str.strip()
    out["FechaHora"] = convertir_datetime(out[col_tiempo])
    out = out[out["Empleado"].notna() & out["Empleado"].ne("") & out["FechaHora"].notna()].copy()
    out["Fecha"] = out["FechaHora"].dt.date
    out["Hora"] = out["FechaHora"].dt.time
    out["EmpleadoNorm"] = out["Empleado"].map(normalizar_texto)
    out["IDEmpleado"] = out[col_id].astype(str).str.strip() if col_id and col_id in out.columns else ""
    out = out.sort_values(["EmpleadoNorm", "FechaHora"]).drop_duplicates()
    return out

def _to_dates(df, col_fecha="Fecha"):
    if df is None or df.empty or col_fecha not in df.columns:
        return set()
    return set(pd.to_datetime(df[col_fecha], errors="coerce").dropna().dt.date)

def _vacaciones_map(vacaciones):
    mapa = {}
    if vacaciones is None or vacaciones.empty:
        return mapa
    cols = {c.lower().strip(): c for c in vacaciones.columns}
    emp = cols.get("empleado")
    ini = cols.get("fecha inicio")
    fin = cols.get("fecha fin")
    if not (emp and ini and fin):
        return mapa
    for _, r in vacaciones.iterrows():
        nombre = normalizar_texto(r[emp])
        a = pd.to_datetime(r[ini], errors="coerce")
        b = pd.to_datetime(r[fin], errors="coerce")
        if nombre and pd.notna(a) and pd.notna(b):
            for d in pd.date_range(a.date(), b.date(), freq="D"):
                mapa.setdefault(d.date(), set()).add(nombre)
    return mapa

def _pair_marks(times):
    """Empareja marcaciones ordenadas en pares. La etiqueta Estado del reloj no es confiable."""
    times = sorted(pd.Timestamp(x) for x in times)
    pairs, unmatched = [], []
    for i in range(0, len(times) - 1, 2):
        pairs.append((times[i], times[i + 1]))
    if len(times) % 2:
        unmatched.append(times[-1])
    return pairs, unmatched

def analizar_asistencia(marcaciones, vacaciones=None, festivos=None, medios_dia=None, config=None):
    config = config or {}
    entrada_obj = config.get("hora_entrada", time(8, 0))
    salida_obj = config.get("hora_salida", time(18, 30))
    tol = int(config.get("tolerancia_minutos", 10))
    laborables = set(config.get("dias_laborables", [0,1,2,3,4]))
    medio_salida = config.get("medio_dia_hora_salida", time(14,0))
    holidays = _to_dates(festivos)
    halfday = {}
    if medios_dia is not None and not medios_dia.empty and "Fecha" in medios_dia:
        for _, r in medios_dia.iterrows():
            d = pd.to_datetime(r.get("Fecha"), errors="coerce")
            if pd.notna(d): halfday[d.date()] = str(r.get("Motivo", "Medio día"))
    vac_map = _vacaciones_map(vacaciones)
    if marcaciones.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    employees = marcaciones[["EmpleadoNorm", "Empleado"]].drop_duplicates()
    dates = pd.date_range(marcaciones["FechaHora"].min().date(), marcaciones["FechaHora"].max().date(), freq="D").date
    groups = { (k[0], k[1]): g["FechaHora"].tolist() for k,g in marcaciones.groupby(["EmpleadoNorm", "Fecha"]) }
    daily, incidents = [], []
    for _, er in employees.iterrows():
        en, name = er["EmpleadoNorm"], er["Empleado"]
        for d in dates:
            if d.weekday() not in laborables:
                continue
            marks = groups.get((en, d), [])
            first = last = None
            hours = 0.0
            incomplete = 0
            status, observation = "", ""
            if d in holidays:
                status = "Día Festivo"
            elif en in vac_map.get(d, set()):
                status = "Vacaciones"
            elif d in halfday:
                status = "Medio Día"
                observation = halfday[d]
                if marks:
                    pairs, unmatched = _pair_marks(marks)
                    first = min(marks); last = max(marks)
                    hours = sum(max(0, (b-a).total_seconds()/3600) for a,b in pairs)
                    if unmatched:
                        incomplete = 1
                        incidents.append([name, d, "Registro Incompleto", "Marcación impar en fecha de medio día"])
            elif not marks:
                status = "Falta"
                incidents.append([name, d, "Falta", "Sin marcaciones en día laborable"])
            else:
                pairs, unmatched = _pair_marks(marks)
                first = min(marks); last = max(marks)
                hours = sum(max(0, (b-a).total_seconds()/3600) for a,b in pairs)
                if len(marks) == 1:
                    incomplete = 1
                    if marks[0].time() <= time(12,0):
                        status = "Entrada sin salida"
                    else:
                        status = "Salida sin entrada"
                    incidents.append([name, d, "Registro Incompleto", status])
                elif unmatched:
                    incomplete = 1
                    status = "Entrada sin salida"
                    incidents.append([name, d, "Registro Incompleto", "Número impar de marcaciones; última marcación sin pareja"])
                else:
                    deadline = (datetime.combine(d, entrada_obj) + timedelta(minutes=tol)).time()
                    if first.time() > deadline:
                        status = "Retardo"
                        incidents.append([name, d, "Retardo", f"Primera marcación {first.time()} posterior a {deadline}"])
                    else:
                        status = "Asistencia Correcta"
            # Retardo en días de medio horario también se evalúa si existen marcaciones.
            if status == "Medio Día" and marks:
                deadline = (datetime.combine(d, entrada_obj) + timedelta(minutes=tol)).time()
                if first and first.time() > deadline:
                    incidents.append([name, d, "Retardo", f"Primera marcación {first.time()} posterior a {deadline}"])
            worked = bool(marks) and status not in ["Falta", "Vacaciones", "Día Festivo"]
            daily.append({"Empleado": name, "Fecha": d, "Mes": pd.Timestamp(d).strftime("%Y-%m"), "Primera Entrada": first, "Última Salida": last,
                "Horas Trabajadas": round(hours, 2), "Días Trabajados": int(worked), "Retardos": int(status == "Retardo" or (status == "Medio Día" and bool(marks) and first.time() > (datetime.combine(d, entrada_obj) + timedelta(minutes=tol)).time())),
                "Faltas": int(status == "Falta"), "Registros Incompletos": incomplete, "Estado": status, "Observación": observation})
    detalle = pd.DataFrame(daily)
    incid = pd.DataFrame(incidents, columns=["Empleado", "Fecha", "Tipo de Incidencia", "Observación"])
    if not detalle.empty:
        resumen = detalle.groupby(["Empleado", "Mes"], as_index=False).agg({"Faltas":"sum", "Retardos":"sum", "Registros Incompletos":"sum", "Días Trabajados":"sum", "Horas Trabajadas":"sum"})
        resumen["Horas Trabajadas"] = resumen["Horas Trabajadas"].round(2)
    else:
        resumen = pd.DataFrame(columns=["Empleado", "Mes", "Faltas", "Retardos", "Registros Incompletos", "Días Trabajados", "Horas Trabajadas"])
    return resumen, detalle, incid
