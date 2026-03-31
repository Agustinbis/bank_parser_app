# parsers/Coinag_parser.py
#
# Parser para extractos del Banco Coinag S.A.
# Formato: Cuenta Corriente en Pesos (multi-página)
#
# Layout calibrado con PDF real (ancho=595pt).
# Las columnas numéricas están RIGHT-ALIGNED, por lo tanto se clasifica
# por x1 (borde derecho del word) en lugar de x0, que varía según el tamaño
# del número.
#
#   Fecha          → x0 ≈  68  → detectar por x0 < 100
#   Concepto       → x0 ≈ 102  → 100 ≤ x0 < 290  (incluye Comprob.)
#   Por Acreditar  → x1 ≈ 415  → 390 ≤ x1 ≤ 425
#   Débito         → x1 ≈ 446  → 430 ≤ x1 ≤ 460
#   Crédito        → x1 ≈ 510  → 495 ≤ x1 ≤ 525
#   Saldo          → x1 ≈ 572  → x1 ≥ 555
#
# Notas:
#   - La fecha solo aparece en el primer movimiento de cada día; se propaga.
#   - "LEY 25413 S/CREDITO" debita la cuenta (aparece en columna Débito).
#   - Las sub-líneas "NroTransaccion:" y "Nro. Tarj:" se omiten.
#   - "Transporte" al inicio de cada página (desde pág. 2) se omite.
#   - La tabla "Detalle de Tributos Debitados" del final se omite.
#   - es_layout_invertido = True: saldo = anterior + crédito − débito

import re
import pandas as pd
from collections import defaultdict
from .utils import open_pdf, calcular_saldos, reportar_inconsistencias

# Patrón de fecha: D/M/YYYY o DD/MM/YYYY
_DATE_RE = re.compile(r'^\d{1,2}/\d{1,2}/\d{4}$')

# Palabras clave en el texto de línea que indican encabezado o pie a saltar
_SKIP_LINE_KEYWORDS = [
    'Fecha Concepto',       # encabezado de tabla
    'CUENTA CORRIENTE',     # encabezado de sección
    'Cliente Nº',           # encabezado
    'Período:',             # encabezado
    'Saldo Ant.',           # saldo anterior (pág 1)
    'Transporte',           # saldo transportado entre páginas
    'SERVICIOS DE',         # razón social del cliente
    'IVA:',                 # datos del cliente
    'CBU:',                 # datos del cliente
    'CUIT:',                # datos del banco/cliente
    'Resumen de Cuenta',    # título del documento
    'BANCO COINAG',         # nombre del banco
    'Casa Central',         # dirección del banco
    'Sucursal:',            # sucursal
    'Detalle de Tributos',  # tabla resumen de tributos (al final del PDF)
    'Base Imponible',       # encabezado de tabla de tributos
]

# Prefijos del primer word de línea que indican sub-detalle a omitir
_SKIP_PREFIXES = (
    'NroTransaccion:',   # detalle de cada movimiento
    'Nro.',              # "Nro. Tarj: ..."
    'Operacion',         # "Operacion de Acreditación a Comercios..."
    'Usted',             # texto legal
    'Los',               # texto legal
    'Si',                # texto legal
    'Pág.',              # "Pág. X/XX"
    'http',              # URL (texto legal)
    'RECLAMOS:',         # texto legal
    'IMPUESTOS',         # texto legal
    'Se',                # texto legal
    'Las',               # texto legal
    'DEBITOS',           # texto legal
    'Asimismo,',         # texto legal
    'Ante',              # texto legal
    'INFORMACIÓN',       # texto legal
    'Total:',            # total de tabla de tributos
)


def _parse_amount(text: str) -> float:
    """
    Convierte importes argentinos a float.
    Ejemplos: '1.440,00' → 1440.0 | '12.578.851,56' → 12578851.56
    """
    text = text.strip()
    if not text:
        return 0.0
    try:
        return float(text.replace('.', '').replace(',', '.'))
    except ValueError:
        return 0.0


