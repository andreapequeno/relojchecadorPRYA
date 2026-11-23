# Control de Asistencia RH

Aplicación web Streamlit para procesar marcaciones exportadas de reloj checador, generar resumen mensual, detalle diario, incidencias y exportaciones Excel.


## Requisitos
- Python 3.10 o superior
- pip

## Instalación local
```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Archivos de entrada
### Asistencia
CSV, XLS o XLSX. Se deben mapear columnas de empleado y fecha-hora en la aplicación. El ID es opcional.

### Vacaciones autorizadas
Plantilla `data/plantilla_vacaciones.xlsx`: `Empleado`, `Fecha Inicio`, `Fecha Fin`, `Comentario`. Las fechas deben cubrir el período autorizado y el nombre del empleado debe coincidir (la comparación ignora mayúsculas, acentos y espacios repetidos).

### Días festivos
Plantilla `data/plantilla_dias_festivos.xlsx`: `Fecha`, `Descripción`. Cargar los días festivos oficiales aplicables. No se incorporan automáticamente calendarios legales, por lo que es responsabilidad de RH mantener esta lista.

### Medio horario
Plantilla `data/plantilla_dias_medio_horario.xlsx`: `Fecha`, `Motivo`. La aplicación propone 10 de mayo, 2 de noviembre, 24 y 31 de diciembre para los años detectados en el archivo. Es editable en la interfaz.

## Reglas predeterminadas
- Lunes a viernes.
- Entrada: 08:00.
- Tolerancia: 10 minutos; retardo a partir de después de 08:10.
- Salida normal: 18:30 (configurable).
- Salida sugerida en medio día: 14:00 (configurable).

## Cómo interpreta las marcaciones
El sistema ordena las marcaciones por empleado y fecha, y empareja cronológicamente de dos en dos (primera con segunda, tercera con cuarta, etc.). Esto permite calcular intervalos cuando el exportador no proporciona entradas y salidas confiables. Si queda una marcación sin pareja, se señala como incompleta. Una sola marcación antes o después del mediodía se clasifica como entrada sin salida o salida sin entrada, respectivamente.

**Limitación de datos:** el CSV analizado reporta prácticamente todas las marcaciones como `Entrada`, incluso por la tarde. Por ello, el programa no usa ese campo como fuente confiable para decidir entrada/salida. Validar el emparejamiento con RH antes de usar el resultado para nómina o sanciones.

## Despliegue en GitHub y Streamlit Cloud
1. Crear un repositorio GitHub y subir todos los archivos del proyecto, incluyendo `app.py`, `utils/`, `data/`, `requirements.txt y README.md.
2. En Streamlit Community Cloud, seleccionar **New app**.
3. Seleccionar el repositorio, rama y archivo principal `app.py`.
4. En Advanced settings, seleccionar una versión de Python compatible (3.11 recomendado).
5. Deploy. Streamlit instalará dependencias desde `requirements.txt`.
6. Probar primero con un archivo pequeño y validar resultados con RH antes de tomar decisiones laborales.

## Estructura
```text
control_asistencia/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── data/
│   ├── plantilla_vacaciones.xlsx
│   ├── plantilla_dias_festivos.xlsx
│   └── plantilla_dias_medio_horario.xlsx
├── utils/
│   ├── procesamiento.py
│   ├── validaciones.py
│   ├── reportes.py
│   └── configuracion.py
└── assets/
```

## Nota de interpretación
Este sistema es una herramienta de apoyo para revisión de asistencia. Las políticas laborales, descansos, permisos, vacaciones, calendarios y criterios de incidencias deben ser validados por la organización. El cálculo de horas es una estimación basada en parejas de marcaciones; no contempla pausas no registradas ni turnos nocturnos que crucen fechas.
