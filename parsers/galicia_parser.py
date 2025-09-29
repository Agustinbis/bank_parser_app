import pdfplumber
import pandas as pd
import re
from pathlib import Path
from parsers.utils import calcular_saldos, reportar_inconsistencias, open_pdf


# ------------------------------------------------
# 1) Helpers de conversión
# ------------------------------------------------
def convertir_a_float(valor):
    try:
        valor = str(valor).strip()
        if valor.endswith('-'):
            valor = '-' + valor[:-1]
        valor = valor.replace('–', '-').replace('−', '-')
        if ',' in valor:
            int_part, dec_part = valor.split(',')
            int_part = int_part.replace('.', '')
            valor = f"{int_part}.{dec_part}"
        valor = re.sub(r'[^\d\.\-]', '', valor)
        return float(valor)
    except Exception as e:
        print(f"⚠️ Error al convertir banco Galicia: '{valor}' → {e}")
        return None

def parse_amount(value):
    if not value:
        return 0.0
    value = value.strip()
    if value.endswith('-'):
        value = '-' + value[:-1]
    value = value.replace('.', '').replace(',', '.')
    try:
        return float(value)
    except ValueError:
        return 0.0

# ------------------------------------------------
# 2) Extracción de movimientos (tu código actual)
# ------------------------------------------------
def extract_movements_by_x0(pdf_path: str) -> pd.DataFrame:
    rows = []
    with open_pdf(pdf_path) as pdf:
        for page in pdf.pages:
            words= page.extract_words()
        for page_num, page in enumerate(pdf.pages, start=1):
            words = page.extract_words()
            if not words:
                print(f"⚠️ Página {page_num} sin contenido.")
                continue

            line_map = {}
            for w in words:
                top = round(w['top'], 1)
                line_map.setdefault(top, []).append(w)

            for top in sorted(line_map):
                line = sorted(line_map[top], key=lambda w: w['x0'])
                fecha = descripcion = ""
                credito = debito = saldo = 0.0

                for i, w in enumerate(line):
                    x, text = w['x0'], w['text'].strip()
                    if i == 0 and "/" in text and len(text) <= 10:
                        fecha = text
                    elif x < 300 and not re.search(r"\d+[,\.]\d{2}-?$", text) and "/" not in text:
                        descripcion += text + " "
                    elif 250 <= x < 400:
                        credito = abs(parse_amount(text))
                    elif 400 <= x < 520:
                        debito = abs(parse_amount(text))
                    elif x >= 520:
                        saldo = parse_amount(text)

                if fecha:
                    rows.append({
                        "Fecha": fecha.strip(),
                        "Descripción": descripcion.strip(),
                        "Crédito": round(credito, 2),
                        "Débito": round(debito, 2),
                        "Saldo": round(convertir_a_float(saldo), 2)
                    })

    return pd.DataFrame(rows)

# ------------------------------------------------
# 3) Función pública parse()
# ------------------------------------------------
es_layout_invertido = True  # Ajustalo según tu layout

def parse(pdf_path: str) -> pd.DataFrame:
    # 1) Extraer movimientos
    df = extract_movements_by_x0(pdf_path)

    # 2) Si no extrajo nada, devolvemos vacío
    if df.empty:
        print(f"❌ No se extrajeron movimientos de {pdf_path}")
        return df

    # 3) Calcular saldo y diferencia
    df = calcular_saldos(df, es_layout_invertido)

    # 4) Reportar inconsistencias
    reportar_inconsistencias(df)

    return df

