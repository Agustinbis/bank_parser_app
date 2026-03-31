# parsers/credicoop_parser.py
#
# Formato Banco Credicoop - Cuenta Corriente Comercial
# Columnas: FECHA | COMBTE | DESCRIPCION | DEBITO | CREDITO | SALDO
#
# Particularidades:
#   - El SALDO aparece solo en la última línea del grupo diario
#   - Algunas descripciones continúan en la línea siguiente (sin fecha)
#   - Una sola cuenta por PDF
#   - Fecha formato DD/MM/YY

import re
import pandas as pd
from collections import defaultdict
from .utils import open_pdf, calcular_saldos, reportar_inconsistencias
from .bank_profiles import BANK_PROFILES

DATE_RE   = re.compile(r'^\d{2}/\d{2}/\d{2}$')
CUENTA_RE = re.compile(r'Cta\.\s*([\d.]+)', re.IGNORECASE)


def convert_amount(txt: str) -> float:
    if not txt:
        return 0.0
    txt = txt.strip().replace('.', '').replace(',', '.')
    try:
        return float(txt)
    except ValueError:
        return 0.0


def extract_cuenta_label(all_lines: list[str]) -> str:
    for line in all_lines[:30]:
        m = CUENTA_RE.search(line)
        if m:
            return f"Cta. {m.group(1)}"
    return "Credicoop"


def parse(pdf_path: str) -> dict[str, pd.DataFrame]:
    """
    Parsea extractos del Banco Credicoop usando coordenadas X (pdfplumber).
    Devuelve  { 'Cta. 191.359.005183.4': DataFrame }
    """
    print(f'\n🔍 [DEBUG-parse] Inicio parse(): {pdf_path}')

    banco = 'CREDICOOP'
    profile = BANK_PROFILES.get(banco)
    if not profile:
        print(f'❌ No se encontró perfil para banco "{banco}"')
        return {}

    layout  = profile.get('layout', {})
    flags   = profile.get('flags', {})
    excluir = profile.get('excluir_si_contiene', [])

    es_invertido = bool(flags.get('es_layout_invertido', False))
    arranca_en_1 = bool(flags.get('saldo_arranca_en_fila_1', True))

    print(f'✅ Perfil: {banco} | invertido={es_invertido} | arranca_en_1={arranca_en_1}')

    en_detalle    = False
    movimientos   = []
    mov_pendiente = None
    cuenta_label  = 'Credicoop'

    with open_pdf(pdf_path) as pdf:
        # Detectar número de cuenta desde texto plano de las primeras páginas
        for page in pdf.pages[:2]:
            text = page.extract_text() or ''
            m = CUENTA_RE.search(text)
            if m:
                cuenta_label = f"Cta. {m.group(1)}"
                break
        print(f'🏦 Cuenta detectada: {cuenta_label}')

        for idx, page in enumerate(pdf.pages):
            words = page.extract_words(use_text_flow=False)
            if not words:
                continue

            # Agrupar palabras por línea (top redondeado)
            line_map = defaultdict(list)
            for w in words:
                y = round(w['top'])
                line_map[y].append(w)

            for y in sorted(line_map):
                line   = sorted(line_map[y], key=lambda w: w['x0'])
                texts  = [w['text'] for w in line]
                joined = ' '.join(texts).strip()
                upper  = joined.upper()

                # 1) Detectar inicio y capturar saldo anterior
                if not en_detalle:
                    if 'SALDO ANTERIOR' in upper:
                        en_detalle = True
                        # Capturar el saldo anterior como primera fila
                        for w in line:
                            if layout['balance_x'][0] <= w['x0'] < layout['balance_x'][1]:
                                saldo_anterior = convert_amount(w['text'].strip())
                                mov_pendiente = {
                                    'Fecha':       'SALDO ANTERIOR',
                                    'Descripción': 'SALDO ANTERIOR',
                                    'Débito':      0.0,
                                    'Crédito':     0.0,
                                    'Saldo':       saldo_anterior,
                                }
                                break
                    continue

                # 2) Detectar fin
                if re.search(r'SALDO AL \d{2}/\d{2}/\d{2}', upper):
                    if mov_pendiente:
                        movimientos.append(mov_pendiente)
                        mov_pendiente = None
                    en_detalle = False
                    continue

                # 3) Saltar encabezados y líneas excluidas
                if any(tok in upper for tok in excluir):
                    continue
                if 'FECHA' in upper and 'DEBITO' in upper:
                    continue

                # 4) Mapear columnas por coordenada X
                cols = {'Fecha': None, 'Descripción': '', 'Débito': None, 'Crédito': None, 'Saldo': None}

                for w in line:
                    x0, txt = w['x0'], w['text'].strip()
                    if layout["date_x"][0] <= x0 < layout["date_x"][1]:
                        cols['Fecha'] = txt
                    elif layout['desc_x'][0]   <= x0 < layout['desc_x'][1]:
                        cols['Descripción'] += (' ' + txt) if cols['Descripción'] else txt
                    elif layout['debit_x'][0]  <= x0 < layout['debit_x'][1]:
                        cols['Débito'] = txt
                    elif layout['credit_x'][0] <= x0 < layout['credit_x'][1]:
                        cols['Crédito'] = txt
                    elif layout['balance_x'][0] <= x0 < layout['balance_x'][1]:
                        cols['Saldo'] = txt

                fecha = (cols['Fecha'] or '').strip()

                # 5) ¿Línea con fecha? → nuevo movimiento
                if fecha and DATE_RE.match(fecha):
                    if mov_pendiente:
                        movimientos.append(mov_pendiente)

                    mov_pendiente = {
                        'Fecha':       fecha,
                        'Descripción': cols['Descripción'].strip(),
                        'Débito':      convert_amount(cols['Débito']),
                        'Crédito':     convert_amount(cols['Crédito']),
                        'Saldo':       convert_amount(cols['Saldo']) if cols['Saldo'] else None,
                    }

                elif mov_pendiente and cols['Descripción'] and not cols['Débito'] and not cols['Crédito'] and not cols['Saldo']:
                    # Línea sin fecha, sin importes → continuación de descripción
                    mov_pendiente['Descripción'] += ' ' + cols['Descripción'].strip()

    # Guardar último pendiente
    if mov_pendiente:
        movimientos.append(mov_pendiente)

    if not movimientos:
        print('❌ No se encontraron movimientos válidos.')
        return {}

    # ── Construir DataFrame ────────────────────────────────────────────────
    df = pd.DataFrame(movimientos)

    for col in ('Débito', 'Crédito', 'Saldo'):
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    df['Fecha'] = pd.to_datetime(df['Fecha'], format='%d/%m/%y', dayfirst=True, errors='coerce').dt.date

    df = calcular_saldos(
        df,
        es_layout_invertido=es_invertido,
        saldo_arranca_en_fila_1=arranca_en_1
    )
    reportar_inconsistencias(df)

    print(f'\n📊 {cuenta_label} → {len(df)} filas procesadas')
    return {cuenta_label: df}

