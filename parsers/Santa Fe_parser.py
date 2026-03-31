"""
santafe_parser.py - Parser para extractos del Banco Santa Fe.
"""
import re, pdfplumber, pandas as pd
from collections import defaultdict

LAYOUT = {
    "date_x":    (38,  93),
    "origen_x":  (93,  130),
    "concepto_x":(130, 315),
    "debit_x":   (315, 410),
    "credit_x":  (410, 492),
    "balance_x": (492, 560),
}

DATE_RE         = re.compile(r'^\d{1,2}/\d{2}/\d{4}$')
CUENTA_RE       = re.compile(r'Nro\.\s+(\d{4,}/\d{2})')
SALDO_ACTUAL_RE = re.compile(r'Saldo Actual al\s*:\s*(\d+)/(\d+)/(\d{4})', re.IGNORECASE)
SALDO_AL_RE     = re.compile(r'^Saldo\s+al\s+\d+/\d+/\d+', re.IGNORECASE)


def _conv(txt):
    if not txt: return 0.0
    t = txt.strip()
    neg = t.endswith('-')
    if neg: t = t[:-1]
    try: return float(t.replace(',','.')) * (-1 if neg else 1)
    except: return 0.0


def _cols(line_words):
    c = {'Fecha':None,'Origen':'','Concepto':'','Debito':None,'Credito':None,'Saldo':None}
    L = LAYOUT
    for w in sorted(line_words, key=lambda w: w['x0']):
        x, txt = w['x0'], w['text'].strip()
        if   L['date_x'][0]    <= x < L['date_x'][1]:    c['Fecha']    = txt
        elif L['origen_x'][0]  <= x < L['origen_x'][1]:  c['Origen']   = (c['Origen']+' '+txt).strip()
        elif L['concepto_x'][0]<= x < L['concepto_x'][1]:c['Concepto'] = (c['Concepto']+' '+txt).strip()
        elif L['debit_x'][0]   <= x < L['debit_x'][1]:   c['Debito']   = txt
        elif L['credit_x'][0]  <= x < L['credit_x'][1]:  c['Credito']  = txt
        elif L['balance_x'][0] <= x < L['balance_x'][1]: c['Saldo']    = txt
    return c


def _saldos(df):
    s = [df['Saldo'].iloc[0]]
    for i in range(1, len(df)):
        s.append(round(s[-1] + df['Crédito'].iloc[i] - df['Débito'].iloc[i], 2))
    return pd.Series(s, index=df.index)


def _save(resultados, pkey, movs, cuenta):
    if not movs: return
    key = pkey or f'Cta. {cuenta}'
    df = pd.DataFrame(movs)
    df = df.rename(columns={'Debito':'Débito','Credito':'Crédito'})
    df['Saldo Calculado'] = _saldos(df)
    df['Diferencia'] = (df['Saldo'] - df['Saldo Calculado']).round(2)
    resultados[key] = df
    incons = (df['Diferencia'].abs() > 0.02).sum()
    print(f"{'✅' if not incons else '⚠️ '}  {key}: {len(df)-1} movs | "
          f"saldo final {df['Saldo'].iloc[-1]:,.2f} | inconsistencias: {incons}")


def parsear_pdf(pdf_path):
    """
    Parsea un PDF del Banco Santa Fe (puede contener varios meses).
    Retorna dict { 'Cta. 276147/00 (12/2025)': DataFrame, ... }
    """
    resultados  = {}
    cuenta_nro  = 'desconocida'
    periodo_key = None
    movimientos = []
    en_movs     = False

    with pdfplumber.open(pdf_path) as pdf:
        print(f'📄 Abierto: {pdf_path} ({len(pdf.pages)} páginas)')

        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False)
            if not words: continue

            lmap = defaultdict(list)
            for w in words:
                lmap[round(w['top'])].append(w)

            for y in sorted(lmap):
                lw = lmap[y]
                joined = ' '.join(w['text'] for w in sorted(lw, key=lambda w: w['x0'])).strip()

                # Cuenta
                if cuenta_nro == 'desconocida':
                    m = CUENTA_RE.search(joined)
                    if m:
                        cuenta_nro = m.group(1)
                        print(f'🏦 Cuenta detectada: {cuenta_nro}')

                # Período (línea "Saldo Anterior  Saldo Actual al : DD/MM/YYYY")
                mp = SALDO_ACTUAL_RE.search(joined)
                if mp:
                    periodo_key = f'Cta. {cuenta_nro} ({mp.group(2)}/{mp.group(3)})'
                    continue

                # SALDO ANTERIOR
                if 'SALDO ANTERIOR' in joined.upper() and not en_movs:
                    en_movs = True
                    saldo_txt = None
                    for w in reversed(sorted(lw, key=lambda w: w['x0'])):
                        try: float(w['text'].replace(',','.').rstrip('-')); saldo_txt = w['text']; break
                        except: continue
                    movimientos = [{'Fecha':'SALDO ANTERIOR','Origen':'','Concepto':'SALDO ANTERIOR',
                                    'Debito':0.0,'Credito':0.0,'Saldo':_conv(saldo_txt or '0')}]
                    continue

                if not en_movs: continue

                # Fin de período
                if SALDO_AL_RE.match(joined):
                    en_movs = False
                    _save(resultados, periodo_key, movimientos, cuenta_nro)
                    movimientos = []
                    continue

                if joined.startswith('Ley 25'): continue

                c = _cols(lw)
                fecha = (c['Fecha'] or '').strip()
                tiene = c['Debito'] or c['Credito'] or c['Saldo']
                if fecha and DATE_RE.match(fecha) and tiene:
                    movimientos.append({'Fecha':fecha,'Origen':c['Origen'],
                                        'Concepto':c['Concepto'],'Debito':_conv(c['Debito']),
                                        'Credito':_conv(c['Credito']),'Saldo':_conv(c['Saldo'])})

        if en_movs and movimientos:
            _save(resultados, periodo_key, movimientos, cuenta_nro)

    # Post-fix: reemplazar claves con cuenta desconocida
    for k in list(resultados.keys()):
        if "desconocida" in k:
            new_k = k.replace("desconocida", cuenta_nro)
            resultados[new_k] = resultados.pop(k)

    if not resultados:
        print('❌  No se extrajeron movimientos.')
        return resultados

    # Consolidar todos los períodos en un único DataFrame por cuenta
    # (varios meses → una sola hoja en el Excel)
    clave_final = f'Cta. {cuenta_nro}'
    periodos_ordenados = sorted(resultados.keys())
    df_total = pd.concat(
        [resultados[k] for k in periodos_ordenados],
        ignore_index=True
    )
    print(f'📋 Consolidado → "{clave_final}": {len(df_total) - len(periodos_ordenados)} movs totales '
          f'({len(periodos_ordenados)} período(s))')
    return {clave_final: df_total}


if __name__ == '__main__':
    import sys, os
    pdf = sys.argv[1] if len(sys.argv) > 1 else 'pdfs/09_a_12_-_2025.pdf'
    if not os.path.exists(pdf):
        print(f'No se encontró: {pdf}'); sys.exit(1)
    r = parsear_pdf(pdf)
    print(f'\n─── {len(r)} período(s) ───')
    for k, df in r.items():
        print(f'  {k}: {len(df)-1} movs')

# Alias requerido por main.py
parse = parsear_pdf
