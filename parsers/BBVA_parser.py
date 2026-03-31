# parsers/frances_parser.py
#
# Formato BBVA Argentina - Resumen Pymes y Negocios
# Columnas: FECHA | ORIGEN | CONCEPTO | DÉBITO | CRÉDITO | SALDO
# Puede contener múltiples cuentas por PDF.
#
# Lógica de detección:
#   - Cuenta nueva  →  línea con "CC $ NNN-NNN/N" + "CTA" o "BANCARIA"
#   - Inicio datos  →  línea con "SALDO ANTERIOR"
#   - Fin datos     →  línea con "SALDO AL DD DE" o "TOTAL MOVIMIENTOS"
#   - Movimiento    →  primera token DD/MM + al menos 2 importes al final

import re
import pandas as pd
from .utils import open_pdf, calcular_saldos, reportar_inconsistencias
from .bank_profiles import BANK_PROFILES

# Detecta encabezado de cuenta:  CC $ 081-351144/1  o  CA $ 081-351145/8
ACCOUNT_RE = re.compile(r'\b(CC|CA)\s*\$\s*(\d[\d-]+/\d+)', re.IGNORECASE)

# Detecta importes en formato argentino: -1.234.567,89  o  1.234,56
IMPORTE_RE = re.compile(r'-?\d{1,3}(?:\.\d{3})*,\d{2}')

# Detecta fecha DD/MM exacta
DATE_RE = re.compile(r'^\d{2}/\d{2}$')


def convert_amount(txt: str) -> float:
    """'1.234,56' → 1234.56  |  '-278,96' → -278.96"""
    if not txt:
        return 0.0
    txt = txt.strip()
    neg = txt.startswith('-')
    txt = txt.lstrip('-').replace('.', '').replace(',', '.')
    try:
        v = float(txt)
        return -v if neg else v
    except ValueError:
        return 0.0


def extract_account_label(line: str) -> str | None:
    """Retorna 'CC $ 081-351144/1' si la línea es un encabezado de cuenta."""
    upper = line.upper()
    if not ('CTA' in upper or 'BANCARIA' in upper or 'MOVIMIENTO' in upper):
        return None
    m = ACCOUNT_RE.search(line)
    if m:
        return f"{m.group(1).upper()} $ {m.group(2)}"
    return None


