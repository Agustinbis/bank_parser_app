# parsers/nacion_parser.py
#
# Formato Banco de la Nación Argentina - Resumen Cuenta Corriente
# Columnas: FECHA | MOVIMIENTOS | COMPROB. | DEBITOS | CREDITOS | SALDO
#
# Particularidades:
#   - Empieza con "SALDO ANTERIOR" (sin fecha, tiene saldo)
#   - Cada fila tiene su propio SALDO
#   - Líneas "TRANSPORTE" al cambio de página → ignorar
#   - Termina con "SALDO FINAL"
#   - Fecha formato DD/MM/YY
#   - Una sola cuenta por PDF

import re
import pandas as pd
from collections import defaultdict
from .utils import open_pdf, calcular_saldos, reportar_inconsistencias
from .bank_profiles import BANK_PROFILES

DATE_RE   = re.compile(r'^\d{2}/\d{2}/\d{2}$')
CUENTA_RE = re.compile(r'NRO\.\s*CUENTA\s*\n?\s*([\d]+)', re.IGNORECASE)
CUENTA_RE2 = re.compile(r'(?:NRO\.?\s*CUENTA[^\d]*)(\d{7,})', re.IGNORECASE)


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
    Parsea extractos del Banco de la Nación Argentina.
    Devuelve  { 'Cta. 1440030604': DataFrame }
    """
    print(f'\n🔍 [DEBUG-parse] Inicio parse(): {pdf_path}')

    banco = 'NACION'
    profile = BANK_PROFILES.get(banco)
    if not profile:
        print(f'❌ No se encontró perfil para banco "{banco}"')
        print('   Asegurate de tener el bloque "NACION" en bank_profiles.py')
        return {}

    # Coordenadas verificadas con PDF real:
    #   date_x=(55,105), desc_x=(105,230), ref_x=(230,280)
    #   debit_x=(280,405), credit_x=(405,497), balance_x=(497,600)
    layout  = profile.get('layout', {})
    flags   = profile.get('flags', {})
    excluir = profile.get('excluir_si_contiene', [])

    es_invertido = bool(flags.get('es_layout_invertido', False))
    arranca_en_1 = bool(flags.get('saldo_arranca_en_fila_1', True))

    print(f'✅ Perfil: {banco} | invertido={es_invertido} | arranca_en_1={arranca_en_1}')

    en_detalle    = False
    movimientos   = []
    mov_pendiente = None
    cuenta_label  = 'Nacion'

    with open_pdf(pdf_path) as pdf:
        # Detectar número de cuenta desde texto plano de las primeras páginas
        for page in pdf.pages[:2]:
            text = page.extract_text() or ''
            m = CUENTA_RE2.search(text)
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

                # 1) Detectar inicio: "SALDO ANTERIOR"
                if not en_detalle:
                    if 'SALDO ANTERIOR' in upper:
                        en_detalle = True
                        # Capturar el saldo anterior como primera fila
                        saldo_val = None
                        for w in line:
                            if layout['balance_x'][0] <= w['x0'] < layout['balance_x'][1]:
                                saldo_val = convert_amount(w['text'].strip())
                                break
                        # Si el saldo está en la misma línea como último token numérico
                        if saldo_val is None:
                            for w in reversed(line):
                                txt = w['text'].strip().replace('.', '').replace(',', '.')
                                try:
                                    saldo_val = float(txt)
                                    break
                                except ValueError:
                                    continue
                        if saldo_val is not None:
                            mov_pendiente = {
                                'Fecha':       'SALDO ANTERIOR',
                                'Descripción': 'SALDO ANTERIOR',
                                'Comprobante': '',
                                'Débito':      0.0,
                                'Crédito':     0.0,
                                'Saldo':       saldo_val,
                            }
                    continue

                # 2) Detectar fin: "SALDO FINAL"
                if 'SALDO FINAL' in upper:
                    if mov_pendiente:
                        movimientos.append(mov_pendiente)
                        mov_pendiente = None
                    en_detalle = False
                    continue

                # 3) Ignorar líneas de transporte y encabezados
                if 'TRANSPORTE' in upper and len(texts) <= 3:
                    # Línea de transporte de página: solo tiene la palabra y el saldo
                    continue

                if any(tok in upper for tok in excluir):
                    continue

                if 'FECHA' in upper and ('DEBITO' in upper or 'DÉBITO' in upper):
                    continue

                # 4) Mapear columnas por coordenada X
                cols = {
                    'Fecha': None,
                    'Descripción': '',
                    'Comprobante': '',
                    'Débito': None,
                    'Crédito': None,
                    'Saldo': None,
                }

                for w in line:
                    x0, txt = w['x0'], w['text'].strip()
                    if layout['date_x'][0]    <= x0 < layout['date_x'][1]:
                        cols['Fecha'] = txt
                    elif layout['desc_x'][0]  <= x0 < layout['desc_x'][1]:
                        cols['Descripción'] += (' ' + txt) if cols['Descripción'] else txt
                    elif layout['ref_x'][0]   <= x0 < layout['ref_x'][1]:
                        cols['Comprobante'] += (' ' + txt) if cols['Comprobante'] else txt
                    elif layout['debit_x'][0] <= x0 < layout['debit_x'][1]:
                        cols['Débito'] = txt
                    elif layout['credit_x'][0] <= x0 < layout['credit_x'][1]:
                        cols['Crédito'] = txt
                    elif layout['balance_x'][0] <= x0 < layout['balance_x'][1]:
                        cols['Saldo'] = txt

                fecha = (cols['Fecha'] or '').strip()
                tiene_importe = cols['Débito'] or cols['Crédito'] or cols['Saldo']

                # 5) Línea con fecha válida → nuevo movimiento
                if fecha and DATE_RE.match(fecha) and tiene_importe:
                    if mov_pendiente:
                        movimientos.append(mov_pendiente)

                    mov_pendiente = {
                        'Fecha':        fecha,
                        'Descripción':  cols['Descripción'].strip(),
                        'Comprobante':  cols['Comprobante'].strip(),
                        'Débito':       convert_amount(cols['Débito']),
                        'Crédito':      convert_amount(cols['Crédito']),
                        'Saldo':        convert_amount(cols['Saldo']) if cols['Saldo'] else None,
                    }

                elif mov_pendiente and not fecha and cols['Descripción'] and not tiene_importe:
                    # Continuación de descripción (sin fecha, sin importes)
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

    # Convertir fechas (la primera fila es "SALDO ANTERIOR", toleramos el error)
    df['Fecha'] = pd.to_datetime(
        df['Fecha'], format='%d/%m/%y', dayfirst=True, errors='coerce'
    ).dt.date

    df = calcular_saldos(
        df,
        es_layout_invertido=es_invertido,
        saldo_arranca_en_fila_1=arranca_en_1
    )
    reportar_inconsistencias(df)

    print(f'\n📊 {cuenta_label} → {len(df)} filas procesadas')
    return {cuenta_label: df}
