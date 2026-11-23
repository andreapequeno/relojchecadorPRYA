import pandas as pd
from io import BytesIO

def excel_consolidado(resumen, detalle, incidencias):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        resumen.to_excel(writer, sheet_name="Resumen mensual", index=False)
        detalle.to_excel(writer, sheet_name="Detalle diario", index=False)
        incidencias.to_excel(writer, sheet_name="Incidencias", index=False)
        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col in ws.columns:
                max_len = max((len(str(c.value)) if c.value is not None else 0 for c in col), default=8)
                ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 2, 12), 35)
    buffer.seek(0)
    return buffer

def excel_individual(df, sheet_name):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        ws = writer.book[sheet_name[:31]]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for col in ws.columns:
            max_len = max((len(str(c.value)) if c.value is not None else 0 for c in col), default=8)
            ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 2, 12), 35)
    buffer.seek(0)
    return buffer