def parse(pdf_path: str) -> pd.DataFrame:
    """
    Parsea extractos del Banco Coinag S.A.

    Args:
        pdf_path: Ruta al archivo PDF del extracto.

    Returns:
        DataFrame con columnas:
            Fecha, Descripción, Por Acreditar, Débito, Crédito, Saldo,
            Saldo Calculado, Diferencia
    """
    print(f"\n🔍 [COINAG] Parseando: {pdf_path}")

    rows = []
    last_date = None

    with open_pdf(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            words = page.extract_words()
            if not words:
                continue

            # ── Agrupar words por línea (coordenada top) ──────────────────
            line_map = defaultdict(list)
            for w in words:
                line_map[round(w['top'], 1)].append(w)

            for top in sorted(line_map):
                line = sorted(line_map[top], key=lambda w: w['x0'])
                if not line:
                    continue

                all_text  = ' '.join(w['text'] for w in line)
                first_txt = line[0]['text']

                # ── Filtro 1: encabezados, pies y textos legales ───────────
                if any(kw in all_text for kw in _SKIP_LINE_KEYWORDS):
                    continue
                if first_txt.startswith(_SKIP_PREFIXES):
                    continue

                # ── Filtro 2: la línea debe tener un Saldo (x1 ≥ 555) ────
                # Coinag usa columnas right-aligned → clasificamos por x1:
                #   Saldo   x1 ≈ 572  → x1 ≥ 555
                #   Crédito x1 ≈ 510  → 495 ≤ x1 ≤ 525
                #   Débito  x1 ≈ 446  → 430 ≤ x1 ≤ 460
                saldo_words = [w for w in line if w['x1'] >= 555]
                if not saldo_words:
                    continue

                # El valor del saldo debe parecer un importe (contiene coma)
                saldo_text = saldo_words[0]['text']
                if ',' not in saldo_text:
                    continue
                saldo = _parse_amount(saldo_text)

                # ── Fecha (x0 < 100) ───────────────────────────────────────
                date_words = [w for w in line if w['x0'] < 100]
                if date_words and _DATE_RE.match(date_words[0]['text']):
                    last_date = date_words[0]['text']

                # Sin fecha aún = páginas de portada → saltar
                if last_date is None:
                    continue

                # ── Descripción (100 ≤ x0 < 290) ──────────────────────────
                desc_words = [w for w in line if 100 <= w['x0'] < 290]
                if not desc_words:
                    continue

                # Los movimientos reales siempre empiezan en x0 ≈ 102.
                # La tabla "Detalle de Tributos" empieza en x0 ≈ 145 → filtrar.
                if desc_words[0]['x0'] > 120:
                    continue

                descripcion = ' '.join(w['text'] for w in desc_words).strip()
                if not descripcion:
                    continue

                # ── Por Acreditar (x1 entre 390 y 425) ────────────────────
                # (raramente tiene valores; se incluye por completitud)
                por_acred_words = [w for w in line if 390 <= w['x1'] <= 425]
                por_acreditar = (_parse_amount(por_acred_words[0]['text'])
                                 if por_acred_words else 0.0)

                # ── Débito (x1 ≈ 446, rango 430-460) ─────────────────────
                debito_words = [w for w in line if 430 <= w['x1'] <= 460]
                debito = (_parse_amount(debito_words[0]['text'])
                          if debito_words else 0.0)

                # ── Crédito (x1 ≈ 510, rango 495-525) ────────────────────
                credito_words = [w for w in line if 495 <= w['x1'] <= 525]
                credito = (_parse_amount(credito_words[0]['text'])
                           if credito_words else 0.0)

                rows.append({
                    "Fecha":         last_date,
                    "Descripción":   descripcion,
                    "Por Acreditar": round(por_acreditar, 2),
                    "Débito":        round(debito,        2),
                    "Crédito":       round(credito,       2),
                    "Saldo":         round(saldo,         2),
                })

    # ── Construir DataFrame ────────────────────────────────────────────────
    df = pd.DataFrame(rows)

    if df.empty:
        print("❌ [COINAG] No se extrajeron movimientos.")
        return df

    # Convertir fechas al tipo date
    df["Fecha"] = pd.to_datetime(
        df["Fecha"], format="%d/%m/%Y", dayfirst=True, errors="coerce"
    ).dt.date

    # Calcular saldo teórico y reportar inconsistencias
    # es_layout_invertido=True: saldo sube con créditos y baja con débitos
    # saldo_arranca_en_fila_1=True: el saldo de la fila 0 es la base inicial
    df = calcular_saldos(df, es_layout_invertido=True, saldo_arranca_en_fila_1=True)
    reportar_inconsistencias(df)

    print(f"✅ [COINAG] {len(df)} movimientos extraídos.")
    return df