def parse(pdf_path: str) -> dict[str, pd.DataFrame]:
    """
    Parsea extractos BBVA/Francés Argentina.
    Devuelve  { 'CC $ 081-351144/1': DataFrame, ... }
    """
    print(f'\n🔍 [DEBUG-parse] Inicio parse(): {pdf_path}')

    banco = 'FRANCES'
    profile = BANK_PROFILES.get(banco)
    if not profile:
        print(f'❌ No se encontró perfil para banco "{banco}"')
        return {}

    flags   = profile.get('flags', {})
    excluir = profile.get('excluir_si_contiene', [])

    es_invertido = bool(flags.get('es_layout_invertido', False))
    arranca_en_1 = bool(flags.get('saldo_arranca_en_fila_1', True))

    print(f'✅ Perfil: {banco} | invertido={es_invertido} | arranca_en_1={arranca_en_1}')

    # ── Estado del parser ──────────────────────────────────────────────────
    cuentas: dict[str, list[dict]] = {}
    cuenta_actual: str | None = None
    en_detalle: bool = False

    # ── Extraer texto del PDF ──────────────────────────────────────────────
    all_lines: list[str] = []
    with open_pdf(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            all_lines.extend(text.split('\n'))
    print(f'   → Líneas totales: {len(all_lines)}')

    # ── Procesar línea por línea ───────────────────────────────────────────
    for raw in all_lines:
        line  = raw.strip()
        if not line:
            continue
        upper = line.upper()

        # 1) ¿Es encabezado de cuenta?
        label = extract_account_label(line)
        if label:
            if label not in cuentas:
                cuentas[label] = []
                print(f'🏦 Cuenta detectada: {label}')
            cuenta_actual = label
            en_detalle    = False
            continue

        if cuenta_actual is None:
            continue

        # 2) ¿Inicio del detalle?
        if not en_detalle:
            if 'SALDO ANTERIOR' in upper:
                en_detalle = True
            continue

        # 3) ¿Fin del detalle?
        if re.search(r'SALDO AL \d{1,2} DE', upper) or 'TOTAL MOVIMIENTOS' in upper:
            en_detalle    = False
            cuenta_actual = None
            continue

        # 4) Saltar líneas de encabezado de columnas o excluidas
        if any(tok in upper for tok in excluir):
            continue
        if 'FECHA' in upper and ('DÉBITO' in upper or 'DEBITO' in upper or 'CREDITO' in upper):
            continue

        # 5) ¿Tiene fecha DD/MM como primer token?
        tokens = line.split()
        if not tokens or not DATE_RE.match(tokens[0]):
            continue

        # 6) Extraer todos los importes de la línea
        importes = IMPORTE_RE.findall(line)
        if not importes:
            continue

        fecha     = tokens[0]
        saldo_raw = importes[-1]    # último importe = Saldo

        # Determinar Débito y Crédito según cuántos importes haya antes del saldo
        debito_raw  = ''
        credito_raw = ''

        if len(importes) >= 3:
            # Tres o más: antepenúltimo=Débito, penúltimo=Crédito
            debito_raw  = importes[-3]
            credito_raw = importes[-2]
        elif len(importes) == 2:
            # Solo un importe antes del saldo → clasificar por signo
            unico = importes[-2]
            if unico.startswith('-'):
                debito_raw = unico
            else:
                credito_raw = unico
        # len == 1 → solo saldo, no es movimiento válido → se ignora implícitamente

        debito  = abs(convert_amount(debito_raw))
        credito = abs(convert_amount(credito_raw))
        saldo   = convert_amount(saldo_raw)

        # 7) Descripción: todo entre la fecha (+ 1 token de origen) y el primer importe
        first_pos   = line.find(importes[0])
        desc_raw    = line[len(fecha):first_pos].strip()
        desc_tokens = desc_raw.split(None, 1)
        # El primer token suele ser el código ORIGEN (D, C, D 569, etc.)
        # Si es corto (≤2 chars) lo saltamos; si es el código "D 569" también
        if desc_tokens and re.fullmatch(r'[A-Z]{1,2}', desc_tokens[0]):
            descripcion = desc_tokens[1].strip() if len(desc_tokens) > 1 else ''
        else:
            descripcion = desc_raw

        cuentas[cuenta_actual].append({
            'Fecha':       fecha,
            'Descripción': descripcion,
            'Débito':      debito,
            'Crédito':     credito,
            'Saldo':       saldo,
        })

    # ── Convertir a DataFrames ─────────────────────────────────────────────
    dfs: dict[str, pd.DataFrame] = {}

    for label, movs in cuentas.items():
        if not movs:
            print(f'⚠️  {label} → sin movimientos')
            continue

        df = pd.DataFrame(movs)

        for col in ('Débito', 'Crédito', 'Saldo'):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # Fecha DD/MM sin año: pandas infiere año actual
        df['Fecha'] = pd.to_datetime(df['Fecha'], format='%d/%m', errors='coerce').dt.date

        df = calcular_saldos(
            df,
            es_layout_invertido=es_invertido,
            saldo_arranca_en_fila_1=arranca_en_1
        )
        reportar_inconsistencias(df)

        dfs[label] = df
        print(f'\n📊 {label} → {len(df)} filas procesadas')

    if not dfs:
        print('❌ No se encontraron movimientos válidos.')
    else:
        print(f'\n✅ Parseo completo. Hojas: {list(dfs.keys())}')

    return dfs

