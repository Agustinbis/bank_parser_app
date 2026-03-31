# parsers/santander_parser.py
#
# Formato Banco Santander Argentina - Resumen Cuenta Corriente
# Columnas: FECHA | COMPROBANTE | MOVIMIENTO | DÉBITO | CRÉDITO | SALDO EN CUENTA
#
# Particularidades:
#   - Cada fila tiene su propio saldo
#   - La descripción puede continuar en la línea siguiente (sin fecha)
#   - El "Saldo Inicial" viene con fecha pero sin débito/crédito
#   - Una sola cuenta por PDF
#   - Fecha formato DD/MM/YY

import re
import pandas as pd
from collections import defaultdict
from .utils import open_pdf, calcular_saldos, reportar_inconsistencias
from .bank_profiles import BANK_PROFILES

DATE_RE   = re.compile(r'^\d{2}/\d{2}/\d{2}$')
CUENTA_RE = re.compile(r'Cuenta\s+Corriente\s+N[°º]\s*([\d\-/]+)', re.IGNORECASE)


def convert_amount(txt: str) -> float:
    if not txt:
        return 0.0
    txt = txt.strip().replace('.', '').replace(',', '.')
    try:
        return float(txt)
    except ValueError:
        return 0.0


def parse(pdf_path: str) -> dict[str, pd.DataFrame]:
    """
    Parsea extractos del Banco Santander Argentina.
    Devuelve  { 'CC Nº 447-000577/7': DataFrame }
    """
    print(f'\n🔍 [DEBUG-parse] Inicio parse(): {pdf_path}')

    banco = 'SANTANDER'
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
    cuenta_label  = 'Santander'

    with open_pdf(pdf_path) as pdf:
        # Detectar número de cuenta
        for page in pdf.pages[:3]:
            text = page.extract_text() or ''
            m = CUENTA_RE.search(text)
            if m:
                cuenta_label = f"CC Nº {m.group(1)}"
                break
        print(f'🏦 Cuenta detectada: {cuenta_label}')

        for idx, page in enumerate(pdf.pages):
            words = page.extract_words(use_text_flow=False)
            if not words:
                continue

            line_map = defaultdict(list)
            for w in words:
                y = round(w['top'])
                line_map[y].append(w)

            for y in sorted(line_map):
                line   = sorted(line_map[y], key=lambda w: w['x0'])
                texts  = [w['text'] for w in line]
                joined = ' '.join(texts).strip()
                upper  = joined.upper()

                # 1) Detectar inicio: línea con "Saldo Inicial"
                if not en_detalle:
                    if 'SALDO INICIAL' in upper:
                        en_detalle = True
                        # No hacemos continue: dejamos caer al procesamiento normal
                        # para que la línea "29/11/25 Saldo Inicial $ 273.458,68"
                        # se capture como primera fila con su saldo
                    else:
                        continue

                # 2) Detectar fin
                if 'SALDO TOTAL' in upper:
                    if mov_pendiente:
                        movimientos.append(mov_pendiente)
                        mov_pendiente = None
                    en_detalle = False
                    continue

                # 3) Saltar encabezados y excluidos
                if any(tok in upper for tok in excluir):
                    continue
                if 'FECHA' in upper and ('DÉBITO' in upper or 'DEBITO' in upper):
                    continue

                # 4) Mapear columnas por coordenada X
                cols = {'Fecha': None, 'Descripción': '', 'Débito': None, 'Crédito': None, 'Saldo': None}
                saldo_negativo = False  # flag para "- $ 273.458,68"

                for w in line:
                    x0, txt = w['x0'], w['text'].strip()
                    if txt in ('$', '-$'):
                        if txt == '-$' and layout['balance_x'][0] <= x0 < layout['balance_x'][1]:
                            saldo_negativo = True
                        continue   # saltar símbolo $ y -$
                    if layout['date_x'][0]    <= x0 < layout['date_x'][1]:
                        cols['Fecha'] = txt
                    elif layout['desc_x'][0]  <= x0 < layout['desc_x'][1]:
                        cols['Descripción'] += (' ' + txt) if cols['Descripción'] else txt
                    elif layout['debit_x'][0] <= x0 < layout['debit_x'][1]:
                        cols['Débito'] = txt
                    elif layout['credit_x'][0] <= x0 < layout['credit_x'][1]:
                        cols['Crédito'] = txt
                    elif layout['balance_x'][0] <= x0 < layout['balance_x'][1]:
                        cols['Saldo'] = ('-' + txt) if saldo_negativo else txt

                fecha = (cols['Fecha'] or '').strip()
                tiene_importe = cols['Débito'] or cols['Crédito'] or cols['Saldo']

                # 5) Línea con fecha Y al menos un importe → nuevo movimiento
                if fecha and DATE_RE.match(fecha) and tiene_importe:
                    if mov_pendiente:
                        movimientos.append(mov_pendiente)

                    mov_pendiente = {
                        'Fecha':       fecha,
                        'Descripción': cols['Descripción'].strip(),
                        'Débito':      convert_amount(cols['Débito']),
                        'Crédito':     convert_amount(cols['Crédito']),
                        'Saldo':       convert_amount(cols['Saldo']) if cols['Saldo'] else None,
                    }

                elif mov_pendiente and not fecha and cols['Descripción'] and not tiene_importe:
                    # Sin fecha, sin importes → continuación de descripción
                    mov_pendiente['Descripción'] += ' ' + cols['Descripción'].strip()

                elif mov_pendiente and not fecha and cols['Descripción'] and tiene_importe:
                    # Sub-movimiento sin fecha propia (impuesto, SIRCREB): es un movimiento nuevo
                    # que hereda la fecha del movimiento anterior
                    movimientos.append(mov_pendiente)
                    mov_pendiente = {
                        'Fecha':       movimientos[-1]['Fecha'],
                        'Descripción': cols['Descripción'].strip(),
                        'Débito':      convert_amount(cols['Débito']),
                        'Crédito':     convert_amount(cols['Crédito']),
                        'Saldo':       convert_amount(cols['Saldo']) if cols['Saldo'] else None,
                    }

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
