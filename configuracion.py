from datetime import time

DEFAULT_CONFIG = {
    "hora_entrada": time(8, 0),
    "hora_salida": time(18, 30),
    "tolerancia_minutos": 10,
    "dias_laborables": [0, 1, 2, 3, 4],
    "medio_dia_default": [(5, 10, "Día de las Madres"), (11, 2, "Día de Muertos"), (12, 24, "Nochebuena"), (12, 31, "Fin de Año")],
    "medio_dia_hora_salida": time(14, 0),
}


def generar_medio_dia_default(anios):
    filas = []
    for anio in anios:
        for mes, dia, motivo in DEFAULT_CONFIG["medio_dia_default"]:
            filas.append({"Fecha": f"{anio}-{mes:02d}-{dia:02d}", "Motivo": motivo})
    return filas
