import pandas as pd
import unicodedata
import re


ALIASES = {
    "empleado": ["nombre", "empleado", "colaborador", "persona", "worker"],
    "id": ["numero", "número", "id", "no empleado", "numero empleado", "employee id"],
    "tiempo": ["tiempo", "fecha", "fecha hora", "datetime", "timestamp", "marcacion", "marcación"],
    "estado": ["estado", "tipo", "tipo marcacion", "tipo de marcacion", "entrada salida"],
}

def normalizar_texto(x):
    if pd.isna(x):
        return ""
    s = str(x).strip().upper()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s)
    return s

def detectar_columnas(df):
    cols = {c: normalizar_texto(c) for c in df.columns}
    mapeo = {}
    for objetivo, alias in ALIASES.items():
        alias_norm = [normalizar_texto(a) for a in alias]
        for col, norm in cols.items():
            if norm in alias_norm or any(a in norm for a in alias_norm if len(a) >= 5):
                mapeo[objetivo] = col
                break
    return mapeo

def validar_base(df, columna_empleado, columna_tiempo):
    avisos, errores = [], []
    if columna_empleado not in df.columns or columna_tiempo not in df.columns:
        errores.append("Selecciona las columnas de empleado y fecha/hora correctamente.")
        return avisos, errores
    if df[columna_empleado].isna().any():
        avisos.append(f"Hay {int(df[columna_empleado].isna().sum())} filas sin empleado.")
    if df[columna_tiempo].isna().any():
        avisos.append(f"Hay {int(df[columna_tiempo].isna().sum())} filas sin fecha/hora.")
    duplicados = df.duplicated().sum()
    if duplicados:
        avisos.append(f"Se encontraron {duplicados} filas duplicadas exactas.")
    return avisos, errores
